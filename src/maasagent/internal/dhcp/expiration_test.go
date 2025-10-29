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
	"encoding/binary"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	dqlite "github.com/canonical/go-dqlite/v2/app"
	"github.com/canonical/lxd/lxd/db/schema"
	"github.com/canonical/microcluster/v2/microcluster"
	"github.com/canonical/microcluster/v2/state"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"maas.io/core/src/maasagent/internal/cluster"
)

func testExpireLeases(t *testing.T, leaseState LeaseState, oppositeState LeaseState, expireFn func(context.Context, *sql.Tx, time.Time) error) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in struct {
			leases []Lease
			ts     time.Time
		}
		out []Expiration
		err error
	}{
		"no expired leases": {
			in: struct {
				leases []Lease
				ts     time.Time
			}{
				leases: []Lease{
					{
						ID:         1,
						IP:         net.ParseIP("10.0.0.1"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      leaseState,
						RangeID:    1,
						NeedsSync:  true,
					},
				},
				ts: time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC),
			},
		},
		"1 expired lease": {
			in: struct {
				leases []Lease
				ts     time.Time
			}{
				leases: []Lease{
					{
						ID:         1,
						IP:         net.ParseIP("10.0.0.1"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      leaseState,
						RangeID:    1,
						NeedsSync:  true,
					},
				},
				ts: time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC),
			},
			out: []Expiration{
				{
					ID:         1,
					IP:         net.ParseIP("10.0.0.1"),
					MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
					CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC).Unix()),
				},
			},
		},
		"1 expired 1 valid lease": {
			in: struct {
				leases []Lease
				ts     time.Time
			}{
				leases: []Lease{
					{
						ID:         1,
						IP:         net.ParseIP("10.0.0.1"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      leaseState,
						RangeID:    1,
						NeedsSync:  true,
					},
					{
						ID:         2,
						IP:         net.ParseIP("10.0.0.2"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x66},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 8, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      leaseState,
						RangeID:    1,
						NeedsSync:  true,
					},
				},
				ts: time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC),
			},
			out: []Expiration{
				{
					ID:         1,
					IP:         net.ParseIP("10.0.0.1"),
					MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
					CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC).Unix()),
				},
			},
		},
		"multiple expired leases": {
			in: struct {
				leases []Lease
				ts     time.Time
			}{
				leases: []Lease{
					{
						ID:         1,
						IP:         net.ParseIP("10.0.0.1"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      leaseState,
						RangeID:    1,
						NeedsSync:  true,
					},
					{
						ID:         2,
						IP:         net.ParseIP("10.0.0.2"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x66},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 8, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      leaseState,
						RangeID:    1,
						NeedsSync:  true,
					},
				},
				ts: time.Date(2025, 10, 8, 0, 0, 12, 0, time.UTC),
			},
			out: []Expiration{
				{
					ID:         1,
					IP:         net.ParseIP("10.0.0.1"),
					MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
					CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 12, 0, time.UTC).Unix()),
				},
				{
					ID:         2,
					IP:         net.ParseIP("10.0.0.2"),
					MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x66},
					CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 12, 0, time.UTC).Unix()),
				},
			},
		},
		"all leases in a different state": {
			in: struct {
				leases []Lease
				ts     time.Time
			}{
				leases: []Lease{
					{
						ID:         1,
						IP:         net.ParseIP("10.0.0.1"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      oppositeState,
						RangeID:    1,
						NeedsSync:  true,
					},
					{
						ID:         2,
						IP:         net.ParseIP("10.0.0.2"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x66},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      oppositeState,
						RangeID:    1,
						NeedsSync:  true,
					},
				},
				ts: time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC),
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

			err = setupSchema(ctx, tx)
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

			err = expireFn(ctx, tx, tc.in.ts)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			rows, err := tx.QueryContext(ctx, "SELECT * FROM expiration;")
			require.NoError(t, err)

			var expirations []Expiration

			for rows.Next() {
				var (
					expiration    Expiration
					ipStr, macStr string
				)

				err = rows.Scan(
					&expiration.ID,
					&ipStr,
					&macStr,
					&expiration.DUID,
					&expiration.CreatedAt,
				)
				require.NoError(t, err)

				expiration.IP = net.ParseIP(ipStr)
				expiration.MACAddress, _ = net.ParseMAC(macStr)

				expirations = append(expirations, expiration)
			}

			assert.Equal(t, expirations, tc.out)
		})
	}
}

func TestExpireUnackedLeases(t *testing.T) {
	eh := &ExpirationHandler{}

	testExpireLeases(t, LeaseStateOffered, LeaseStateAcked, eh.expireUnackedLeases)
}

func TestExpireAckedLeases(t *testing.T) {
	eh := &ExpirationHandler{}

	testExpireLeases(t, LeaseStateAcked, LeaseStateOffered, eh.expireAckedLeases)
}

func TestExpire(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in struct {
			leases []Lease
			ts     time.Time
		}
		out []Expiration
		err error
	}{
		"no expired leases": {
			in: struct {
				leases []Lease
				ts     time.Time
			}{
				leases: []Lease{
					{
						ID:         1,
						IP:         net.ParseIP("10.0.0.1"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      LeaseStateAcked,
						RangeID:    1,
						NeedsSync:  true,
					},
				},
				ts: time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC),
			},
		},
		"expired offered": {
			in: struct {
				leases []Lease
				ts     time.Time
			}{
				leases: []Lease{
					{
						ID:         1,
						IP:         net.ParseIP("10.0.0.1"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      LeaseStateOffered,
						RangeID:    1,
						NeedsSync:  true,
					},
				},
				ts: time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC),
			},
			out: []Expiration{
				{
					ID:         1,
					IP:         net.ParseIP("10.0.0.1"),
					MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
					CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC).Unix()),
				},
			},
		},
		"expired acked": {
			in: struct {
				leases []Lease
				ts     time.Time
			}{
				leases: []Lease{
					{
						ID:         1,
						IP:         net.ParseIP("10.0.0.1"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      LeaseStateAcked,
						RangeID:    1,
						NeedsSync:  true,
					},
				},
				ts: time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC),
			},
			out: []Expiration{
				{
					ID:         1,
					IP:         net.ParseIP("10.0.0.1"),
					MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
					CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC).Unix()),
				},
			},
		},
		"both types expired": {
			in: struct {
				leases []Lease
				ts     time.Time
			}{
				leases: []Lease{
					{
						ID:         1,
						IP:         net.ParseIP("10.0.0.1"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      LeaseStateOffered,
						RangeID:    1,
						NeedsSync:  true,
					},
					{
						ID:         2,
						IP:         net.ParseIP("10.0.0.2"),
						MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x66},
						CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						UpdatedAt:  int(time.Date(2025, 10, 8, 0, 0, 0, 0, time.UTC).Unix()),
						Lifetime:   300,
						State:      LeaseStateAcked,
						RangeID:    1,
						NeedsSync:  true,
					},
				},
				ts: time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC),
			},
			out: []Expiration{
				{
					ID:         1,
					IP:         net.ParseIP("10.0.0.1"),
					MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55},
					CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC).Unix()),
				},
				{
					ID:         2,
					IP:         net.ParseIP("10.0.0.2"),
					MACAddress: net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x66},
					CreatedAt:  int(time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC).Unix()),
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

			err = setupSchema(ctx, tx)
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

			eh := &ExpirationHandler{}

			err = eh.expire(ctx, tx, tc.in.ts)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			rows, err := tx.QueryContext(ctx, "SELECT * FROM expiration;")
			require.NoError(t, err)

			var expirations []Expiration

			for rows.Next() {
				var (
					expiration    Expiration
					ipStr, macStr string
				)

				err = rows.Scan(
					&expiration.ID,
					&ipStr,
					&macStr,
					&expiration.DUID,
					&expiration.CreatedAt,
				)
				require.NoError(t, err)

				expiration.IP = net.ParseIP(ipStr)
				expiration.MACAddress, _ = net.ParseMAC(macStr)

				expirations = append(expirations, expiration)
			}

			assert.Equal(t, expirations, tc.out)
		})
	}
}

func ipv4ToUint32(ip net.IP) uint32 {
	return binary.BigEndian.Uint32(ip.To4())
}

func uint32ToIPv4(val uint32) net.IP {
	ip := make(net.IP, 4)
	binary.BigEndian.PutUint32(ip, val)

	return ip
}

func benchmarkExpire(b *testing.B, count int) {
	ctx := b.Context()

	db, err := withTestDatabase(b)
	require.NoError(b, err)

	tx, err := db.BeginTx(ctx, nil)
	require.NoError(b, err)

	b.Cleanup(func() {
		tx.Rollback()
	})

	err = setupSchema(ctx, tx)
	require.NoError(b, err)

	baseIPInt := ipv4ToUint32(net.ParseIP("10.0.0.1"))
	mac := net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55}
	ts := time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC)

	eh := &ExpirationHandler{}

	for b.Loop() {
		_, err = tx.ExecContext(ctx, "DELETE FROM expiration;") // cleanup expirations
		require.NoError(b, err)

		for i := 0; i < count; i++ {
			ip := uint32ToIPv4(baseIPInt + uint32(i))

			_, err = tx.ExecContext(ctx, `INSERT INTO lease (
					id,
					ip,
					mac_address,
					duid,
					created_at,
					updated_at,
					lifetime,
					state,
					needs_sync,
					range_id
				) VALUES (NULL, $1, $2, $3, $4, $5, $6, $7, $8, $9);`,
				ip.String(),
				mac.String(),
				"",
				int(ts.Unix()),
				int(ts.Unix()),
				300,
				LeaseStateAcked,
				false,
				1,
			)
		}

		require.NoError(b, err)

		err = eh.expire(ctx, tx, ts.Add(3*time.Second))
		require.NoError(b, err)
	}
}

func BenchmarkExpire_10(b *testing.B) {
	benchmarkExpire(b, 10)
}

func BenchmarkExpire_100(b *testing.B) {
	benchmarkExpire(b, 100)
}

func BenchmarkExpire_1000(b *testing.B) {
	benchmarkExpire(b, 1000)
}

func benchmarkExpireMicrocluster(b *testing.B, count int) {
	ctx := b.Context()

	dataPath := b.TempDir()
	dataDir := filepath.Join(dataPath, "microcluster")
	app, appErr := microcluster.App(microcluster.Args{
		StateDir: dataDir,
	})
	require.NoError(b, appErr)

	b.Cleanup(func() {
		os.RemoveAll(dataDir)
	})

	clusterName := strings.ReplaceAll(strings.ReplaceAll(b.Name(), "/", "-"), "_", "-")

	done := make(chan struct{})
	waitChan := make(chan struct{})
	txChan := make(chan *sql.Tx)

	eh := &ExpirationHandler{}

	go app.Start(ctx, microcluster.DaemonArgs{
		Version:          "UNKNOWN",
		Debug:            false,
		ExtensionsSchema: []schema.Update{cluster.SchemaAppendDHCP},
		Hooks: &state.Hooks{
			OnStart: func(ctx context.Context, s state.State) error {
				defer close(done)

				err := app.NewCluster(ctx, clusterName, "127.0.0.1:5858", nil)
				require.NoError(b, err)

				err = s.Database().IsOpen(ctx)
				require.NoError(b, err)

				err = s.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
					_, err = tx.ExecContext(ctx, `
						INSERT INTO vlan (id, vid) VALUES (1, 0);
						INSERT INTO subnet (id, cidr, address_family, vlan_id) VALUES (1, '10.0.0.0/16', 4, 1);
						INSERT INTO ip_range (id, start_ip, end_ip, size, fully_allocated, dynamic, subnet_id) VALUES (
							1, '10.0.0.1', '10.0.100.0', 25500, false, true, 1
						);
					`)
					require.NoError(b, err)

					txChan <- tx

					<-waitChan

					return nil
				})
				require.NoError(b, err)

				return nil
			},
		},
	})

	tx := <-txChan

	baseIPInt := ipv4ToUint32(net.ParseIP("10.0.0.1"))
	mac := net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55}
	ts := time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC)

	for b.Loop() {
		_, err := tx.ExecContext(ctx, "DELETE FROM expiration;") // cleanup expirations
		require.NoError(b, err)

		for i := 0; i < count; i++ {
			ip := uint32ToIPv4(baseIPInt + uint32(i))

			_, err = tx.ExecContext(ctx, `INSERT INTO lease (
					id,
					ip,
					mac_address,
					duid,
					created_at,
					updated_at,
					lifetime,
					state,
					needs_sync,
					range_id
				) VALUES (NULL, $1, $2, $3, $4, $5, $6, $7, $8, $9);`,
				ip.String(),
				mac.String(),
				"",
				int(ts.Unix()),
				int(ts.Unix()),
				300,
				LeaseStateAcked,
				false,
				1,
			)
			require.NoError(b, err)
		}

		err = eh.expire(ctx, tx, ts.Add(3*time.Second))
		require.NoError(b, err)
	}

	close(waitChan)

	<-done
}

func BenchmarkExpireMicrocluster_10(b *testing.B) {
	benchmarkExpireMicrocluster(b, 10)
}

func BenchmarkExpireMicrocluster_100(b *testing.B) {
	benchmarkExpireMicrocluster(b, 100)
}

func BenchmarkExpireMicrocluster_1000(b *testing.B) {
	benchmarkExpireMicrocluster(b, 1000)
}

func benchmarkExpireDQLite(b *testing.B, count int) {
	ctx := b.Context()

	app, err := dqlite.New(b.TempDir(), dqlite.WithAddress(fmt.Sprintf("127.0.0.1:%d", 9900+count)))
	require.NoError(b, err)

	db, err := app.Open(ctx, b.Name())
	require.NoError(b, err)

	tx, err := db.BeginTx(ctx, nil)
	require.NoError(b, err)

	b.Cleanup(func() {
		tx.Rollback()
	})

	err = setupSchema(ctx, tx)
	require.NoError(b, err)

	baseIPInt := ipv4ToUint32(net.ParseIP("10.0.0.1"))
	mac := net.HardwareAddr{0x00, 0x11, 0x22, 0x33, 0x44, 0x55}
	ts := time.Date(2025, 10, 8, 0, 0, 3, 0, time.UTC)

	eh := &ExpirationHandler{}

	_, err = tx.ExecContext(ctx, `
		INSERT INTO vlan (id, vid) VALUES (1, 0);
		INSERT INTO subnet (id, cidr, address_family, vlan_id) VALUES (1, '10.0.0.0/16', 4, 1);
		INSERT INTO ip_range (id, start_ip, end_ip, size, fully_allocated, dynamic, subnet_id) VALUES (
			1, '10.0.0.1', '10.0.100.0', 25500, false, true, 1
		);
	`)
	require.NoError(b, err)

	for b.Loop() {
		_, err = tx.ExecContext(ctx, "DELETE FROM expiration;") // cleanup expirations
		require.NoError(b, err)

		for i := 0; i < count; i++ {
			ip := uint32ToIPv4(baseIPInt + uint32(i))

			_, err = tx.ExecContext(ctx, `INSERT INTO lease (
					id,
					ip,
					mac_address,
					duid,
					created_at,
					updated_at,
					lifetime,
					state,
					needs_sync,
					range_id
				) VALUES (NULL, $1, $2, $3, $4, $5, $6, $7, $8, $9);`,
				ip.String(),
				mac.String(),
				"",
				int(ts.Unix()),
				int(ts.Unix()),
				300,
				LeaseStateAcked,
				false,
				1,
			)
		}

		require.NoError(b, err)

		err = eh.expire(ctx, tx, ts.Add(3*time.Second))
		require.NoError(b, err)
	}
}

func BenchmarkExpireDQLite_10(b *testing.B) {
	benchmarkExpireDQLite(b, 10)
}

func BenchmarkExpireDQLite_100(b *testing.B) {
	benchmarkExpireDQLite(b, 100)
}

func BenchmarkExpireDQLite_1000(b *testing.B) {
	benchmarkExpireDQLite(b, 1000)
}
