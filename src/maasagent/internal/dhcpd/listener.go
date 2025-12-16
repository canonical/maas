// Copyright (c) 2023-2024 Canonical Ltd
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

package dhcpd

import (
	"container/heap"
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"net"
	"os"
	"sync"
	"time"

	"github.com/canonical/microcluster/v2/state"
	"github.com/rs/zerolog/log"
)

const (
	fetchExistingLeasesStmt      = "SELECT ip, mac_address, duid, updated_at, lifetime FROM lease WHERE needs_sync=true AND state=1;"
	fetchExistingExpirationsStmt = "SELECT ip, mac_address, duid, created_at FROM expiration;"
	setLeaseSyncedStmt           = "UPDATE lease SET needs_sync=false WHERE ip=$1 AND mac_address=$2;"
	// use created_at in the event the same IP and MAC expire multiple times before sync
	deleteExpirationStmt = "DELETE FROM expiration WHERE ip=$1 AND mac_address=$2 AND created_at=$3;"
)

type Notification struct {
	Action    string `json:"action"`
	IPFamily  string `json:"ip_family"`
	Hostname  string `json:"hostname"`
	MAC       string `json:"mac"`
	IP        string `json:"ip"`
	Timestamp int64  `json:"timestamp"`
	LeaseTime int64  `json:"lease_time"`
}

type NotificationListener struct {
	conn         net.Conn
	clusterState state.State
	queue        *NotificationQueue
	buf          chan *Notification
	pool         *sync.Pool
	fn           func(context.Context, []*Notification) error
	interval     time.Duration
	stateLock    sync.RWMutex
}

type NotificationListenerOption func(*NotificationListener)

func NewNotificationListener(conn net.Conn, fn func(context.Context, []*Notification) error,
	options ...NotificationListenerOption) *NotificationListener {
	pool := &sync.Pool{
		New: func() any {
			s := make([]*Notification, 0, 1024)
			return &s
		},
	}

	l := &NotificationListener{
		pool:  pool,
		conn:  conn,
		buf:   make(chan *Notification, 1024),
		queue: NewNotificationQueue(),
		fn:    fn,
	}

	for _, opt := range options {
		opt(l)
	}

	return l
}

// WithInterval allows setting custom interval for the buffer-flush timer.
// (default: 5*time.Second)
func WithInterval(d time.Duration) NotificationListenerOption {
	return func(l *NotificationListener) { l.interval = d }
}

func (l *NotificationListener) Listen(ctx context.Context) {
	internalDHCPEnabled := os.Getenv("MAAS_DHCP_INTERNAL") == "1"

	if internalDHCPEnabled {
		err := l.loadExisting(ctx)
		if err != nil {
			log.Err(err).Send()
		}
	}

	go l.read(ctx)

	interval := 5 * time.Second
	if l.interval > 0 {
		interval = l.interval
	}

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case notification := <-l.buf:
			heap.Push(l.queue, notification)
		case <-ticker.C:
			if os.Getenv("MAAS_INTERNAL_DHCP") != "1" {
				err := l.syncWithoutDB(ctx)
				if err != nil {
					log.Err(err).Send()
				}

				continue
			}

			func() {
				l.stateLock.RLock()
				defer l.stateLock.RUnlock()

				if l.clusterState == nil {
					log.Warn().Msg("cluster state not initialized for lease sync")
					return
				}

				err := l.clusterState.Database().Transaction(ctx, l.syncWithDB)
				if err != nil {
					log.Err(err).Send()
				}
			}()
		}
	}
}

func (l *NotificationListener) EnqueueLeaseNotification(ctx context.Context, n *Notification) error {
	select {
	case <-ctx.Done():
		if err := ctx.Err(); err != nil {
			return err
		}
	case l.buf <- n:
	}

	return nil
}

func (l *NotificationListener) SetClusterState(s state.State) {
	l.stateLock.Lock()
	defer l.stateLock.Unlock()

	l.clusterState = s
}

func (l *NotificationListener) syncWithoutDB(ctx context.Context) error {
	batchPtr, ok := l.pool.Get().(*[]*Notification)
	if !ok {
		panic("wrong type. should be *[]*Notification")
	}

	batch := *batchPtr
	batch = batch[:0]

	now := time.Now().UTC().Unix()

	for l.queue.Len() > 0 {
		notification, ok := heap.Pop(l.queue).(*Notification)
		if !ok {
			panic("wrong type. should be *Notification")
		}

		if now-notification.Timestamp > 1 {
			batch = append(batch, notification)
			continue
		}

		l.queue.Push(notification)

		break
	}

	if len(batch) == 0 {
		l.pool.Put(&batch)
		return nil
	}

	copied := make([]*Notification, len(batch))
	copy(copied, batch)
	l.pool.Put(&batch)

	err := l.fn(ctx, copied)
	if err != nil { // failed to send, push leases back
		for _, n := range copied {
			heap.Push(l.queue, n)
		}
	}

	return err
}

func (l *NotificationListener) syncWithDB(ctx context.Context, tx *sql.Tx) error {
	batchPtr, ok := l.pool.Get().(*[]*Notification)
	if !ok {
		panic("wrong type. should be *[]*Notification")
	}

	batch := *batchPtr
	batch = batch[:0]

	now := time.Now().UTC().Unix()

	var (
		errs   []error
		copied []*Notification
	)

	defer func() {
		if len(errs) > 0 {
			for _, n := range copied {
				heap.Push(l.queue, n)
			}
		}
	}()

	for l.queue.Len() > 0 {
		notification, ok := heap.Pop(l.queue).(*Notification)
		if !ok {
			panic("wrong type. should be *Notification")
		}

		if now-notification.Timestamp > 1 {
			batch = append(batch, notification)

			switch notification.Action {
			case "commit":
				_, err := tx.ExecContext(ctx, setLeaseSyncedStmt, notification.IP, notification.MAC)
				if err != nil {
					errs = append(errs, err)
				}
			case "expiry":
				_, err := tx.ExecContext(ctx, deleteExpirationStmt, notification.IP, notification.MAC, notification.Timestamp)
				if err != nil {
					errs = append(errs, err)
				}
			}

			continue
		}

		l.queue.Push(notification)

		break
	}

	if len(batch) == 0 {
		l.pool.Put(&batch)
		return nil
	}

	copied = make([]*Notification, len(batch))
	copy(copied, batch)
	l.pool.Put(&batch)

	if len(errs) > 0 {
		return errors.Join(errs...)
	}

	err := l.fn(ctx, copied)
	if err != nil {
		errs = append(errs, err) // still append to errs for deferred check
	}

	return err // should be the only error occurred if execution reached here
}

func ipStringAddressFamily(ipStr string) string {
	ip := net.ParseIP(ipStr)
	if ip.To4() != nil {
		return "ipv4"
	}

	return "ipv6"
}

func (l *NotificationListener) loadExistingLeases(ctx context.Context, tx *sql.Tx) error {
	leaseRows, err := tx.QueryContext(ctx, fetchExistingLeasesStmt)
	if err != nil {
		return err
	}

	defer func() {
		cErr := leaseRows.Close()
		if err == nil && cErr != nil {
			err = cErr
		}
	}()

	for leaseRows.Next() {
		var (
			ipStr, macStr, duid string
			updatedAt, lifetime int64
		)

		err = leaseRows.Scan(
			&ipStr,
			&macStr,
			&duid,
			&updatedAt,
			&lifetime,
		)
		if err != nil {
			return err
		}

		// TODO report DUID
		heap.Push(l.queue, &Notification{
			Action:    "commit",
			IPFamily:  ipStringAddressFamily(ipStr),
			MAC:       macStr,
			IP:        ipStr,
			Timestamp: updatedAt,
			LeaseTime: lifetime,
		})
	}

	return leaseRows.Err()
}

func (l *NotificationListener) loadExistingExpirations(ctx context.Context, tx *sql.Tx) error {
	expirationRows, err := tx.QueryContext(ctx, fetchExistingExpirationsStmt)
	if err != nil {
		return err
	}

	defer func() {
		cErr := expirationRows.Close()
		if err == nil && cErr != nil {
			err = cErr
		}
	}()

	for expirationRows.Next() {
		var (
			ipStr, macStr, duid string
			createdAt           int64
		)

		err = expirationRows.Scan(
			&ipStr,
			&macStr,
			&duid,
			&createdAt,
		)
		if err != nil {
			return err
		}

		heap.Push(l.queue, &Notification{
			Action:    "expiry",
			IPFamily:  ipStringAddressFamily(ipStr),
			MAC:       macStr,
			IP:        ipStr,
			Timestamp: createdAt,
		})
	}

	return nil
}

func (l *NotificationListener) loadExisting(ctx context.Context) error {
	l.stateLock.RLock()
	defer l.stateLock.RUnlock()

	return l.clusterState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
		err := l.loadExistingLeases(ctx, tx)
		if err != nil {
			return err
		}

		return l.loadExistingExpirations(ctx, tx)
	})
}

func (l *NotificationListener) read(ctx context.Context) {
	decoder := json.NewDecoder(l.conn)

	for {
		select {
		case <-ctx.Done():
			if err := l.conn.Close(); err != nil {
				log.Warn().Err(err).Send()
			}

			return
		default:
			var notification Notification

			err := decoder.Decode(&notification)
			if err != nil {
				log.Warn().Err(err).Msg("Malformed DHCP notification")
				// reset the decoder
				decoder = json.NewDecoder(l.conn)

				continue
			}

			l.buf <- &notification
		}
	}
}
