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
	"net"
	"os"
	"testing"

	_ "github.com/mattn/go-sqlite3"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"maas.io/core/src/maasagent/internal/cluster"
)

func setupSchema(ctx context.Context, tx *sql.Tx) error {
	return cluster.SchemaAppendDHCP(ctx, tx)
}

func withTestDatabase(t *testing.T) (*sql.DB, error) {
	f, err := os.CreateTemp(t.TempDir(), t.Name()+".db")
	if err != nil {
		return nil, err
	}

	if err = f.Close(); err != nil {
		return nil, err
	}

	db, err := sql.Open("sqlite3", f.Name())
	if err != nil {
		return nil, err
	}

	return db, nil
}

func TestVlanScanRow(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in  string
		out Vlan
		err error
	}{
		"all values set": {
			in: "INSERT INTO vlan VALUES (NULL, 0, 2);",
			out: Vlan{
				ID:            1,
				VID:           0,
				RelayedVlanID: 2,
			},
		},
		"no relayed vlan": {
			in: "INSERT INTO vlan(vid) VALUES (0);",
			out: Vlan{
				ID:  1,
				VID: 0,
			},
		},
		"missing": {
			err: sql.ErrNoRows,
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

			_, err = tx.ExecContext(ctx, tc.in)
			require.NoError(t, err)

			row := tx.QueryRowContext(ctx, "SELECT * FROM vlan WHERE id = $1;", tc.out.ID)
			vlan := &Vlan{}

			err = vlan.ScanRow(row)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, *vlan, tc.out)
		})
	}
}

func TestVlanLoadOptions(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in  string
		out map[uint16]string
		err error
	}{
		"one option": {
			in: `
			INSERT INTO vlan VALUES (NULL, 0, NULL);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 1);
			`,
			out: map[uint16]string{
				26: "1500",
			},
		},
		"multiple options": {
			in: `
			INSERT INTO vlan VALUES (NULL, 0, NULL);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 1);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("hostname", 12, "test", 1);
			`,
			out: map[uint16]string{
				26: "1500",
				12: "test",
			},
		},
		"no options": {
			in:  "INSERT INTO vlan VALUES (NULL, 0, NULL);",
			out: map[uint16]string{},
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

			_, err = tx.ExecContext(ctx, tc.in)
			require.NoError(t, err)

			row := tx.QueryRowContext(ctx, "SELECT * FROM vlan WHERE id = 1;")
			vlan := &Vlan{}

			err = vlan.ScanRow(row)
			require.NoError(t, err)

			err = vlan.LoadOptions(ctx, tx)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, vlan.Options, tc.out)
		})
	}
}

func TestInterfaceScanRow(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in  string
		out Interface
		err error
	}{
		"all values set": {
			in: "INSERT INTO interface VALUES (NULL, \"host\", 0, 2);",
			out: Interface{
				ID:       1,
				Hostname: "host",
				Index:    0,
				VlanID:   2,
			},
		},
		"missing": {
			err: sql.ErrNoRows,
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

			_, err = tx.ExecContext(ctx, tc.in)
			require.NoError(t, err)

			row := tx.QueryRowContext(ctx, "SELECT * FROM interface WHERE id = $1;", tc.out.ID)
			iface := &Interface{}

			err = iface.ScanRow(row)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, *iface, tc.out)
		})
	}
}

func TestSubnetScanRow(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	_, testCidr, _ := net.ParseCIDR("10.0.0.0/24")
	testcases := map[string]struct {
		in  string
		out Subnet
		err error
	}{
		"all values set": {
			in: "INSERT INTO subnet VALUES (NULL, \"10.0.0.0/24\", 4, 1);",
			out: Subnet{
				ID:            1,
				CIDR:          testCidr,
				AddressFamily: 4,
				VlanID:        1,
			},
		},
		"missing": {
			err: sql.ErrNoRows,
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

			_, err = tx.ExecContext(ctx, tc.in)
			require.NoError(t, err)

			row := tx.QueryRowContext(ctx, "SELECT * FROM subnet WHERE id = $1;", tc.out.ID)
			subnet := &Subnet{}

			err = subnet.ScanRow(row)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, *subnet, tc.out)
		})
	}
}

func TestSubnetLoadOptions(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in  string
		out map[uint16]string
		err error
	}{
		"one option": {
			in: `
			INSERT INTO subnet VALUES (NULL, "10.0.0.0/24", 4, 5);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("mtu", 26, "1500", 1);
			`,
			out: map[uint16]string{
				26: "1500",
			},
		},
		"multiple options": {
			in: `
			INSERT INTO subnet VALUES (NULL, "10.0.0.0/24", 4, 4);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("mtu", 26, "1500", 1);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("hostname", 12, "test", 1);
			`,
			out: map[uint16]string{
				26: "1500",
				12: "test",
			},
		},
		"no options": {
			in:  "INSERT INTO subnet VALUES (NULL, \"10.0.0.0/24\", 4, 2);",
			out: map[uint16]string{},
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

			_, err = tx.ExecContext(ctx, tc.in)
			require.NoError(t, err)

			row := tx.QueryRowContext(ctx, "SELECT * FROM subnet WHERE id = 1;")
			subnet := &Subnet{}

			err = subnet.ScanRow(row)
			require.NoError(t, err)

			err = subnet.LoadOptions(ctx, tx)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, subnet.Options, tc.out)
		})
	}
}

func TestIPRangeScanRow(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in  string
		out IPRange
		err error
	}{
		"all values set": {
			in: "INSERT INTO ip_range VALUES (NULL, \"10.0.0.1\", \"10.0.0.21\", 20, false, true, 3);",
			out: IPRange{
				ID:             1,
				StartIP:        net.ParseIP("10.0.0.1"),
				EndIP:          net.ParseIP("10.0.0.21"),
				Size:           20,
				FullyAllocated: false,
				Dynamic:        true,
				SubnetID:       3,
			},
		},
		"missing": {
			err: sql.ErrNoRows,
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

			_, err = tx.ExecContext(ctx, tc.in)
			require.NoError(t, err)

			row := tx.QueryRowContext(ctx, "SELECT * FROM ip_range WHERE id = $1;", tc.out.ID)
			iprange := &IPRange{}

			err = iprange.ScanRow(row)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, *iprange, tc.out)
		})
	}
}

func TestIPRangeLoadOptions(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in  string
		out map[uint16]string
		err error
	}{
		"one option": {
			in: `
			INSERT INTO ip_range VALUES (NULL, "10.0.0.1", "10.0.0.21", 20, false, true, 5);
			INSERT INTO dhcp_option(label, number, value, range_id) VALUES ("mtu", 26, "1500", 1);
			`,
			out: map[uint16]string{
				26: "1500",
			},
		},
		"multiple options": {
			in: `
			INSERT INTO ip_range VALUES (NULL, "10.0.0.1", "10.0.0.21", 20, false, true, 5);
			INSERT INTO dhcp_option(label, number, value, range_id) VALUES ("mtu", 26, "1500", 1);
			INSERT INTO dhcp_option(label, number, value, range_id) VALUES ("hostname", 12, "test", 1);
			`,
			out: map[uint16]string{
				26: "1500",
				12: "test",
			},
		},
		"no options": {
			in:  "INSERT INTO ip_range VALUES (NULL, \"10.0.0.1\", \"10.0.0.21\", 20, false, true, 5);",
			out: map[uint16]string{},
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

			_, err = tx.ExecContext(ctx, tc.in)
			require.NoError(t, err)

			row := tx.QueryRowContext(ctx, "SELECT * FROM ip_range WHERE id = 1;")
			iprange := &IPRange{}

			err = iprange.ScanRow(row)
			require.NoError(t, err)

			err = iprange.LoadOptions(ctx, tx)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, iprange.Options, tc.out)
		})
	}
}

func TestHostReservationScanRow(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testMac, _ := net.ParseMAC("ab:cd:ef:00:11:22")
	testcases := map[string]struct {
		in  string
		out HostReservation
		err error
	}{
		"all values set": {
			in: "INSERT INTO host_reservation VALUES (NULL, \"10.0.0.1\", \"ab:cd:ef:00:11:22\", 3);",
			out: HostReservation{
				ID:         1,
				IPAddress:  net.ParseIP("10.0.0.1"),
				MACAddress: testMac,
				RangeID:    3,
			},
		},
		"missing": {
			err: sql.ErrNoRows,
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

			_, err = tx.ExecContext(ctx, tc.in)
			require.NoError(t, err)

			row := tx.QueryRowContext(ctx, "SELECT * FROM host_reservation WHERE id = $1;", tc.out.ID)
			hr := &HostReservation{}

			err = hr.ScanRow(row)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, *hr, tc.out)
		})
	}
}

func TestHostReservationLoadOptions(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in  string
		out map[uint16]string
		err error
	}{
		"one option": {
			in: `
			INSERT INTO host_reservation VALUES (NULL, "10.0.0.1", "ab:cd:ef:00:11:22", 3);
			INSERT INTO dhcp_option(label, number, value, host_reservation_id) VALUES ("mtu", 26, "1500", 1);
			`,
			out: map[uint16]string{
				26: "1500",
			},
		},
		"multiple options": {
			in: `
			INSERT INTO host_reservation VALUES (NULL, "10.0.0.1", "ab:cd:ef:00:11:22", 3);
			INSERT INTO dhcp_option(label, number, value, host_reservation_id) VALUES ("mtu", 26, "1500", 1);
			INSERT INTO dhcp_option(label, number, value, host_reservation_id) VALUES ("hostname", 12, "test", 1);
			`,
			out: map[uint16]string{
				26: "1500",
				12: "test",
			},
		},
		"inherits from VLAN": {
			in: `
			INSERT INTO vlan VALUES (2, 2, NULL);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 2);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.21", 20, false, true, 3);
			INSERT INTO host_reservation VALUES (1, "10.0.0.2", "ab:cd:ef:00:11:22", 4);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 2);
			`,
			out: map[uint16]string{
				26: "1500",
			},
		},
		"subnet inheritance overrides VLAN": {
			in: `
			INSERT INTO vlan VALUES (2, 2, NULL);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 2);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.21", 20, false, true, 3);
			INSERT INTO host_reservation VALUES (1, "10.0.0.2", "ab:cd:ef:00:11:22", 4);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 2);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("mtu", 26, "1000", 3);
			`,
			out: map[uint16]string{
				26: "1000",
			},
		},
		"ip range inheritance overrides subnet": {
			in: `
			INSERT INTO vlan VALUES (2, 2, NULL);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 2);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.21", 20, false, true, 3);
			INSERT INTO host_reservation VALUES (1, "10.0.0.2", "ab:cd:ef:00:11:22", 4);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 2);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("mtu", 26, "1000", 3);
			INSERT INTO dhcp_option(label, number, value, range_id) VALUES ("mtu", 26, "500", 4);
			`,
			out: map[uint16]string{
				26: "500",
			},
		},
		"self overrides all inherited options": {
			in: `
			INSERT INTO vlan VALUES (2, 2, NULL);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 2);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.21", 20, false, true, 3);
			INSERT INTO host_reservation VALUES (1, "10.0.0.2", "ab:cd:ef:00:11:22", 4);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 2);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("mtu", 26, "1000", 3);
			INSERT INTO dhcp_option(label, number, value, range_id) VALUES ("mtu", 26, "500", 4);
			INSERT INTO dhcp_option(label, number, value, host_reservation_id) VALUES ("mtu", 26, "3200", 1);
			`,
			out: map[uint16]string{
				26: "3200",
			},
		},
		"no options": {
			in:  "INSERT INTO host_reservation VALUES (1, \"10.0.0.2\", \"ab:cd:ef:00:11:22\", 4);",
			out: map[uint16]string{},
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

			_, err = tx.ExecContext(ctx, tc.in)
			require.NoError(t, err)

			row := tx.QueryRowContext(ctx, "SELECT * FROM host_reservation WHERE id = 1;")
			hr := &HostReservation{}

			err = hr.ScanRow(row)
			require.NoError(t, err)

			err = hr.LoadOptions(ctx, tx)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, hr.Options, tc.out)
		})
	}
}

func TestLeaseScanRow(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testMac, _ := net.ParseMAC("ab:cd:ef:00:11:22")
	testcases := map[string]struct {
		in  string
		out Lease
		err error
	}{
		"all values set": {
			in: "INSERT INTO lease VALUES (NULL, \"10.0.0.1\", \"ab:cd:ef:00:11:22\", NULL, 100, 100, 3000, 0, true, 3);",
			out: Lease{
				ID:         1,
				IP:         net.ParseIP("10.0.0.1"),
				MACAddress: testMac,
				CreatedAt:  100,
				UpdatedAt:  100,
				Lifetime:   3000,
				State:      LeaseStateOffered,
				NeedsSync:  true,
				RangeID:    3,
			},
		},
		"missing": {
			err: sql.ErrNoRows,
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

			_, err = tx.ExecContext(ctx, tc.in)
			require.NoError(t, err)

			row := tx.QueryRowContext(ctx, "SELECT * FROM lease WHERE id = $1;", tc.out.ID)
			lease := &Lease{}

			err = lease.ScanRow(row)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, *lease, tc.out)
		})
	}
}

func TestLeaseLoadOptions(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		in  string
		out map[uint16]string
		err error
	}{
		"inherits from VLAN": {
			in: `
			INSERT INTO vlan VALUES (2, 2, NULL);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 2);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.21", 20, false, true, 3);
			INSERT INTO lease VALUES (NULL, "10.0.0.1", "ab:cd:ef:00:11:22", NULL, 100, 100, 3000, 0, true, 4);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 2);
			`,
			out: map[uint16]string{
				26: "1500",
			},
		},
		"subnet inheritance overrides VLAN": {
			in: `
			INSERT INTO vlan VALUES (2, 2, NULL);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 2);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.21", 20, false, true, 3);
			INSERT INTO lease VALUES (NULL, "10.0.0.1", "ab:cd:ef:00:11:22", NULL, 100, 100, 3000, 0, true, 4);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 2);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("mtu", 26, "1000", 3);
			`,
			out: map[uint16]string{
				26: "1000",
			},
		},
		"ip range inheritance overrides subnet": {
			in: `
			INSERT INTO vlan VALUES (2, 2, NULL);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 2);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.21", 20, false, true, 3);
			INSERT INTO lease VALUES (NULL, "10.0.0.1", "ab:cd:ef:00:11:22", NULL, 100, 100, 3000, 0, true, 4);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 2);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("mtu", 26, "1000", 3);
			INSERT INTO dhcp_option(label, number, value, range_id) VALUES ("mtu", 26, "500", 4);
			`,
			out: map[uint16]string{
				26: "500",
			},
		},
		"host reservation overrides all inherited options": {
			in: `
			INSERT INTO vlan VALUES (2, 2, NULL);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 2);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.21", 20, false, true, 3);
			INSERT INTO host_reservation VALUES (1, "10.0.0.1", "ab:cd:ef:00:11:22", 4);
			INSERT INTO lease VALUES (NULL, "10.0.0.1", "ab:cd:ef:00:11:22", NULL, 100, 100, 3000, 0, true, 4);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 2);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("mtu", 26, "1000", 3);
			INSERT INTO dhcp_option(label, number, value, range_id) VALUES ("mtu", 26, "500", 4);
			INSERT INTO dhcp_option(label, number, value, host_reservation_id) VALUES ("mtu", 26, "3200", 1);
			`,
			out: map[uint16]string{
				26: "3200",
			},
		},
		"no options": {
			in: `
			INSERT INTO vlan VALUES (2, 2, NULL);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 2);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.21", 20, false, true, 3);
			INSERT INTO lease VALUES (NULL, "10.0.0.1", "ab:cd:ef:00:11:22", NULL, 100, 100, 3000, 0, true, 4);
			`,
			out: map[uint16]string{},
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

			_, err = tx.ExecContext(ctx, tc.in)
			require.NoError(t, err)

			row := tx.QueryRowContext(ctx, "SELECT * FROM lease WHERE id = 1;")
			lease := &Lease{}

			err = lease.ScanRow(row)
			require.NoError(t, err)

			err = lease.LoadOptions(ctx, tx)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, lease.Options, tc.out)
		})
	}
}

func TestExpirationScanRow(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testMac, _ := net.ParseMAC("ab:cd:ef:00:11:22")
	testcases := map[string]struct {
		in  string
		out Expiration
		err error
	}{
		"all values set": {
			in: "INSERT INTO expiration VALUES (NULL, \"10.0.0.1\", \"ab:cd:ef:00:11:22\", NULL, 100);",
			out: Expiration{
				ID:         1,
				IP:         net.ParseIP("10.0.0.1"),
				MACAddress: testMac,
				CreatedAt:  100,
			},
		},
		"missing": {
			err: sql.ErrNoRows,
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

			_, err = tx.ExecContext(ctx, tc.in)
			require.NoError(t, err)

			row := tx.QueryRowContext(ctx, "SELECT * FROM expiration WHERE id = $1;", tc.out.ID)
			expiration := &Expiration{}

			err = expiration.ScanRow(row)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, *expiration, tc.out)
		})
	}
}
