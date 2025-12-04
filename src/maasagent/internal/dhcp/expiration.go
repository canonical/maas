// Copyright (c) 2025 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

package dhcp

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net"
	"sync"
	"time"

	"github.com/canonical/microcluster/v2/state"
	"github.com/rs/zerolog/log"

	"maas.io/core/src/maasagent/internal/dhcpd"
)

const (
	fetchExpiredLeasesStmt          = "SELECT * FROM lease WHERE state=$1 AND ($2 - updated_at) * 100 >= lifetime;"
	deleteExpiredLeasesStmt         = "DELETE FROM lease WHERE state=$1 AND ($2 - updated_at) * 100 >= lifetime;"
	deleteAndFetchExpiredLeasesStmt = "DELETE FROM lease WHERE state=$1 AND ($2 - updated_at) * 100 >= lifetime RETURNING *;"
	insertExpirationStmt            = "INSERT INTO expiration (id, ip, mac_address, duid, created_at) VALUES (NULL, $1, $2, $3, $4);"
)

type ExpirationHandler struct {
	clusterState  state.State
	leaseReporter LeaseReporter
	tick          *time.Ticker
	stateLock     sync.RWMutex
}

func newExpirationHandler(sweepInterval time.Duration) *ExpirationHandler {
	return &ExpirationHandler{
		tick: time.NewTicker(sweepInterval),
	}
}

func (e *ExpirationHandler) Start(ctx context.Context) error {
	defer e.tick.Stop()

	for {
		select {
		case <-ctx.Done():
			return nil
		case ts := <-e.tick.C:
			err := func() error {
				e.stateLock.RLock()
				defer e.stateLock.RUnlock()

				if e.clusterState == nil {
					log.Warn().Msg("expiration handler's cluster state not set")
					return nil
				}

				err := e.clusterState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
					err := e.expire(ctx, tx, ts)
					if err != nil && !errors.Is(err, sql.ErrNoRows) {
						return err
					}

					return nil
				})
				if err != nil {
					return fmt.Errorf("error initializing expiration transaction: %w", err)
				}

				return nil
			}()
			if err != nil {
				return err
			}
		}
	}
}

func (e *ExpirationHandler) SetClusterState(s state.State) {
	e.stateLock.Lock()
	defer e.stateLock.Unlock()

	e.clusterState = s
}

func (e *ExpirationHandler) expireLeases(ctx context.Context, tx *sql.Tx, leaseRows *sql.Rows, ts time.Time, report bool) error {
	epoch := ts.Unix()

	var leases []Lease

	for leaseRows.Next() {
		var (
			lease         Lease
			ipStr, macStr string
		)

		err := leaseRows.Scan(
			&lease.ID,
			&ipStr,
			&macStr,
			&lease.DUID,
			&lease.CreatedAt,
			&lease.UpdatedAt,
			&lease.Lifetime,
			&lease.State,
			&lease.NeedsSync,
			&lease.RangeID,
		)
		if err != nil {
			return fmt.Errorf("error fetching expired leases: %w", err)
		}

		lease.IP = net.ParseIP(ipStr)

		lease.MACAddress, err = net.ParseMAC(macStr)
		if err != nil {
			return fmt.Errorf("error parsing lease MAC: %w", err)
		}

		leases = append(leases, lease)
	}

	if err := leaseRows.Err(); err != nil {
		return fmt.Errorf("error querying expired leases: %w", err)
	}

	for _, lease := range leases {
		ip := lease.IP.String()
		mac := lease.MACAddress.String()

		_, err := tx.ExecContext(
			ctx,
			insertExpirationStmt,
			ip,
			mac,
			lease.DUID,
			epoch,
		)
		if err != nil {
			return fmt.Errorf("error writing expirations: %w", err)
		}

		ipVer := "ipv6"
		if lease.IP.To4() != nil {
			ipVer = "ipv4"
		}

		err = e.leaseReporter.EnqueueLeaseNotification(ctx, &dhcpd.Notification{
			Action:    "expiry",
			IPFamily:  ipVer,
			MAC:       mac,
			IP:        ip,
			Timestamp: epoch,
		})
		if err != nil {
			return err
		}
	}

	return nil
}

func (e *ExpirationHandler) expireUnackedLeases(ctx context.Context, tx *sql.Tx, ts time.Time) error {
	unackedRows, err := tx.QueryContext(ctx, fetchExpiredLeasesStmt, LeaseStateOffered, int(ts.Unix()))
	if err != nil {
		return fmt.Errorf("error querying for unacked expirations: %w", err)
	}

	err = e.expireLeases(ctx, tx, unackedRows, ts, false)
	if err != nil {
		return fmt.Errorf("error expiring unacked leases: %w", err)
	}

	_, err = tx.ExecContext(ctx, deleteExpiredLeasesStmt, LeaseStateOffered, int(ts.Unix()))
	if err != nil {
		return fmt.Errorf("error deleting expired unacked leases: %w", err)
	}

	return nil
}

func (e *ExpirationHandler) expireAckedLeases(ctx context.Context, tx *sql.Tx, ts time.Time) error {
	ackedRows, err := tx.QueryContext(ctx, fetchExpiredLeasesStmt, LeaseStateAcked, int(ts.Unix()))
	if err != nil {
		return fmt.Errorf("error querying for acked expirations: %w", err)
	}

	err = e.expireLeases(ctx, tx, ackedRows, ts, true)
	if err != nil {
		return fmt.Errorf("error expiring acked leases: %w", err)
	}

	_, err = tx.ExecContext(ctx, deleteExpiredLeasesStmt, LeaseStateAcked, int(ts.Unix()))
	if err != nil {
		return fmt.Errorf("error deleting expired acked leases: %w", err)
	}

	return nil
}

func (e *ExpirationHandler) expire(ctx context.Context, tx *sql.Tx, ts time.Time) error {
	// lets join errors instead of returning on first error to ensure if an error
	// interrupts one, we still attempt to expire the other
	var errs []error

	err := e.expireUnackedLeases(ctx, tx, ts)
	if err != nil {
		errs = append(errs, err)
	}

	err = e.expireAckedLeases(ctx, tx, ts)
	if err != nil {
		errs = append(errs, err)
	}

	if len(errs) > 0 {
		return errors.Join(errs...)
	}

	return nil
}
