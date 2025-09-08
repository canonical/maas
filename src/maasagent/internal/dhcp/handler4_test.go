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
	"path/filepath"
	"strings"
	"testing"

	"github.com/canonical/lxd/lxd/db/schema"
	"github.com/canonical/microcluster/v2/microcluster"
	"github.com/canonical/microcluster/v2/state"
	"github.com/insomniacslk/dhcp/dhcpv4"
	"github.com/insomniacslk/dhcp/dhcpv6"
	"github.com/insomniacslk/dhcp/iana"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"maas.io/core/src/maasagent/internal/cluster"
)

func TestDORAHandlerServeDHCP4(t *testing.T) {
	hostname, hostnameErr := os.Hostname()
	require.NoError(t, hostnameErr)

	testcases := map[string]struct {
		data string
		in   Message
		out  *dhcpv4.DHCPv4
		err  error
	}{
		"discover": {
			data: fmt.Sprintf(`
			INSERT INTO vlan (id, vid) VALUES (1, 0);
			INSERT INTO interface (id, hostname, idx, vlan_id) VALUES (1, '%s', 1, 1);
			INSERT INTO subnet (id, cidr, address_family, vlan_id) VALUES (1, '10.0.0.0/24', 4, 1);
			INSERT INTO ip_range (id, start_ip, end_ip, size, fully_allocated, dynamic, subnet_id) VALUES (1, '10.0.0.2', '10.0.0.22', 20, false, true, 1);
			INSERT INTO dhcp_option (id, label, number, value, vlan_id) VALUES (1, 'lease_lifetime', 51, "30", 1);
			INSERT INTO dhcp_option (id, label, number, value, subnet_id) VALUES (2, 'gateway_ip', 3, "10.0.0.1", 1);
			`, hostname),
			in: Message{
				IfaceIdx: 1,
				SrcMAC:   net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				Pkt4: &dhcpv4.DHCPv4{
					OpCode:        dhcpv4.OpcodeBootRequest,
					HWType:        iana.HWTypeEthernet,
					ClientHWAddr:  net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
					ClientIPAddr:  net.ParseIP("0.0.0.0").To4(),
					ServerIPAddr:  net.ParseIP("255.255.255.255").To4(),
					TransactionID: [4]byte{0x01, 0x02, 0x03, 0x04},
					Options: dhcpv4.Options{
						uint8(dhcpv4.OptionDHCPMessageType): []byte{byte(dhcpv4.MessageTypeDiscover)},
					},
				},
			},
			out: &dhcpv4.DHCPv4{
				OpCode:        dhcpv4.OpcodeBootReply,
				HWType:        iana.HWTypeEthernet,
				ClientHWAddr:  net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				ClientIPAddr:  net.ParseIP("0.0.0.0").To4(),
				YourIPAddr:    net.ParseIP("10.0.0.2").To4(),
				ServerIPAddr:  net.ParseIP("127.0.0.1").To4(),
				GatewayIPAddr: net.ParseIP("10.0.0.1").To4(),
				TransactionID: [4]byte{0x01, 0x02, 0x03, 0x04},
				Options: dhcpv4.Options{
					uint8(dhcpv4.OptionDHCPMessageType):    []byte{byte(dhcpv4.MessageTypeOffer)},
					uint8(dhcpv4.OptionIPAddressLeaseTime): []byte{0x00, 0x00, 0x00, 0x1e},
					uint8(dhcpv4.OptionRouter):             []byte(net.ParseIP("10.0.0.1").To4()),
				},
			},
		},
		"request": {
			data: fmt.Sprintf(`
			INSERT INTO vlan (id, vid) VALUES (1, 0);
			INSERT INTO interface (id, hostname, idx, vlan_id) VALUES (1, '%s', 1, 1);
			INSERT INTO subnet (id, cidr, address_family, vlan_id) VALUES (1, '10.0.0.0/24', 4, 1);
			INSERT INTO ip_range (id, start_ip, end_ip, size, fully_allocated, dynamic, subnet_id) VALUES (1, '10.0.0.2', '10.0.0.22', 20, false, true, 1);
			INSERT INTO lease (id, ip, mac_address, created_at, updated_at, lifetime, state, needs_sync, range_id) VALUES (1, '10.0.0.2', 'ab:cd:ef:00:11:22', 10, 10, 30, 0, true, 1);
			INSERT INTO dhcp_option (id, label, number, value, vlan_id) VALUES (1, 'lease_lifetime', 51, "30", 1);
			INSERT INTO dhcp_option (id, label, number, value, subnet_id) VALUES (2, 'gateway_ip', 3, "10.0.0.1", 1);
			`, hostname),
			in: Message{
				IfaceIdx: 1,
				SrcMAC:   net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				SrcIP:    net.ParseIP("10.0.0.2"),
				SrcPort:  68,
				Pkt4: &dhcpv4.DHCPv4{
					OpCode:        dhcpv4.OpcodeBootRequest,
					HWType:        iana.HWTypeEthernet,
					ClientHWAddr:  net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
					ClientIPAddr:  net.ParseIP("0.0.0.0").To4(),
					ServerIPAddr:  net.ParseIP("255.255.255.255").To4(),
					TransactionID: [4]byte{0x01, 0x02, 0x03, 0x04},
					Options: dhcpv4.Options{
						uint8(dhcpv4.OptionDHCPMessageType):    []byte{byte(dhcpv4.MessageTypeRequest)},
						uint8(dhcpv4.OptionRequestedIPAddress): []byte(net.ParseIP("10.0.0.2").To4()),
					},
				},
			},
			out: &dhcpv4.DHCPv4{
				OpCode:        dhcpv4.OpcodeBootReply,
				HWType:        iana.HWTypeEthernet,
				ClientHWAddr:  net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				ClientIPAddr:  net.ParseIP("0.0.0.0").To4(),
				ServerIPAddr:  net.ParseIP("127.0.0.1").To4(),
				YourIPAddr:    net.ParseIP("10.0.0.2").To4(),
				GatewayIPAddr: net.ParseIP("10.0.0.1").To4(),
				TransactionID: [4]byte{0x01, 0x02, 0x03, 0x04},
				Options: dhcpv4.Options{
					uint8(dhcpv4.OptionDHCPMessageType):    []byte{byte(dhcpv4.MessageTypeAck)},
					uint8(dhcpv4.OptionIPAddressLeaseTime): []byte{0x00, 0x00, 0x00, 0x1e},
					uint8(dhcpv4.OptionRouter):             []byte(net.ParseIP("10.0.0.1").To4()),
				},
			},
		},
		"decline": {
			in: Message{
				IfaceIdx: 1,
				SrcMAC:   net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				Pkt4: &dhcpv4.DHCPv4{
					OpCode:        dhcpv4.OpcodeBootRequest,
					HWType:        iana.HWTypeEthernet,
					ClientHWAddr:  net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
					ClientIPAddr:  net.ParseIP("0.0.0.0").To4(),
					ServerIPAddr:  net.ParseIP("255.255.255.255").To4(),
					TransactionID: [4]byte{0x01, 0x02, 0x03, 0x04},
					Options: dhcpv4.Options{
						uint8(dhcpv4.OptionDHCPMessageType):    []byte{byte(dhcpv4.MessageTypeDecline)},
						uint8(dhcpv4.OptionRequestedIPAddress): []byte(net.ParseIP("10.0.0.2").To4()),
					},
				},
			},
		},
		"release": {
			data: fmt.Sprintf(`
			INSERT INTO vlan (id, vid) VALUES (1, 0);
			INSERT INTO interface (id, hostname, idx, vlan_id) VALUES (1, '%s', 1, 1);
			INSERT INTO subnet (id, cidr, address_family, vlan_id) VALUES (1, '10.0.0.0/24', 4, 1);
			INSERT INTO ip_range (id, start_ip, end_ip, size, fully_allocated, dynamic, subnet_id) VALUES (1, '10.0.0.2', '10.0.0.22', 20, false, true, 1);
			INSERT INTO lease (id, ip, mac_address, created_at, updated_at, lifetime, state, needs_sync, range_id) VALUES (1, '10.0.0.2', 'ab:cd:ef:00:11:22', 10, 10, 30, 1, true, 1);
			INSERT INTO dhcp_option (id, label, number, value, vlan_id) VALUES (1, 'lease_lifetime', 51, "30", 1);
			INSERT INTO dhcp_option (id, label, number, value, subnet_id) VALUES (2, 'gateway_ip', 3, "10.0.0.1", 1);
			`, hostname),
			in: Message{
				IfaceIdx: 1,
				SrcMAC:   net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				Pkt4: &dhcpv4.DHCPv4{
					OpCode:        dhcpv4.OpcodeBootRequest,
					HWType:        iana.HWTypeEthernet,
					ClientHWAddr:  net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
					ClientIPAddr:  net.ParseIP("0.0.0.0").To4(),
					ServerIPAddr:  net.ParseIP("255.255.255.255").To4(),
					TransactionID: [4]byte{0x01, 0x02, 0x03, 0x04},
					Options: dhcpv4.Options{
						uint8(dhcpv4.OptionDHCPMessageType):    []byte{byte(dhcpv4.MessageTypeRelease)},
						uint8(dhcpv4.OptionRequestedIPAddress): []byte(net.ParseIP("10.0.0.2").To4()),
					},
				},
			},
		},
		"inform": {
			data: fmt.Sprintf(`
			INSERT INTO vlan (id, vid) VALUES (1, 0);
			INSERT INTO interface (id, hostname, idx, vlan_id) VALUES (1, '%s', 1, 1);
			INSERT INTO subnet (id, cidr, address_family, vlan_id) VALUES (1, '10.0.0.0/24', 4, 1);
			INSERT INTO ip_range (id, start_ip, end_ip, size, fully_allocated, dynamic, subnet_id) VALUES (1, '10.0.0.2', '10.0.0.22', 20, false, true, 1);
			INSERT INTO lease (id, ip, mac_address, created_at, updated_at, lifetime, state, needs_sync, range_id) VALUES (1, '10.0.0.2', 'ab:cd:ef:00:11:22', 10, 10, 30, 1, true, 1);
			INSERT INTO dhcp_option (id, label, number, value, vlan_id) VALUES (1, 'lease_lifetime', 51, "30", 1);
			INSERT INTO dhcp_option (id, label, number, value, subnet_id) VALUES (2, 'gateway_ip', 3, "10.0.0.1", 1);
			`, hostname),
			in: Message{
				IfaceIdx: 1,
				SrcMAC:   net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				Pkt4: &dhcpv4.DHCPv4{
					OpCode:        dhcpv4.OpcodeBootRequest,
					HWType:        iana.HWTypeEthernet,
					TransactionID: [4]byte{0x01, 0x02, 0x03, 0x04},
					ClientHWAddr:  net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
					ClientIPAddr:  net.ParseIP("10.0.0.2").To4(),
					YourIPAddr:    net.ParseIP("10.0.0.2").To4(),
					ServerIPAddr:  net.ParseIP("127.0.0.1").To4(),
					GatewayIPAddr: net.ParseIP("10.0.0.1").To4(),
					Options: dhcpv4.Options{
						uint8(dhcpv4.OptionDHCPMessageType):    []byte{byte(dhcpv4.MessageTypeInform)},
						uint8(dhcpv4.OptionRequestedIPAddress): []byte(net.ParseIP("10.0.0.2").To4()),
					},
				},
			},
			out: &dhcpv4.DHCPv4{
				OpCode:        dhcpv4.OpcodeBootReply,
				HWType:        iana.HWTypeEthernet,
				TransactionID: [4]byte{0x01, 0x02, 0x03, 0x04},
				ClientHWAddr:  net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				ClientIPAddr:  net.ParseIP("10.0.0.2").To4(),
				YourIPAddr:    net.ParseIP("10.0.0.2").To4(),
				ServerIPAddr:  net.ParseIP("127.0.0.1").To4(),
				GatewayIPAddr: net.ParseIP("10.0.0.1").To4(),
				Options: dhcpv4.Options{
					uint8(dhcpv4.OptionDHCPMessageType):    []byte{byte(dhcpv4.MessageTypeAck)},
					uint8(dhcpv4.OptionIPAddressLeaseTime): []byte{0x00, 0x00, 0x00, 0x1e},
					uint8(dhcpv4.OptionRouter):             []byte(net.ParseIP("10.0.0.1").To4()),
				},
			},
		},
		"not dhcp4": {
			in: Message{
				IfaceIdx: 1,
				SrcMAC:   net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				Pkt6:     &dhcpv6.Message{},
			},
			err: ErrNotDHCPv4,
		},
		"invalid message": {
			in: Message{
				IfaceIdx: 1,
				SrcMAC:   net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
				Pkt4:     &dhcpv4.DHCPv4{},
			},
			err: ErrInvalidMessageType,
		},
	}

	i := 0

	for tname, tc := range testcases {
		t.Run(tname, func(t *testing.T) {
			ctx := context.Background()

			_ = tc

			if deadline, ok := t.Deadline(); ok {
				var cancel context.CancelFunc

				ctx, cancel = context.WithDeadline(ctx, deadline)

				defer cancel()
			}

			dataPath := t.TempDir()
			app, appErr := microcluster.App(microcluster.Args{
				StateDir: filepath.Join(dataPath, "microcluster"),
			})
			require.NoError(t, appErr)

			clusterName := strings.ReplaceAll(strings.ReplaceAll(t.Name(), "/", "-"), "_", "-")

			errChan := make(chan error)

			go app.Start(ctx, microcluster.DaemonArgs{
				Version:          "UNKNOWN",
				Debug:            false,
				ExtensionsSchema: []schema.Update{cluster.SchemaAppendDHCP},
				Hooks: &state.Hooks{
					OnStart: func(ctx context.Context, s state.State) error {
						defer close(errChan)

						err := app.NewCluster(ctx, clusterName, fmt.Sprintf("127.0.0.1:555%d", i), nil)
						if err != nil {
							errChan <- err
							return nil
						}

						err = s.Database().IsOpen(ctx)
						if err != nil {
							errChan <- err
							return nil
						}

						err = s.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
							_, err = tx.ExecContext(ctx, tc.data)
							return err
						})
						if err != nil {
							errChan <- err
							return nil
						}

						allocator, err := newDQLiteAllocator4()
						if err != nil {
							errChan <- err
							return nil
						}

						handler := NewDORAHandler(allocator, s)

						handler.discoverReplyOverride = func(ctx context.Context, ifaceIdx int, resp *dhcpv4.DHCPv4) error {
							assert.Equal(t, resp, tc.out)
							return nil
						}

						handler.requestReplyOverride = func(ctx context.Context, resp *dhcpv4.DHCPv4) error {
							assert.Equal(t, resp, tc.out)
							return nil
						}

						handler.informReplyOverride = func(ctx context.Context, resp *dhcpv4.DHCPv4) error {
							assert.Equal(t, resp, tc.out)
							return nil
						}

						err = handler.ServeDHCPv4(ctx, tc.in)
						if err != nil {
							if tc.err != nil {
								assert.ErrorIs(t, err, tc.err)
								return nil
							}

							errChan <- err
						}

						return nil
					},
				},
			})

			err := <-errChan
			if err != nil {
				t.Fatal(err)
			}
		})

		i++
	}
}
