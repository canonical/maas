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
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/suite"
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/testsuite"
	tworkflow "go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/apiclient"
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

	s.svc = NewDHCPService(
		s.T().Name(),
		mockControllerV4,
		mockControllerV6,
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
