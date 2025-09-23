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

package dhcp

import (
	"context"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/canonical/lxd/lxd/db/schema"
	"github.com/canonical/microcluster/v2/microcluster"
	"github.com/canonical/microcluster/v2/state"
	"github.com/insomniacslk/dhcp/dhcpv4"
	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/stretchr/testify/suite"
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/testsuite"
	tworkflow "go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/apiclient"
	"maas.io/core/src/maasagent/internal/cluster"
	"maas.io/core/src/maasagent/internal/dhcpd"
	"maas.io/core/src/maasagent/internal/dhcpd/omapi"
	"maas.io/core/src/maasagent/internal/servicecontroller"
	"maas.io/core/src/maasagent/internal/workflow/log"
)

func MockConfigureDHCPForAgent(ctx tworkflow.Context, args map[string]any) error {
	return nil
}

type mockOMAPIClient struct {
	omapi.OMAPI
	assertAddHost func(net.IP, net.HardwareAddr) error
}

func (m *mockOMAPIClient) Close() error {
	return nil
}

func (m *mockOMAPIClient) AddHost(ip net.IP, mac net.HardwareAddr) error {
	return m.assertAddHost(ip, mac)
}

type MockDHCPController struct {
	restarted bool
}

func NewMockDHCPController(service string) *MockDHCPController {
	return &MockDHCPController{}
}

func (m *MockDHCPController) Start(ctx context.Context) error {
	return nil
}

func (m *MockDHCPController) Stop(ctx context.Context) error {
	return nil
}

func (m *MockDHCPController) Restart(ctx context.Context) error {
	m.restarted = true
	return nil
}

func (m *MockDHCPController) Status(ctx context.Context) (servicecontroller.ServiceStatus, error) {
	return 0, nil
}

var writeConfigFileTest = writeConfigFileSnap

type DHCPServiceTestSuite struct {
	suite.Suite
	workflowEnv            *testsuite.TestWorkflowEnvironment
	activityEnv            *testsuite.TestActivityEnvironment
	svc                    *DHCPService
	configureViaOMAPICalls [][]any
	configureViaFileCalls  [][]any
	omapiPipe              net.Conn
	configHTTPServer       *httptest.Server
	configAPIResponse      []byte
	testsuite.WorkflowTestSuite
}

func (s *DHCPServiceTestSuite) SetupTest() {
	logger := log.NewZerologAdapter(zerolog.Nop())
	s.SetLogger(logger)

	s.workflowEnv = s.NewTestWorkflowEnvironment()
	s.activityEnv = s.NewTestActivityEnvironment()

	client, server := net.Pipe()

	s.omapiPipe = server

	s.configureViaOMAPICalls = [][]any{}
	s.configureViaFileCalls = [][]any{}

	s.configHTTPServer = httptest.NewServer(http.HandlerFunc(func(rw http.ResponseWriter,
		req *http.Request) {
		reqURL := fmt.Sprintf("/agents/%s/services/dhcp/config", s.T().Name())
		assert.Equal(s.T(), reqURL, req.URL.String())
		assert.Equal(s.T(), http.MethodGet, req.Method)
		rw.Write(s.configAPIResponse)
	}))

	configBaseURL, err := url.Parse(s.configHTTPServer.URL)
	if err != nil {
		s.T().Fatal(err)
	}

	apiClient := apiclient.NewAPIClient(configBaseURL, s.configHTTPServer.Client())
	dataPath := s.T().TempDir()

	serviceV4 := servicecontroller.GetServiceName(servicecontroller.DHCPv4)
	mockControllerV4 := NewMockDHCPController(serviceV4)
	serviceV6 := servicecontroller.GetServiceName(servicecontroller.DHCPv6)
	mockControllerV6 := NewMockDHCPController(serviceV6)

	writeConfigFile = writeConfigFileTest

	s.svc = NewDHCPService(
		s.T().Name(),
		mockControllerV4,
		mockControllerV6,
		false,
		WithOMAPIConnFactory(func(_ string, _ string) (net.Conn, error) {
			return client, nil
		}),
		WithOMAPIClientFactory(func(_ net.Conn, _ omapi.Authenticator) (omapi.OMAPI, error) {
			return &mockOMAPIClient{
				assertAddHost: func(ip net.IP, mac net.HardwareAddr) error {
					s.configureViaOMAPICalls = append(s.configureViaOMAPICalls, []any{ip, mac})
					return nil
				},
			}, nil
		}),
		WithAPIClient(apiClient),
		WithDataPathFactory(func(path string) string {
			return filepath.Join(dataPath, path)
		}),
	)
	if err != nil {
		s.T().Fatal(err)
	}

	s.workflowEnv.RegisterWorkflowWithOptions(MockConfigureDHCPForAgent,
		tworkflow.RegisterOptions{
			Name: "configure-dhcp-for-agent",
		})

	s.activityEnv.RegisterActivityWithOptions(s.svc.configureViaOMAPI,
		activity.RegisterOptions{
			Name: "configure-dhcp-via-omapi",
		})

	s.activityEnv.RegisterActivityWithOptions(s.svc.configureViaFile,
		activity.RegisterOptions{
			Name: "configure-dhcp-via-file",
		})

	s.activityEnv.RegisterActivityWithOptions(s.svc.restartService,
		activity.RegisterOptions{
			Name: "restart-dhcp-service",
		})
}

func (s *DHCPServiceTestSuite) TearDownTest() {
	s.configHTTPServer.Close()
}

func TestDHCPServiceTestSuite(t *testing.T) {
	suite.Run(t, new(DHCPServiceTestSuite))
}

func (s *DHCPServiceTestSuite) TestConfigurationWorkflowEnabled() {
	s.workflowEnv.ExecuteWorkflow(s.svc.configure,
		DHCPServiceConfigParam{Enabled: true})

	s.True(s.workflowEnv.IsWorkflowCompleted())
	s.NoError(s.workflowEnv.GetWorkflowError())
	s.True(s.svc.running.Load())
}

func (s *DHCPServiceTestSuite) TestConfigurationWorkflowDisabled() {
	s.workflowEnv.ExecuteWorkflow(s.svc.configure,
		DHCPServiceConfigParam{Enabled: false})

	s.True(s.workflowEnv.IsWorkflowCompleted())
	s.NoError(s.workflowEnv.GetWorkflowError())
	s.False(s.svc.running.Load())
}

func (s *DHCPServiceTestSuite) TestConfigureViaOMAPIV4() {
	secret := base64.StdEncoding.EncodeToString([]byte("abc"))

	hosts := []Host{
		{
			IP:  net.ParseIP("10.0.0.1"),
			MAC: net.HardwareAddr{0x00, 0x01, 0x02, 0x03, 0x04, 0x05},
		},
		{
			IP:  net.ParseIP("10.0.0.2"),
			MAC: net.HardwareAddr{0x00, 0x01, 0x02, 0x03, 0x04, 0x06},
		},
	}

	s.svc.runningV4.Store(true)

	_, err := s.activityEnv.ExecuteActivity(
		"configure-dhcp-via-omapi",
		ApplyConfigViaOMAPIParam{
			Secret: secret,
			Hosts:  hosts,
		},
	)

	s.NoError(err)

	for i, call := range s.configureViaOMAPICalls {
		ip, ok := call[0].(net.IP)

		s.True(ok)

		mac, ok := call[1].(net.HardwareAddr)

		s.True(ok)

		s.Equal(hosts[i].IP, ip)
		s.Equal(hosts[i].MAC, mac)
	}
}

func (s *DHCPServiceTestSuite) TestConfigureViaOMAPIV6() {
	secret := base64.StdEncoding.EncodeToString([]byte("abc"))

	hosts := []Host{
		{
			IP:  net.ParseIP("::1"),
			MAC: net.HardwareAddr{0x00, 0x01, 0x02, 0x03, 0x04, 0x05},
		},
		{
			IP:  net.ParseIP("::2"),
			MAC: net.HardwareAddr{0x00, 0x01, 0x02, 0x03, 0x04, 0x06},
		},
	}

	s.svc.runningV6.Store(true)

	_, err := s.activityEnv.ExecuteActivity(
		"configure-dhcp-via-omapi",
		ApplyConfigViaOMAPIParam{
			Secret: secret,
			Hosts:  hosts,
		},
	)

	s.NoError(err)

	for i, call := range s.configureViaOMAPICalls {
		ip, ok := call[0].(net.IP)

		s.True(ok)

		mac, ok := call[1].(net.HardwareAddr)

		s.True(ok)

		s.Equal(hosts[i].IP, ip)
		s.Equal(hosts[i].MAC, mac)
	}
}

func (s *DHCPServiceTestSuite) TestConfigureViaOMAPINotRunningV4() {
	secret := base64.StdEncoding.EncodeToString([]byte("abc"))

	hosts := []Host{
		{
			IP:  net.ParseIP("10.0.0.1"),
			MAC: net.HardwareAddr{0x00, 0x01, 0x02, 0x03, 0x04, 0x05},
		},
		{
			IP:  net.ParseIP("10.0.0.2"),
			MAC: net.HardwareAddr{0x00, 0x01, 0x02, 0x03, 0x04, 0x06},
		},
	}

	_, err := s.activityEnv.ExecuteActivity(
		"configure-dhcp-via-omapi",
		ApplyConfigViaOMAPIParam{
			Secret: secret,
			Hosts:  hosts,
		},
	)

	s.Equal(errors.Unwrap(err).Error(), ErrV4NotActive.Error())
}

func (s *DHCPServiceTestSuite) TestConfigureViaOMAPINotRunningV6() {
	secret := base64.StdEncoding.EncodeToString([]byte("abc"))

	hosts := []Host{
		{
			IP:  net.ParseIP("::1"),
			MAC: net.HardwareAddr{0x00, 0x01, 0x02, 0x03, 0x04, 0x05},
		},
		{
			IP:  net.ParseIP("::2"),
			MAC: net.HardwareAddr{0x00, 0x01, 0x02, 0x03, 0x04, 0x06},
		},
	}

	_, err := s.activityEnv.ExecuteActivity(
		"configure-dhcp-via-omapi",
		ApplyConfigViaOMAPIParam{
			Secret: secret,
			Hosts:  hosts,
		},
	)

	s.Equal(errors.Unwrap(err).Error(), ErrV6NotActive.Error())
}

func (s *DHCPServiceTestSuite) TestConfigureViaOMAPIV4NoErrorHostAlreadyExisting() {
	secret := base64.StdEncoding.EncodeToString([]byte("abc"))

	hosts := []Host{
		{
			IP:  net.ParseIP("10.0.0.1"),
			MAC: net.HardwareAddr{0x00, 0x01, 0x02, 0x03, 0x04, 0x05},
		},
	}

	s.svc.runningV4.Store(true)
	s.svc.omapiClientFactory = func(_ net.Conn, _ omapi.Authenticator) (omapi.OMAPI, error) {
		return &mockOMAPIClient{
			assertAddHost: func(ip net.IP, mac net.HardwareAddr) error {
				s.configureViaOMAPICalls = append(s.configureViaOMAPICalls, []any{ip, mac})
				return omapi.ErrHostAlreadyExists
			},
		}, nil
	}
	_, err := s.activityEnv.ExecuteActivity(
		"configure-dhcp-via-omapi",
		ApplyConfigViaOMAPIParam{
			Secret: secret,
			Hosts:  hosts,
		},
	)

	s.NoError(err)
}

func (s *DHCPServiceTestSuite) TestConfigureViaOMAPIV6NoErrorHostAlreadyExisting() {
	secret := base64.StdEncoding.EncodeToString([]byte("abc"))

	hosts := []Host{
		{
			IP:  net.ParseIP("::1"),
			MAC: net.HardwareAddr{0x00, 0x01, 0x02, 0x03, 0x04, 0x05},
		},
	}

	s.svc.runningV6.Store(true)
	s.svc.omapiClientFactory = func(_ net.Conn, _ omapi.Authenticator) (omapi.OMAPI, error) {
		return &mockOMAPIClient{
			assertAddHost: func(ip net.IP, mac net.HardwareAddr) error {
				s.configureViaOMAPICalls = append(s.configureViaOMAPICalls, []any{ip, mac})
				return omapi.ErrHostAlreadyExists
			},
		}, nil
	}
	_, err := s.activityEnv.ExecuteActivity(
		"configure-dhcp-via-omapi",
		ApplyConfigViaOMAPIParam{
			Secret: secret,
			Hosts:  hosts,
		},
	)

	s.NoError(err)
}

// TestConfigureViaFile ensures that provided JSON decoded and written
// properly into corresponding files.
func (s *DHCPServiceTestSuite) TestConfigureViaFile() {
	config := `{
    "dhcpd": "Y29uZmlndXJhdGlvbl92NA==",
    "dhcpd_interfaces": "aW50ZXJmYWNlc192NA==",
    "dhcpd6": "Y29uZmlndXJhdGlvbl92Ng==",
    "dhcpd6_interfaces": "aW50ZXJmYWNlc192Ng=="
  }`

	s.configAPIResponse = []byte(config)
	_, err := s.activityEnv.ExecuteActivity(
		"configure-dhcp-via-file",
	)

	assert.NoError(s.T(), err)

	results := map[string]string{
		"dhcpd.conf":        "configuration_v4",
		"dhcpd-interfaces":  "interfaces_v4",
		"dhcpd6.conf":       "configuration_v6",
		"dhcpd6-interfaces": "interfaces_v6",
	}

	for k, v := range results {
		data, err := os.ReadFile(s.svc.dataPathFactory(k))
		if err != nil {
			s.T().Error(err)
		}

		assert.Equal(s.T(), []byte(v), data)
	}
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

func (s *DHCPServiceTestSuite) TestRestartDHCPServiceV4() {
	controllerV4 := s.svc.controllerV4.(*MockDHCPController)

	// DHCP V4 controller expected to restart
	s.svc.runningV4.Store(true)

	_, err := s.activityEnv.ExecuteActivity(
		"restart-dhcp-service",
	)
	s.NoError(err)
	s.True(controllerV4.restarted)

	// DHCP V4 controller not expected to restart
	controllerV4.restarted = false
	s.svc.runningV4.Store(false)

	_, err = s.activityEnv.ExecuteActivity(
		"restart-dhcp-service",
	)
	s.NoError(err)
	s.False(controllerV4.restarted)
}

func (s *DHCPServiceTestSuite) TestRestartDHCPServiceV6() {
	controllerV6 := s.svc.controllerV6.(*MockDHCPController)

	// DHCP V6 controller expected to restart
	s.svc.runningV6.Store(true)

	_, err := s.activityEnv.ExecuteActivity(
		"restart-dhcp-service",
	)
	s.NoError(err)
	s.True(controllerV6.restarted)

	// DHCP V4 controller not expected to restart
	controllerV6.restarted = false
	s.svc.runningV6.Store(false)

	_, err = s.activityEnv.ExecuteActivity(
		"restart-dhcp-service",
	)
	s.NoError(err)
	s.False(controllerV6.restarted)
}

type mockRoundTripper struct {
	calledOnce bool
	Error      error
	Responses  []*http.Response
}

func (m *mockRoundTripper) RoundTrip(req *http.Request) (*http.Response, error) {
	defer func() {
		if !m.calledOnce {
			m.calledOnce = true
		}
	}()

	if m.Error != nil && (len(m.Responses) == 0 || !m.calledOnce) {
		return nil, m.Error
	}

	if m.Error == nil && len(m.Responses) == 0 {
		//nolint:nilnil // this is fine for this fixture
		return nil, nil
	}

	resp := m.Responses[0]

	if len(m.Responses) > 1 {
		m.Responses = m.Responses[:len(m.Responses)-1]
	}

	return resp, nil
}

func TestQueueFlush(t *testing.T) {
	dummyURL := &url.URL{
		Scheme: "http",
		Host:   "localhost:8888",
	}

	testcases := map[string]struct {
		notifications []*dhcpd.Notification
		apiClient     *apiclient.APIClient
		interval      time.Duration
		err           error
	}{
		"successful request": {
			notifications: []*dhcpd.Notification{

				{
					IP:  "10.0.0.1",
					MAC: "00:00:00:00:00",
				},
			},
			apiClient: apiclient.NewAPIClient(
				dummyURL,
				&http.Client{
					Transport: &mockRoundTripper{
						Responses: []*http.Response{
							{
								StatusCode: http.StatusNoContent,
							},
						},
					},
				},
			),
			interval: time.Second,
		},
		"retry once": {
			notifications: []*dhcpd.Notification{

				{
					IP:  "10.0.0.1",
					MAC: "00:00:00:00:00",
				},
			},
			apiClient: apiclient.NewAPIClient(
				dummyURL,
				&http.Client{
					Transport: &mockRoundTripper{
						Error: http.ErrServerClosed,
						Responses: []*http.Response{
							{
								StatusCode: http.StatusNoContent,
							},
						},
					},
				},
			),
			interval: time.Second,
		},
		"max retries": {
			err: http.ErrServerClosed,
			apiClient: apiclient.NewAPIClient(
				dummyURL,
				&http.Client{
					Transport: &mockRoundTripper{
						Error: http.ErrServerClosed,
					},
				},
			),
			interval: time.Second,
		},
		"bad status": {
			err: ErrFailedToPostNotifications,
			apiClient: apiclient.NewAPIClient(
				dummyURL,
				&http.Client{
					Transport: &mockRoundTripper{
						Responses: []*http.Response{
							{
								StatusCode: http.StatusInternalServerError,
							},
						},
					},
				},
			),
			interval: time.Second,
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			flush := queueFlush(tc.apiClient, tc.interval)

			err := flush(context.Background(), tc.notifications)
			if err != nil {
				assert.ErrorIs(t, err, tc.err)
				return
			}

			if tc.err != nil {
				t.Error("expected an error to be returned")
			}
		})
	}
}

func TestConfigureDQLite(t *testing.T) {
	testcases := map[string]struct {
		in  ConfigDQLiteParam
		out struct {
			vlans    []Vlan
			subnets  []Subnet
			ipranges []IPRange
			hosts    []HostReservation
		}
		err error
	}{
		"basic": {
			in: ConfigDQLiteParam{
				Vlans: []VLANData{
					{
						ID:  1,
						VID: 0,
						MTU: 1500,
					},
				},
				Subnets: []SubnetData{
					{
						ID:         1,
						GatewayIP:  "10.0.0.1",
						DNSServers: []string{"10.0.0.2"},
						VlanID:     1,
						AllowDNS:   true,
						CIDR:       "10.0.0.0/24",
					},
				},
				Interfaces: []InterfaceData{
					{
						ID:     1,
						Name:   "lo",
						VlanID: 1,
					},
				},
				IPRanges: []IPRangeData{
					{
						ID:       1,
						StartIP:  "10.0.0.100",
						EndIP:    "10.0.0.200",
						Dynamic:  true,
						SubnetID: 1,
					},
				},
				DefaultDNSServers: []string{"1.1.1.1"},
				NTPServers:        []string{"10.0.0.2"},
			},
			out: struct {
				vlans    []Vlan
				subnets  []Subnet
				ipranges []IPRange
				hosts    []HostReservation
			}{
				vlans: []Vlan{
					{
						ID:  1,
						VID: 0,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionInterfaceMTU):       "1500",
							uint16(dhcpv4.OptionIPAddressLeaseTime): "600",
						},
					},
				},
				subnets: []Subnet{
					{
						ID: 1,
						CIDR: &net.IPNet{
							IP:   net.ParseIP("10.0.0.0").To4(),
							Mask: net.CIDRMask(24, 32),
						},
						VlanID:        1,
						AddressFamily: 4,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionSubnetMask):       "ffffff00",
							uint16(dhcpv4.OptionDomainNameServer): "1.1.1.1,10.0.0.2",
							uint16(dhcpv4.OptionNTPServers):       "10.0.0.2",
							uint16(dhcpv4.OptionRouter):           "10.0.0.1",
						},
					},
				},
				ipranges: []IPRange{
					{
						ID:             1,
						StartIP:        net.ParseIP("10.0.0.100"),
						EndIP:          net.ParseIP("10.0.0.200"),
						Size:           101,
						SubnetID:       1,
						FullyAllocated: false,
						Dynamic:        true,
						Options:        make(map[uint16]string),
					},
				},
			},
		},
		"relayed vlan": {
			in: ConfigDQLiteParam{
				Vlans: []VLANData{
					{
						ID:  1,
						VID: 0,
						MTU: 1500,
					}, {
						ID:            2,
						VID:           1,
						MTU:           1500,
						RelayedVLANID: 1,
					},
				},
				Subnets: []SubnetData{
					{
						ID:         1,
						GatewayIP:  "10.0.0.1",
						DNSServers: []string{"10.0.0.2"},
						VlanID:     1,
						AllowDNS:   true,
						CIDR:       "10.0.0.0/24",
					},
				},
				Interfaces: []InterfaceData{
					{
						ID:     1,
						Name:   "lo",
						VlanID: 1,
					},
				},
				IPRanges: []IPRangeData{
					{
						ID:       1,
						StartIP:  "10.0.0.100",
						EndIP:    "10.0.0.200",
						Dynamic:  true,
						SubnetID: 1,
					},
				},
				DefaultDNSServers: []string{"1.1.1.1"},
				NTPServers:        []string{"10.0.0.2"},
			},
			out: struct {
				vlans    []Vlan
				subnets  []Subnet
				ipranges []IPRange
				hosts    []HostReservation
			}{
				vlans: []Vlan{
					{
						ID:  1,
						VID: 0,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionInterfaceMTU):       "1500",
							uint16(dhcpv4.OptionIPAddressLeaseTime): "600",
						},
					}, {
						ID:            2,
						VID:           1,
						RelayedVlanID: 1,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionInterfaceMTU):       "1500",
							uint16(dhcpv4.OptionIPAddressLeaseTime): "600",
						},
					},
				},
				subnets: []Subnet{
					{
						ID: 1,
						CIDR: &net.IPNet{
							IP:   net.ParseIP("10.0.0.0").To4(),
							Mask: net.CIDRMask(24, 32),
						},
						VlanID:        1,
						AddressFamily: 4,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionSubnetMask):       "ffffff00",
							uint16(dhcpv4.OptionDomainNameServer): "1.1.1.1,10.0.0.2",
							uint16(dhcpv4.OptionNTPServers):       "10.0.0.2",
							uint16(dhcpv4.OptionRouter):           "10.0.0.1",
						},
					},
				},
				ipranges: []IPRange{
					{
						ID:             1,
						StartIP:        net.ParseIP("10.0.0.100"),
						EndIP:          net.ParseIP("10.0.0.200"),
						Size:           101,
						SubnetID:       1,
						FullyAllocated: false,
						Dynamic:        true,
						Options:        make(map[uint16]string),
					},
				},
			},
		},
		"multiple subnets": {
			in: ConfigDQLiteParam{
				Vlans: []VLANData{
					{
						ID:  1,
						VID: 0,
						MTU: 1500,
					},
				},
				Subnets: []SubnetData{
					{
						ID:         1,
						GatewayIP:  "10.0.0.1",
						DNSServers: []string{"10.0.0.2"},
						VlanID:     1,
						AllowDNS:   true,
						CIDR:       "10.0.0.0/24",
					}, {
						ID:         2,
						GatewayIP:  "10.0.1.1",
						DNSServers: []string{"10.0.1.2"},
						VlanID:     1,
						AllowDNS:   true,
						CIDR:       "10.0.1.0/24",
					},
				},
				Interfaces: []InterfaceData{
					{
						ID:     1,
						Name:   "lo",
						VlanID: 1,
					},
				},
				IPRanges: []IPRangeData{
					{
						ID:       1,
						StartIP:  "10.0.0.100",
						EndIP:    "10.0.0.200",
						Dynamic:  true,
						SubnetID: 1,
					},
				},
				DefaultDNSServers: []string{"1.1.1.1"},
				NTPServers:        []string{"10.0.0.2"},
			},
			out: struct {
				vlans    []Vlan
				subnets  []Subnet
				ipranges []IPRange
				hosts    []HostReservation
			}{
				vlans: []Vlan{
					{
						ID:  1,
						VID: 0,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionInterfaceMTU):       "1500",
							uint16(dhcpv4.OptionIPAddressLeaseTime): "600",
						},
					},
				},
				subnets: []Subnet{
					{
						ID: 1,
						CIDR: &net.IPNet{
							IP:   net.ParseIP("10.0.0.0").To4(),
							Mask: net.CIDRMask(24, 32),
						},
						VlanID:        1,
						AddressFamily: 4,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionSubnetMask):       "ffffff00",
							uint16(dhcpv4.OptionDomainNameServer): "1.1.1.1,10.0.0.2",
							uint16(dhcpv4.OptionNTPServers):       "10.0.0.2",
							uint16(dhcpv4.OptionRouter):           "10.0.0.1",
						},
					}, {
						ID: 2,
						CIDR: &net.IPNet{
							IP:   net.ParseIP("10.0.1.0").To4(),
							Mask: net.CIDRMask(24, 32),
						},
						VlanID:        1,
						AddressFamily: 4,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionSubnetMask):       "ffffff00",
							uint16(dhcpv4.OptionDomainNameServer): "1.1.1.1,10.0.1.2",
							uint16(dhcpv4.OptionNTPServers):       "10.0.0.2",
							uint16(dhcpv4.OptionRouter):           "10.0.1.1",
						},
					},
				},
				ipranges: []IPRange{
					{
						ID:             1,
						StartIP:        net.ParseIP("10.0.0.100"),
						EndIP:          net.ParseIP("10.0.0.200"),
						Size:           101,
						SubnetID:       1,
						FullyAllocated: false,
						Dynamic:        true,
						Options:        make(map[uint16]string),
					},
				},
			},
		},
		"no dns or ntp": {
			in: ConfigDQLiteParam{
				Vlans: []VLANData{
					{
						ID:  1,
						VID: 0,
						MTU: 1500,
					},
				},
				Subnets: []SubnetData{
					{
						ID:        1,
						GatewayIP: "10.0.0.1",
						VlanID:    1,
						AllowDNS:  false,
						CIDR:      "10.0.0.0/24",
					},
				},
				Interfaces: []InterfaceData{
					{
						ID:     1,
						Name:   "lo",
						VlanID: 1,
					},
				},
				IPRanges: []IPRangeData{
					{
						ID:       1,
						StartIP:  "10.0.0.100",
						EndIP:    "10.0.0.200",
						Dynamic:  true,
						SubnetID: 1,
					},
				},
			},
			out: struct {
				vlans    []Vlan
				subnets  []Subnet
				ipranges []IPRange
				hosts    []HostReservation
			}{
				vlans: []Vlan{
					{
						ID:  1,
						VID: 0,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionInterfaceMTU):       "1500",
							uint16(dhcpv4.OptionIPAddressLeaseTime): "600",
						},
					},
				},
				subnets: []Subnet{
					{
						ID: 1,
						CIDR: &net.IPNet{
							IP:   net.ParseIP("10.0.0.0").To4(),
							Mask: net.CIDRMask(24, 32),
						},
						VlanID:        1,
						AddressFamily: 4,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionSubnetMask): "ffffff00",
							uint16(dhcpv4.OptionRouter):     "10.0.0.1",
						},
					},
				},
				ipranges: []IPRange{
					{
						ID:             1,
						StartIP:        net.ParseIP("10.0.0.100"),
						EndIP:          net.ParseIP("10.0.0.200"),
						Size:           101,
						SubnetID:       1,
						FullyAllocated: false,
						Dynamic:        true,
						Options:        make(map[uint16]string),
					},
				},
			},
		},
		"host reservations": {
			in: ConfigDQLiteParam{
				Vlans: []VLANData{
					{
						ID:  1,
						VID: 0,
						MTU: 1500,
					},
				},
				Subnets: []SubnetData{
					{
						ID:        1,
						GatewayIP: "10.0.0.1",
						VlanID:    1,
						AllowDNS:  false,
						CIDR:      "10.0.0.0/24",
					},
				},
				Interfaces: []InterfaceData{
					{
						ID:     1,
						Name:   "lo",
						VlanID: 1,
					},
				},
				IPRanges: []IPRangeData{
					{
						ID:       1,
						StartIP:  "10.0.0.100",
						EndIP:    "10.0.0.200",
						Dynamic:  true,
						SubnetID: 1,
					},
				},
				HostReservations: []HostData{
					{
						IP:           "10.0.0.4",
						MAC:          "AB:CD:EF:00:11:22",
						Hostname:     "host",
						Domain:       "example.com",
						DomainSearch: []string{"example.com", "test"},
						SubnetID:     1,
					},
				},
			},
			out: struct {
				vlans    []Vlan
				subnets  []Subnet
				ipranges []IPRange
				hosts    []HostReservation
			}{
				vlans: []Vlan{
					{
						ID:  1,
						VID: 0,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionInterfaceMTU):       "1500",
							uint16(dhcpv4.OptionIPAddressLeaseTime): "600",
						},
					},
				},
				subnets: []Subnet{
					{
						ID: 1,
						CIDR: &net.IPNet{
							IP:   net.ParseIP("10.0.0.0").To4(),
							Mask: net.CIDRMask(24, 32),
						},
						VlanID:        1,
						AddressFamily: 4,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionSubnetMask): "ffffff00",
							uint16(dhcpv4.OptionRouter):     "10.0.0.1",
						},
					},
				},
				ipranges: []IPRange{
					{
						ID:             1,
						StartIP:        net.ParseIP("10.0.0.100"),
						EndIP:          net.ParseIP("10.0.0.200"),
						Size:           101,
						SubnetID:       1,
						FullyAllocated: false,
						Dynamic:        true,
						Options:        make(map[uint16]string),
					},
				},
				hosts: []HostReservation{
					{
						ID:         1,
						IPAddress:  net.ParseIP("10.0.0.4"),
						MACAddress: net.HardwareAddr{0xab, 0xcd, 0xef, 0x00, 0x11, 0x22},
						SubnetID:   1,
						Options: map[uint16]string{
							uint16(dhcpv4.OptionHostName):            "host",
							uint16(dhcpv4.OptionDomainName):          "example.com",
							uint16(dhcpv4.OptionDNSDomainSearchList): "example.com,test",
						},
					},
				},
			},
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

			dhcpService := NewDHCPService(
				"abc",
				nil,
				nil,
				true,
				WithDataPathFactory(func(path string) string {
					return filepath.Join(dataPath, path)
				}),
				WithServerStart(func(_ context.Context, _ LeaseReporter) error {
					return nil
				}),
			)

			var currentState state.State

			stateLock := &sync.RWMutex{}

			go app.Start(ctx, microcluster.DaemonArgs{
				Version:          "UNKNOWN",
				Debug:            false,
				ExtensionsSchema: []schema.Update{cluster.SchemaAppendDHCP},
				Hooks: &state.Hooks{
					OnStart: func(ctx context.Context, _ state.State) error {
						defer close(errChan)

						err := app.NewCluster(ctx, clusterName, fmt.Sprintf("127.0.0.1:556%d", i), nil)
						if err != nil {
							errChan <- err
							return nil
						}

						return nil
					},
					PostBootstrap: func(ctx context.Context, s state.State, _ map[string]string) error {
						stateLock.Lock()
						defer stateLock.Unlock()

						currentState = s

						return dhcpService.OnBootstrap(ctx, s)
					},
				},
			})

			err := <-errChan
			require.NoError(t, err)

			err = app.Ready(ctx)
			require.NoError(t, err)

			wfTestSuite := &testsuite.WorkflowTestSuite{}
			env := wfTestSuite.NewTestActivityEnvironment()

			_, err = env.ExecuteLocalActivity(dhcpService.configureDQLite, tc.in)
			if err != nil && tc.err != nil {
				assert.ErrorIs(t, err, tc.err)
				return
			}

			require.NoError(t, err)

			stateLock.RLock()
			defer stateLock.RUnlock()

			err = currentState.Database().Transaction(ctx, func(ctx context.Context, tx *sql.Tx) error {
				for _, expectedVlan := range tc.out.vlans {
					row := tx.QueryRowContext(ctx, "SELECT * FROM vlan WHERE id=$1;", expectedVlan.ID)

					vlan := &Vlan{}

					err = vlan.ScanRow(row)
					if err != nil {
						return err
					}

					err = vlan.LoadOptions(ctx, tx)
					if err != nil {
						return err
					}

					assert.Equal(t, expectedVlan, *vlan)
				}

				for _, expectedSubnet := range tc.out.subnets {
					row := tx.QueryRowContext(ctx, "SELECT * FROM subnet WHERE id=$1;", expectedSubnet.ID)

					subnet := &Subnet{}

					err = subnet.ScanRow(row)
					if err != nil {
						return err
					}

					err = subnet.LoadOptions(ctx, tx)
					if err != nil {
						return err
					}

					assert.Equal(t, expectedSubnet, *subnet)
				}

				for _, expectedIPRange := range tc.out.ipranges {
					row := tx.QueryRowContext(ctx, "SELECT * FROM ip_range WHERE id=$1;", expectedIPRange.ID)

					iprange := &IPRange{}

					err = iprange.ScanRow(row)
					if err != nil {
						return err
					}

					err = iprange.LoadOptions(ctx, tx)
					if err != nil {
						return err
					}

					assert.Equal(t, expectedIPRange, *iprange)
				}

				for _, expectedHost := range tc.out.hosts {
					row := tx.QueryRowContext(ctx, "SELECT * FROM host_reservation WHERE id=$1;", expectedHost.ID)

					host := &HostReservation{}

					err = host.ScanRow(row)
					if err != nil {
						return err
					}

					err = host.LoadOptions(ctx, tx)
					if err != nil {
						return err
					}

					assert.Equal(t, expectedHost, *host)
				}

				return nil
			})

			require.NoError(t, err)
		})

		i++
	}
}
