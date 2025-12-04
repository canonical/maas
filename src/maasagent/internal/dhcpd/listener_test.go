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
	"context"
	"database/sql"
	"encoding/json"
	"errors"
	"io"
	"net"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	testdb "maas.io/core/src/maasagent/internal/testing/db"
)

// Lease is redefined here to avoid a circular import
type Lease struct {
	ID         int
	IP         net.IP
	MACAddress net.HardwareAddr
	DUID       string
	CreatedAt  int
	UpdatedAt  int
	Lifetime   int
	State      int
	RangeID    int
	NeedsSync  bool
}

// Expiration is redefined here to avoid a circular import
type Expiration struct {
	ID         int
	IP         net.IP
	MACAddress net.HardwareAddr
	DUID       string
	CreatedAt  int
}

func TestLoadExistingLease(t *testing.T) {
	db, err := testdb.WithTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in  []Lease
		out NotificationQueue
	}{
		"no existing entries": {},
		"existing leases": {
			in: []Lease{
				{
					ID:         1,
					IP:         net.ParseIP("10.0.0.1"),
					MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
					CreatedAt:  int(time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix()),
					UpdatedAt:  int(time.Date(2025, 10, 22, 1, 0, 0, 0, time.UTC).Unix()),
					Lifetime:   300,
					State:      1,
					RangeID:    1,
					NeedsSync:  true,
				},
				{
					ID:         2,
					IP:         net.ParseIP("10.0.0.2"),
					MACAddress: net.HardwareAddr{0x01, 0x11, 0x22, 0x33, 0x44, 0x55},
					CreatedAt:  int(time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix()),
					UpdatedAt:  int(time.Date(2025, 10, 22, 1, 0, 0, 0, time.UTC).Unix()),
					Lifetime:   300,
					State:      1,
					RangeID:    1,
					NeedsSync:  false,
				},
			},
			out: NotificationQueue{
				{
					Action:    "commit",
					IP:        "10.0.0.1",
					MAC:       "00:11:22:33:44:55",
					IPFamily:  "ipv4",
					Timestamp: time.Date(2025, 10, 22, 1, 0, 0, 0, time.UTC).Unix(),
					LeaseTime: 300,
				},
			},
		},
	}

	for tname, tc := range testcases {
		t.Run(tname, func(t *testing.T) {
			ctx := context.Background()

			deadline, ok := t.Deadline()
			if ok {
				var cancel context.CancelFunc

				ctx, cancel = context.WithDeadline(ctx, deadline)

				defer cancel()
			}

			tx, err := db.BeginTx(ctx, nil)
			require.NoError(t, err)

			t.Cleanup(func() {
				tx.Rollback()
			})

			err = testdb.SetupSchema(ctx, tx)
			require.NoError(t, err)

			for _, lease := range tc.in {
				_, err = tx.ExecContext(
					ctx,
					`
					INSERT INTO lease (
						id, ip, mac_address, duid, created_at, updated_at,
						lifetime, state, needs_sync, range_id
					) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);
					`,
					lease.ID,
					lease.IP.String(),
					lease.MACAddress.String(),
					lease.DUID,
					lease.CreatedAt,
					lease.UpdatedAt,
					lease.Lifetime,
					lease.State,
					lease.NeedsSync,
					lease.RangeID,
				)
				require.NoError(t, err)
			}

			nl := &NotificationListener{
				queue: NewNotificationQueue(),
			}

			err = nl.loadExistingLeases(ctx, tx)
			require.NoError(t, err)

			assert.Equal(t, tc.out, *nl.queue)
		})
	}
}

func TestLoadExistingExpirations(t *testing.T) {
	db, err := testdb.WithTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in  []Expiration
		out NotificationQueue
	}{
		"no existing entries": {},
		"existing expirations": {
			in: []Expiration{
				{
					ID:         1,
					IP:         net.ParseIP("10.0.0.1"),
					MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
					CreatedAt:  int(time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix()),
				},
				{
					ID:         2,
					IP:         net.ParseIP("10.0.0.2"),
					MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
					CreatedAt:  int(time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix()),
				},
			},
			out: NotificationQueue{
				{
					Action:    "expiry",
					IP:        "10.0.0.1",
					MAC:       "00:11:22:33:44:55",
					IPFamily:  "ipv4",
					Timestamp: time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix(),
				},
				{
					Action:    "expiry",
					IP:        "10.0.0.2",
					MAC:       "00:11:22:33:44:55",
					IPFamily:  "ipv4",
					Timestamp: time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix(),
				},
			},
		},
	}

	for tname, tc := range testcases {
		t.Run(tname, func(t *testing.T) {
			ctx := context.Background()

			deadline, ok := t.Deadline()
			if ok {
				var cancel context.CancelFunc

				ctx, cancel = context.WithDeadline(ctx, deadline)

				defer cancel()
			}

			tx, err := db.BeginTx(ctx, nil)
			require.NoError(t, err)

			t.Cleanup(func() {
				tx.Rollback()
			})

			err = testdb.SetupSchema(ctx, tx)
			require.NoError(t, err)

			for _, expiration := range tc.in {
				_, err = tx.ExecContext(
					ctx,
					`
					INSERT INTO expiration (
						id, ip, mac_address, duid, created_at
					) VALUES ($1, $2, $3, $4, $5);
					`,
					expiration.ID,
					expiration.IP.String(),
					expiration.MACAddress.String(),
					expiration.DUID,
					expiration.CreatedAt,
				)
				require.NoError(t, err)
			}

			nl := &NotificationListener{
				queue: NewNotificationQueue(),
			}

			err = nl.loadExistingExpirations(ctx, tx)
			require.NoError(t, err)

			assert.Equal(t, tc.out, *nl.queue)
		})
	}
}

func TestSyncWithDB(t *testing.T) {
	db, err := testdb.WithTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in struct {
			leases      []Lease
			expirations []Expiration
		}
		out struct {
			sent  []Notification
			queue NotificationQueue
		}
	}{
		"too new to flush": {
			in: struct {
				leases      []Lease
				expirations []Expiration
			}{
				leases: []Lease{
					{
						ID:         1,
						IP:         net.ParseIP("10.0.0.1"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
						CreatedAt:  int(time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(3025, 10, 22, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      1,
						RangeID:    1,
						NeedsSync:  true,
					},
				},
			},
			out: struct {
				sent  []Notification
				queue NotificationQueue
			}{
				queue: NotificationQueue{
					{
						Action:    "commit",
						IP:        "10.0.0.1",
						MAC:       "00:11:22:33:44:55",
						IPFamily:  "ipv4",
						LeaseTime: 300,
						Timestamp: time.Date(3025, 10, 22, 0, 0, 0, 0, time.UTC).Unix(),
					},
				},
			},
		},
		"send all": {
			in: struct {
				leases      []Lease
				expirations []Expiration
			}{
				leases: []Lease{
					{
						ID:         1,
						IP:         net.ParseIP("10.0.0.1"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
						CreatedAt:  int(time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      1,
						RangeID:    1,
						NeedsSync:  true,
					},
				},
				expirations: []Expiration{
					{
						ID:         2,
						IP:         net.ParseIP("10.0.0.2"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x00, 0x11, 0x00, 0x11},
						CreatedAt:  int(time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix()),
					},
				},
			},
			out: struct {
				sent  []Notification
				queue NotificationQueue
			}{
				sent: []Notification{
					{
						Action:    "commit",
						IP:        "10.0.0.1",
						IPFamily:  "ipv4",
						MAC:       "00:11:22:33:44:55",
						Timestamp: time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix(),
						LeaseTime: 300,
					}, {
						Action:    "expiry",
						IP:        "10.0.0.2",
						IPFamily:  "ipv4",
						MAC:       "00:11:00:11:00:11",
						Timestamp: time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix(),
					},
				},
				queue: NotificationQueue{},
			},
		},
		"send some": {
			in: struct {
				leases      []Lease
				expirations []Expiration
			}{
				leases: []Lease{
					{
						ID:         1,
						IP:         net.ParseIP("10.0.0.1"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
						CreatedAt:  int(time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(3025, 10, 22, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      1,
						RangeID:    1,
						NeedsSync:  true,
					},
				},
				expirations: []Expiration{
					{
						ID:         2,
						IP:         net.ParseIP("10.0.0.2"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x00, 0x11, 0x00, 0x11},
						CreatedAt:  int(time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix()),
					},
				},
			},
			out: struct {
				sent  []Notification
				queue NotificationQueue
			}{
				sent: []Notification{
					{
						Action:    "expiry",
						IP:        "10.0.0.2",
						IPFamily:  "ipv4",
						MAC:       "00:11:00:11:00:11",
						Timestamp: time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix(),
					},
				},
				queue: NotificationQueue{
					{
						Action:    "commit",
						IP:        "10.0.0.1",
						IPFamily:  "ipv4",
						MAC:       "00:11:22:33:44:55",
						Timestamp: time.Date(3025, 10, 22, 0, 0, 0, 0, time.UTC).Unix(),
						LeaseTime: 300,
					},
				},
			},
		},
	}

	for tname, tc := range testcases {
		t.Run(tname, func(t *testing.T) {
			ctx := context.Background()

			deadline, ok := t.Deadline()
			if ok {
				var cancel context.CancelFunc

				ctx, cancel = context.WithDeadline(ctx, deadline)

				defer cancel()
			}

			tx, err := db.BeginTx(ctx, nil)
			require.NoError(t, err)

			t.Cleanup(func() {
				tx.Rollback()
			})

			err = testdb.SetupSchema(ctx, tx)
			require.NoError(t, err)

			for _, lease := range tc.in.leases {
				_, err = tx.ExecContext(
					ctx,
					`
					INSERT INTO lease (
						id, ip, mac_address, duid, created_at, updated_at,
						lifetime, state, needs_sync, range_id
					) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10);
					`,
					lease.ID,
					lease.IP.String(),
					lease.MACAddress.String(),
					lease.DUID,
					lease.CreatedAt,
					lease.UpdatedAt,
					lease.Lifetime,
					lease.State,
					lease.NeedsSync,
					lease.RangeID,
				)
				require.NoError(t, err)
			}

			for _, expiration := range tc.in.expirations {
				_, err = tx.ExecContext(
					ctx,
					`
					INSERT INTO expiration (
						id, ip, mac_address, duid, created_at
					) VALUES ($1, $2, $3, $4, $5);
					`,
					expiration.ID,
					expiration.IP.String(),
					expiration.MACAddress.String(),
					expiration.DUID,
					expiration.CreatedAt,
				)
				require.NoError(t, err)
			}

			rConn, wConn := net.Pipe()

			var sent []Notification

			ready := make(chan error)

			go func() {
				defer close(ready)

				var n []Notification

				for {
					err = json.NewDecoder(rConn).Decode(&n)
					if err != nil {
						if !errors.Is(err, io.EOF) && !errors.Is(err, io.ErrClosedPipe) {
							ready <- err
						}

						return
					}

					sent = append(sent, n...)
				}
			}()

			nl := NewNotificationListener(rConn, func(ctx context.Context, n []*Notification) error {
				return json.NewEncoder(wConn).Encode(n)
			})

			// use loadExisting to fetch input from DB
			err = nl.loadExistingLeases(ctx, tx)
			require.NoError(t, err)

			err = nl.loadExistingExpirations(ctx, tx)
			require.NoError(t, err)

			err = nl.syncWithDB(ctx, tx)
			require.NoError(t, err)

			assert.Equal(t, tc.out.queue, *nl.queue)

			err = wConn.Close()
			assert.NoError(t, err)

			err = rConn.Close()
			assert.NoError(t, err)

			err = <-ready
			require.NoError(t, err)

			assert.Equal(t, tc.out.sent, sent)

			for _, s := range sent {
				if s.Action == "commit" {
					var needsSync bool

					row := tx.QueryRowContext(
						ctx,
						"SELECT needs_sync FROM lease WHERE ip=$1 AND mac_address=$2;",
						s.IP,
						s.MAC,
					)

					err = row.Scan(&needsSync)
					require.NoError(t, err)

					assert.False(t, needsSync)
				} else {
					var id int

					row := tx.QueryRowContext(
						ctx,
						"SELECT id FROM expiration WHERE ip=$1 AND mac_address=$2 AND created_at=$3;",
						s.IP,
						s.MAC,
						s.Timestamp,
					)

					err = row.Scan(&id)
					assert.ErrorIs(t, err, sql.ErrNoRows)
				}
			}
		})
	}
}
