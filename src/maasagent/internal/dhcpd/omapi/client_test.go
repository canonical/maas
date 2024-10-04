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

package omapi

import (
	"encoding/json"
	"fmt"
	"net"
	"os"
	"strings"
	"testing"
	"time"

	backoff "github.com/cenkalti/backoff/v4"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/suite"

	lxdtest "maas.io/core/src/maasagent/internal/testing/lxd"
)

type ClientTestSuite struct {
	suite.Suite
	dummyIP   net.IP
	container *lxdtest.LXDContainer
	client    *Client
}

// TestClientTestSuite will run all tests in the ClientTestSuite
// This test suite is a set of integration tests that require isc-dhcp-server.
// TEST_OMAPI_CLIENT=true \
// go test maas.io/core/src/maasagent/internal/dhcpd/omapi -run 'TestClientTestSuite' -count 1 -v
// You can use optional TEST_OMAPI_CLIENT_DUMMY_IP variable to set a different IP.
// (default: 192.168.0.1/24)
func TestClientTestSuite(t *testing.T) {
	env := os.Getenv("TEST_OMAPI_CLIENT")
	if env == "" {
		t.Skip("set TEST_OMAPI_CLIENT to run this test")
	}

	suite.Run(t, new(ClientTestSuite))
}

// SetupTest ensures that before each test run we have fresh container with dhcpd.
func (s *ClientTestSuite) SetupTest() {
	// s.T().Name() returns name that is not compatible with LXD
	name := strings.ReplaceAll(s.T().Name(), "/", "-")

	container := lxdtest.NewLXDContainer(s.T(), name, "jammy")

	env := os.Getenv("TEST_OMAPI_CLIENT_DUMMY_IP")
	if env == "" {
		env = "192.168.0.1/24"
	}

	ip, ipnet, err := net.ParseCIDR(env)
	assert.NoError(s.T(), err)

	// Create dummy interface that isc-dhcp-server will listen on
	// because we are not interested in providing DHCP on the network
	dhcpdsetup := fmt.Sprintf(`
ip link add dummy0 type dummy
ip addr add %s dev dummy0
ip link set dummy0 up
apt install -y isc-dhcp-server

cat <<EOF > /etc/default/isc-dhcp-server
INTERFACESv4="dummy0"
EOF

cat <<EOF >> /etc/dhcp/dhcpd.conf
subnet %s netmask %s {
    interface dummy0;
    range %s %s;
}
key omapi_key {
    algorithm hmac-md5;
    secret "a2V5";
}
omapi-port 7911;
omapi-key omapi_key;
EOF

systemctl restart isc-dhcp-server
`, env, ipnet.IP, net.IP(ipnet.Mask), ip, ip)

	container.Exec([]string{"sh", "-c", dhcpdsetup})

	// We know that eth0 exists because of default profile
	address := container.Network()["eth0"].Addresses[0].Address

	// It takes some time for isc-dhcp-server to start OMAPI
	retry := backoff.NewExponentialBackOff()
	retry.MaxElapsedTime = 10 * time.Second

	conn, err := backoff.RetryWithData(func() (net.Conn, error) {
		return net.Dial("tcp", fmt.Sprintf("%s:7911", address))
	}, retry)
	assert.NoError(s.T(), err)

	authenticator := NewHMACMD5Authenticator("omapi_key", "a2V5")

	client, err := NewClient(conn, &authenticator)
	assert.NoError(s.T(), err)

	var ok bool

	s.container = container
	s.dummyIP = ip
	s.client, ok = client.(*Client)

	assert.True(s.T(), ok)
}

// TestClientAddHost verifies the OMAPI client's ability to add and retrieve a host entry.
// The test performs the following steps:
//
// 1. Uses the OMAPI client to create a new host entry with the AddHost method.
// 2. Calls the GetHost method to retrieve the newly created host entry.
// 3. Asserts that the retrieved host entry matches the properties of the host that was created.
func (s *ClientTestSuite) TestClientAddHost() {
	ip := s.dummyIP
	mac := net.HardwareAddr([]byte{0xca, 0xfe, 0xc0, 0xff, 0xee, 0x00})

	err := s.client.AddHost(ip, mac)
	assert.NoError(s.T(), err)

	options := map[string][]byte{"hardware-address": mac}

	host, err := s.client.GetHost(options)
	assert.NoError(s.T(), err)

	assert.Equal(s.T(), ip.To4(), host.IP)
	assert.Equal(s.T(), mac, host.MAC)
}

// TestClientDeleteHost verifies the OMAPI client's functionality for deleting a host.
// It performs the following steps:
//
// 1. Uses the OMAPI client to create a new host entry with the AddHost method.
// 2. Checks the successful creation of the host entry by calling the GetHost.
// 3. Calls the DeleteHost method to remove the previously created host entry.
// 4. Verifies that the host entry has been deleted by making another call to GetHost.
func (s *ClientTestSuite) TestClientDeleteHost() {
	ip := s.dummyIP
	mac := net.HardwareAddr([]byte{0xca, 0xfe, 0xc0, 0xff, 0xee, 0x00})

	err := s.client.AddHost(ip, mac)
	assert.NoError(s.T(), err)

	options := map[string][]byte{"hardware-address": mac}

	host, err := s.client.GetHost(options)
	assert.NoError(s.T(), err)

	assert.Equal(s.T(), ip.To4(), host.IP)

	err = s.client.DeleteHost(mac)
	assert.NoError(s.T(), err)

	_, err = s.client.GetHost(options)
	assert.EqualError(s.T(), err, "host lookup failed: no object matches specification")
}

func TestHostMarshalJSON(t *testing.T) {
	h := Host{
		Hostname: "localhost",
		IP:       net.IPv4(127, 0, 0, 1),
		MAC:      net.HardwareAddr{0xCA, 0xFE, 0xBA, 0xBE, 0x00, 0x00},
	}

	marshaled, err := json.Marshal(h)
	if err != nil {
		assert.NoError(t, err)
	}

	assert.Equal(t,
		`{"hostname":"localhost","ip":"127.0.0.1","mac":"ca:fe:ba:be:00:00"}`,
		string(marshaled),
	)
}

func TestHostUnmarshalJSON(t *testing.T) {
	input := `{"hostname":"localhost","ip":"127.0.0.1","mac":"CA:FE:BA:BE:00:00"}`
	expected := Host{
		Hostname: "localhost",
		IP:       net.IPv4(127, 0, 0, 1),
		MAC:      net.HardwareAddr{0xCA, 0xFE, 0xBA, 0xBE, 0x00, 0x00},
	}

	var h Host

	err := json.Unmarshal([]byte(input), &h)
	assert.NoError(t, err)

	assert.Equal(t, expected, h)
}
