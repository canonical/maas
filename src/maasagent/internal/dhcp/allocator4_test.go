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
	"fmt"
	"net"
	"os"
	"testing"
	"time"

	"github.com/insomniacslk/dhcp/dhcpv4"
	"github.com/insomniacslk/dhcp/iana"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestAllocator4GetOfferFromDiscover(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	hostname, err := os.Hostname()
	require.NoError(t, err)

	testMAC := net.HardwareAddr{0xAB, 0xCD, 0xEF, 0x00, 0x11, 0x22}

	testDiscover, err := dhcpv4.NewDiscovery(testMAC)
	require.NoError(t, err)

	testcases := map[string]struct {
		data string
		in   dhcpv4.DHCPv4
		out  Offer
		err  error
	}{
		"chooses IP in a dynamic range": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (2, "%s", 1, 1);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.5", 4, false, false, 3);
			INSERT INTO ip_range VALUES (5, "10.0.0.10", "10.0.0.15", 4, false, true, 3);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 1);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("lease lifetime", 51, "3000", 1);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("gateway", 3, "10.0.0.1", 3);
			`, hostname),
			in: *testDiscover,
			out: Offer{
				IP: net.ParseIP("10.0.0.10").To4(),
				Options: map[uint16]string{
					3:  "10.0.0.1",
					26: "1500",
					51: "3000",
				},
			},
		},
		"chooses next IP after most recent lease": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (2, "%s", 1, 1);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.5", 4, false, false, 3);
			INSERT INTO ip_range VALUES (5, "10.0.0.10", "10.0.0.15", 4, false, true, 3);
			INSERT INTO lease VALUES (6, "10.0.0.10", "00:11:22:33:44:55", NULL, 100, 100, 3000, 0, true, 5);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 1);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("lease lifetime", 51, "3000", 1);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("gateway", 3, "10.0.0.1", 3);
			`, hostname),
			in: *testDiscover,
			out: Offer{
				IP: net.ParseIP("10.0.0.11").To4(),
				Options: map[uint16]string{
					3:  "10.0.0.1",
					26: "1500",
					51: "3000",
				},
			},
		},
		"chooses host reservation if one exists": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (2, "%s", 1, 1);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.5", 4, false, false, 3);
			INSERT INTO ip_range VALUES (5, "10.0.0.10", "10.0.0.15", 4, false, true, 3);
			INSERT INTO host_reservation(id, ip_address, mac_address, range_id, subnet_id) VALUES (6, "10.0.0.2", "ab:cd:ef:00:11:22", 4, 3);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 1);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("lease lifetime", 51, "3000", 1);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("gateway", 3, "10.0.0.1", 3);
			INSERT INTO dhcp_option(label, number, value, host_reservation_id) VALUES ("hostname", 12, "test", 6);
			`, hostname),
			in: *testDiscover,
			out: Offer{
				IP: net.ParseIP("10.0.0.2").To4(),
				Options: map[uint16]string{
					3:  "10.0.0.1",
					12: "test",
					26: "1500",
					51: "3000",
				},
			},
		},
		"chooses existing valid lease": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (2, "%s", 1, 1);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.5", 4, false, false, 3);
			INSERT INTO ip_range VALUES (5, "10.0.0.10", "10.0.0.15", 4, false, true, 3);
			INSERT INTO lease VALUES (6, "10.0.0.10", "ab:cd:ef:00:11:22", NULL, 100, 100, 3000, 0, true, 5);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 1);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("lease lifetime", 51, "3000", 1);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("gateway", 3, "10.0.0.1", 3);
			`, hostname),
			in: *testDiscover,
			out: Offer{
				IP: net.ParseIP("10.0.0.10").To4(),
				Options: map[uint16]string{
					3:  "10.0.0.1",
					26: "1500",
					51: "3000",
				},
			},
		},
		"handles no matching vlan": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (2, "%s", 2, 1);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.5", 4, false, false, 3);
			INSERT INTO ip_range VALUES (5, "10.0.0.10", "10.0.0.15", 4, false, true, 3);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 1);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("lease lifetime", 51, "3000", 1);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("gateway", 3, "10.0.0.1", 3);
			`, hostname),
			in:  *testDiscover,
			err: ErrNoMatchingVLAN,
		},
		"handles all ranges fully allocated": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (2, "%s", 1, 1);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.5", 4, true, false, 3);
			INSERT INTO ip_range VALUES (5, "10.0.0.10", "10.0.0.15", 4, true, true, 3);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 1);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("lease lifetime", 51, "3000", 1);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("gateway", 3, "10.0.0.1", 3);
			`, hostname),
			in:  *testDiscover,
			err: ErrNoAvailableIP,
		},
		"scans range if all sequential IP allocated": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (2, "%s", 1, 1);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.5", 4, false, false, 3);
			INSERT INTO ip_range VALUES (5, "10.0.0.10", "10.0.0.15", 4, false, true, 3);
			INSERT INTO lease VALUES (6, "10.0.0.10", "ab:cd:ef:00:11:00", NULL, 100, 100, 3000, 0, true, 5);
			INSERT INTO lease VALUES (7, "10.0.0.11", "ab:cd:ef:00:11:01", NULL, 100, 100, 3000, 0, true, 5);
			INSERT INTO lease VALUES (8, "10.0.0.12", "ab:cd:ef:00:11:02", NULL, 100, 100, 3000, 0, true, 5);
			INSERT INTO lease VALUES (9, "10.0.0.14", "ab:cd:ef:00:11:03", NULL, 100, 100, 3000, 0, true, 5);
			INSERT INTO lease VALUES (10, "10.0.0.15", "ab:cd:ef:00:11:04", NULL, 100, 100, 3000, 0, true, 5);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("mtu", 26, "1500", 1);
			INSERT INTO dhcp_option(label, number, value, vlan_id) VALUES ("lease lifetime", 51, "3000", 1);
			INSERT INTO dhcp_option(label, number, value, subnet_id) VALUES ("gateway", 3, "10.0.0.1", 3);
			`, hostname),
			in: *testDiscover,
			out: Offer{
				IP: net.ParseIP("10.0.0.13").To4(),
				Options: map[uint16]string{
					3:  "10.0.0.1",
					26: "1500",
					51: "3000",
				},
			},
		},
		"ignores non-discovery messages": {
			in: dhcpv4.DHCPv4{
				OpCode: dhcpv4.OpcodeBootRequest,
				HWType: iana.HWTypeEthernet,
				Options: map[uint8][]byte{
					uint8(dhcpv4.OptionMessage): dhcpv4.MessageTypeRequest.ToBytes(),
				},
			},
			err: ErrInvalidDHCP4State,
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

			_, err = tx.ExecContext(ctx, tc.data)
			require.NoError(t, err)

			allocator, err := newDQLiteAllocator4()
			require.NoError(t, err)

			offer, err := allocator.GetOfferFromDiscover(ctx, tx, &tc.in, 1, testMAC)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, *offer, tc.out)
		})
	}
}

func TestGetVLANForAllocation(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	hostname, err := os.Hostname()
	require.NoError(t, err)

	testcases := map[string]struct {
		data string
		in   int
		out  Vlan
		err  error
	}{
		"basic": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (2, "%s", 1, 1);
			`, hostname),
			in: 1,
			out: Vlan{
				ID:  1,
				VID: 0,
			},
		},
		"multiple interfaces": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (2, "%s", 1, 1);
			INSERT INTO interface VALUES (3, "%s", 2, 1);
			`, hostname, hostname),
			in: 1,
			out: Vlan{
				ID:  1,
				VID: 0,
			},
		},
		"multiple vlans": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO vlan VALUES (2, 1, NULL);
			INSERT INTO interface VALUES (3, "%s", 1, 1);
			`, hostname),
			in: 1,
			out: Vlan{
				ID:  1,
				VID: 0,
			},
		},
		"vlan not found": {
			data: fmt.Sprintf(`
			INSERT INTO interface VALUES (1, "%s", 1, 1);
			`, hostname),
			in:  1,
			err: sql.ErrNoRows,
		},
		"interface not found": {
			data: "INSERT INTO vlan VALUES (1, 0, NULL);",
			in:   1,
			err:  sql.ErrNoRows,
		},
		// TODO test for relayed vlan
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

			_, err = tx.ExecContext(ctx, tc.data)
			require.NoError(t, err)

			allocator, err := newDQLiteAllocator4()
			require.NoError(t, err)

			vlan, err := allocator.getVLANForAllocation(ctx, tx, tc.in)
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

func TestGetLeaseIfExists(t *testing.T) {
	db, err := withTestDatabase(t)
	if err != nil {
		t.Fatal(err)
	}

	testcases := map[string]struct {
		data string
		in   struct {
			vlanID int
			mac    net.HardwareAddr
		}
		out Lease
		err error
	}{
		"lease exists": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.11", 10, false, true, 2);
			INSERT INTO lease VALUES (4, "10.0.0.2", "ab:cd:ef:00:11:22", NULL, 100, 100, 3000, 1, false, 3);
			`,
			in: struct {
				vlanID int
				mac    net.HardwareAddr
			}{
				vlanID: 1,
				mac:    net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
			out: Lease{
				ID:         4,
				IP:         net.ParseIP("10.0.0.2"),
				MACAddress: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				CreatedAt:  100,
				UpdatedAt:  100,
				Lifetime:   3000,
				State:      LeaseStateAcked,
				NeedsSync:  false,
				RangeID:    3,
			},
		},
		"lease exists for same mac different vlan": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO vlan VALUES (2, 1, NULL);
			INSERT INTO subnet VALUES (3, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (4, "10.0.0.1", "10.0.0.11", 10, false, true, 3);
			INSERT INTO lease VALUES (5, "10.0.0.2", "ab:cd:ef:00:11:22", NULL, 100, 100, 3000, 1, false, 3);
			`,
			in: struct {
				vlanID int
				mac    net.HardwareAddr
			}{
				vlanID: 2,
				mac:    net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
			err: sql.ErrNoRows,
		},
		"lease does not exist": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.11", 10, false, true, 2);
			`,
			in: struct {
				vlanID int
				mac    net.HardwareAddr
			}{
				vlanID: 1,
				mac:    net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
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

			_, err = tx.ExecContext(ctx, tc.data)
			require.NoError(t, err)

			allocator, err := newDQLiteAllocator4()
			require.NoError(t, err)

			lease, err := allocator.getLeaseIfExists(ctx, tx, tc.in.vlanID, tc.in.mac)
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

func TestGetHostReservationIfExists(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		data string
		in   struct {
			vlanID int
			mac    net.HardwareAddr
		}
		out HostReservation
		err error
	}{
		"host reservation exists": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.11", 10, false, true, 2);
			INSERT INTO host_reservation(id, ip_address, mac_address, range_id, subnet_id) VALUES (4, "10.0.0.2", "ab:cd:ef:00:11:22", 3, 2);
			`,
			in: struct {
				vlanID int
				mac    net.HardwareAddr
			}{
				vlanID: 1,
				mac:    net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
			out: HostReservation{
				ID:         4,
				IPAddress:  net.ParseIP("10.0.0.2"),
				MACAddress: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				RangeID:    3,
				SubnetID:   2,
			},
		},
		"host reservation exists for different vlan": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO vlan VALUES (5, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.11", 10, false, true, 2);
			INSERT INTO host_reservation(id, ip_address, mac_address, range_id, subnet_id) VALUES (4, "10.0.0.2", "ab:cd:ef:00:11:22", 3, 2);
			`,
			in: struct {
				vlanID int
				mac    net.HardwareAddr
			}{
				vlanID: 5,
				mac:    net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
			err: sql.ErrNoRows,
		},
		"no host reservation": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.11", 10, false, true, 2);
			`,
			in: struct {
				vlanID int
				mac    net.HardwareAddr
			}{
				vlanID: 1,
				mac:    net.HardwareAddr{0xab, 0xcd, 0xef, 0x11, 0x22, 0x33},
			},
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

			_, err = tx.ExecContext(ctx, tc.data)
			require.NoError(t, err)

			allocator, err := newDQLiteAllocator4()
			require.NoError(t, err)

			hr, err := allocator.getHostReservationIfExists(ctx, tx, tc.in.vlanID, tc.in.mac)
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

func TestGetIPRangeForAllocation(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		data string
		in   int
		out  IPRange
		err  error
	}{
		"basic": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.3", 2, true, false, 2);
			INSERT INTO ip_range VALUES (4, "10.0.0.10", "10.0.0.13", 2, false, true, 2);
			`,
			in: 1,
			out: IPRange{
				ID:             4,
				StartIP:        net.ParseIP("10.0.0.10"),
				EndIP:          net.ParseIP("10.0.0.13"),
				Size:           2,
				FullyAllocated: false,
				Dynamic:        true,
				SubnetID:       2,
			},
		},
		"no dynamic ranges": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.3", 2, true, false, 2);
			`,
			in:  1,
			err: ErrNoAvailableIP,
		},
		"all ranges full": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.3", 2, true, false, 2);
			INSERT INTO ip_range VALUES (4, "10.0.0.5", "10.0.0.8", 2, true, true, 2);
			`,
			in:  1,
			err: ErrNoAvailableIP,
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

			_, err = tx.ExecContext(ctx, tc.data)
			require.NoError(t, err)

			allocator, err := newDQLiteAllocator4()
			require.NoError(t, err)

			iprange, err := allocator.getIPRangeForAllocation(ctx, tx, tc.in, true)
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

func TestGetIPForAllocation(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		data string
		in   IPRange
		out  net.IP
		err  error
	}{
		"gets first IP": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			`,
			in: IPRange{
				ID:             3,
				StartIP:        net.ParseIP("10.0.0.1"),
				EndIP:          net.ParseIP("10.0.0.5"),
				Size:           4,
				FullyAllocated: false,
				Dynamic:        true,
				SubnetID:       2,
			},
			out: net.ParseIP("10.0.0.1"),
		},
		"gets next available IP": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			INSERT INTO lease VALUES (4, "10.0.0.1", "ab:cd:ef:00:11:22", NULL, 100, 100, 2000, 1, false, 3);
			`,
			in: IPRange{
				ID:             3,
				StartIP:        net.ParseIP("10.0.0.1"),
				EndIP:          net.ParseIP("10.0.0.5"),
				Size:           4,
				FullyAllocated: false,
				Dynamic:        true,
				SubnetID:       2,
			},
			out: net.ParseIP("10.0.0.2"),
		},
		"scans for free IP when last IP in range reached": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			INSERT INTO lease VALUES (4, "10.0.0.1", "ab:cd:ef:00:11:22", NULL, 100, 100, 2000, 1, false, 3);
			INSERT INTO lease VALUES (5, "10.0.0.2", "ab:cd:ef:00:11:22", NULL, 100, 100, 2000, 1, false, 3);
			INSERT INTO lease VALUES (6, "10.0.0.4", "ab:cd:ef:00:11:22", NULL, 100, 100, 2000, 1, false, 3);
			`,
			in: IPRange{
				ID:             3,
				StartIP:        net.ParseIP("10.0.0.1"),
				EndIP:          net.ParseIP("10.0.0.5"),
				Size:           4,
				FullyAllocated: false,
				Dynamic:        true,
				SubnetID:       2,
			},
			out: net.ParseIP("10.0.0.3"),
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

			_, err = tx.ExecContext(ctx, tc.data)
			require.NoError(t, err)

			allocator, err := newDQLiteAllocator4()
			require.NoError(t, err)

			ip, err := allocator.getIPForAllocation(ctx, tx, &tc.in)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, ip, tc.out.To4())
		})
	}
}

func TestSetIPRangeFull(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

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

	require.NoError(t, setupSchema(ctx, tx))

	_, err = tx.ExecContext(ctx, `
	INSERT INTO vlan VALUES (1, 0, NULL);
	INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
	INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
	`)
	require.NoError(t, err)

	allocator, err := newDQLiteAllocator4()
	require.NoError(t, err)

	err = allocator.setIPRangeFull(ctx, tx, 3)
	require.NoError(t, err)

	row := tx.QueryRowContext(ctx, "SELECT fully_allocated FROM ip_range WHERE id=3;")

	var fullyAllocated bool

	err = row.Scan(&fullyAllocated)
	require.NoError(t, err)

	assert.True(t, fullyAllocated)
}

func TestCreateOfferedLease(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	testcases := map[string]struct {
		data string
		in   struct {
			offer     Offer
			mac       net.HardwareAddr
			iprangeID int
		}
		out Lease
		err error
	}{
		"basic": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			INSERT INTO dhcp_option(id, label, number, value, vlan_id) VALUES (4, "lease_lifetime", 51, "30", 1);
			`,
			in: struct {
				offer     Offer
				mac       net.HardwareAddr
				iprangeID int
			}{
				offer: Offer{
					IP: net.ParseIP("10.0.0.2").To4(),
				},
				mac:       net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				iprangeID: 3,
			},
			out: Lease{
				IP:         net.ParseIP("10.0.0.2").To4(),
				MACAddress: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				Lifetime:   30000,
				State:      LeaseStateOffered,
				RangeID:    3,
				NeedsSync:  true,
				Options: map[uint16]string{
					51: "30",
				},
			},
		},
		"lease lifetime missing": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			`,
			in: struct {
				offer     Offer
				mac       net.HardwareAddr
				iprangeID int
			}{
				offer: Offer{
					IP: net.ParseIP("10.0.0.2").To4(),
				},
				mac:       net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				iprangeID: 3,
			},
			err: ErrMissingDHCPOption,
		},
		"iprange not found": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			`,
			in: struct {
				offer     Offer
				mac       net.HardwareAddr
				iprangeID int
			}{
				offer: Offer{
					IP: net.ParseIP("10.0.0.2").To4(),
				},
				mac:       net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				iprangeID: 3,
			},
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

			require.NoError(t, setupSchema(ctx, tx))

			_, err = tx.ExecContext(ctx, tc.data)
			require.NoError(t, err)

			allocator, err := newDQLiteAllocator4()
			require.NoError(t, err)

			lease, err := allocator.createOfferedLease(ctx, tx, &tc.in.offer, tc.in.mac, tc.in.iprangeID)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, lease.IP, tc.out.IP)
			assert.Equal(t, lease.MACAddress, tc.out.MACAddress)
			assert.Equal(t, lease.State, tc.out.State)
			assert.Equal(t, lease.Lifetime, tc.out.Lifetime)
			assert.Equal(t, lease.RangeID, tc.out.RangeID)
			assert.Equal(t, lease.Options, tc.out.Options)
		})
	}
}

func TestAckLease(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	now := time.Now().Unix() - 1 // execution can be fast enough that we get the same timestamp twice
	testcases := map[string]struct {
		data string
		in   struct {
			ip  net.IP
			mac net.HardwareAddr
		}
		out Lease
		err error
	}{
		"basic": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			INSERT INTO lease VALUES (4, "10.0.0.2", "ab:cd:ef:00:11:22", NULL, %d, %d, 30000, 0, true, 3);
			`, now, now),
			in: struct {
				ip  net.IP
				mac net.HardwareAddr
			}{
				ip:  net.ParseIP("10.0.0.2"),
				mac: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
			out: Lease{
				ID:         4,
				IP:         net.ParseIP("10.0.0.2").To4(),
				MACAddress: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				CreatedAt:  int(now),
				Lifetime:   30000,
				State:      LeaseStateAcked,
				NeedsSync:  true,
				RangeID:    3,
			},
		},
		"lease not found": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			`,
			in: struct {
				ip  net.IP
				mac net.HardwareAddr
			}{
				ip:  net.ParseIP("10.0.0.2").To4(),
				mac: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
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

			require.NoError(t, setupSchema(ctx, tx))

			_, err = tx.ExecContext(ctx, tc.data)
			require.NoError(t, err)

			allocator, err := newDQLiteAllocator4()
			require.NoError(t, err)

			lease, err := allocator.ACKLease(ctx, tx, tc.in.ip, tc.in.mac)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			assert.Equal(t, lease.IP.To4(), tc.out.IP)
			assert.Equal(t, lease.MACAddress, tc.out.MACAddress)
			assert.Equal(t, lease.CreatedAt, tc.out.CreatedAt)
			assert.Greater(t, lease.UpdatedAt, tc.out.CreatedAt)
			assert.Equal(t, lease.Lifetime, tc.out.Lifetime)
			assert.Equal(t, lease.RangeID, tc.out.RangeID)
		})
	}
}

func TestNACKRelease(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	hostname, err := os.Hostname()
	require.NoError(t, err)

	testcases := map[string]struct {
		data string
		in   struct {
			ip  net.IP
			mac net.HardwareAddr
		}
		err error
	}{
		"basic": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (1, "%s", 1, 1);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			INSERT INTO lease VALUES (4, "10.0.0.2", "ab:cd:ef:00:11:22", NULL, 300, 300, 3000, 0, true, 3);
			`, hostname),
			in: struct {
				ip  net.IP
				mac net.HardwareAddr
			}{
				ip:  net.ParseIP("10.0.0.2").To4(),
				mac: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
		},
		"lease does not exist": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (1, "%s", 1, 1);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			`, hostname),
			in: struct {
				ip  net.IP
				mac net.HardwareAddr
			}{
				ip:  net.ParseIP("10.0.0.2").To4(),
				mac: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
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

			require.NoError(t, setupSchema(ctx, tx))

			_, err = tx.ExecContext(ctx, tc.data)
			require.NoError(t, err)

			allocator, err := newDQLiteAllocator4()
			require.NoError(t, err)

			err = allocator.NACKLease(ctx, tx, tc.in.ip, tc.in.mac)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			row := tx.QueryRowContext(ctx, "SELECT * FROM lease WHERE mac_address = $1;", tc.in.mac)
			lease := &Lease{}

			err = lease.ScanRow(row)
			assert.ErrorIs(t, err, sql.ErrNoRows)
		})
	}
}

func TestUpdateForRenewal(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	now := time.Now().Unix() - 1 // execution can be fast enough that we get the same timestamp twice
	testcases := map[string]struct {
		data string
		in   struct {
			ip  net.IP
			mac net.HardwareAddr
		}
		err error
	}{
		"basic": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			INSERT INTO lease VALUES (4, "10.0.0.2", "ab:cd:ef:00:11:22", NULL, %d, %d, 30000, 1, true, 3);
			`, now, now),
			in: struct {
				ip  net.IP
				mac net.HardwareAddr
			}{
				ip:  net.ParseIP("10.0.0.2"),
				mac: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
		},
		"lease not found": {
			data: `
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			`,
			in: struct {
				ip  net.IP
				mac net.HardwareAddr
			}{
				ip:  net.ParseIP("10.0.0.2").To4(),
				mac: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
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

			require.NoError(t, setupSchema(ctx, tx))

			_, err = tx.ExecContext(ctx, tc.data)
			require.NoError(t, err)

			allocator, err := newDQLiteAllocator4()
			require.NoError(t, err)

			err = allocator.UpdateForRenewal(ctx, tx, tc.in.ip, tc.in.mac)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			lease := &Lease{}
			row := tx.QueryRowContext(ctx, "SELECT * FROM lease WHERE id = 4;")

			err = lease.ScanRow(row)
			require.NoError(t, err)

			assert.Greater(t, lease.UpdatedAt, lease.CreatedAt)
		})
	}
}

func TestRelease(t *testing.T) {
	db, err := withTestDatabase(t)
	require.NoError(t, err)

	now := time.Now().Unix() - 1 // execution can be fast enough that we get the same timestamp twice

	hostname, err := os.Hostname()
	require.NoError(t, err)

	testcases := map[string]struct {
		data string
		in   struct {
			ifaceIdx int
			mac      net.HardwareAddr
		}
		out Expiration
		err error
	}{
		"basic": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (1, "%s", 1, 1);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			INSERT INTO lease VALUES (4, "10.0.0.2", "ab:cd:ef:00:11:22", NULL, %d, %d, 30000, 1, true, 3);
			`, hostname, now, now),
			in: struct {
				ifaceIdx int
				mac      net.HardwareAddr
			}{
				ifaceIdx: 1,
				mac:      net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
			out: Expiration{
				IP:         net.ParseIP("10.0.0.2"),
				MACAddress: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
		},
		"lease not found": {
			data: fmt.Sprintf(`
			INSERT INTO vlan VALUES (1, 0, NULL);
			INSERT INTO interface VALUES (1, "%s", 1, 1);
			INSERT INTO subnet VALUES (2, "10.0.0.0/24", 4, 1);
			INSERT INTO ip_range VALUES (3, "10.0.0.1", "10.0.0.5", 4, false, true, 2);
			`, hostname),
			in: struct {
				ifaceIdx int
				mac      net.HardwareAddr
			}{
				ifaceIdx: 1,
				mac:      net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
			},
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

			require.NoError(t, setupSchema(ctx, tx))

			_, err = tx.ExecContext(ctx, tc.data)
			require.NoError(t, err)

			allocator, err := newDQLiteAllocator4()
			require.NoError(t, err)

			err = allocator.Release(ctx, tx, tc.in.ifaceIdx, tc.in.mac)
			if err != nil {
				if tc.err != nil {
					assert.ErrorIs(t, err, tc.err)
					return
				}

				t.Fatal(err)
			}

			lease := &Lease{}
			row := tx.QueryRowContext(ctx, "SELECT * FROM lease WHERE id = 4;")

			assert.ErrorIs(t, lease.ScanRow(row), sql.ErrNoRows)

			expiration := &Expiration{}
			row = tx.QueryRowContext(ctx, "SELECT * FROM expiration WHERE mac_address = $1;", tc.in.mac.String())

			err = expiration.ScanRow(row)
			require.NoError(t, err)
			assert.Equal(t, expiration.IP.To4(), tc.out.IP.To4())
			assert.Equal(t, expiration.IP.To4(), tc.out.IP.To4())
		})
	}
}
