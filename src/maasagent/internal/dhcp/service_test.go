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
	"encoding/base64"
	"errors"
	"net"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/suite"
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/testsuite"
	tworkflow "go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/dhcpd/omapi"
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

type DHCPServiceTestSuite struct {
	suite.Suite
	env                    *testsuite.TestWorkflowEnvironment
	activity               *testsuite.TestActivityEnvironment
	svc                    *DHCPService
	configureViaOMAPICalls [][]any
	omapiPipe              net.Conn
	testsuite.WorkflowTestSuite
}

func (s *DHCPServiceTestSuite) SetupTest() {
	logger := log.NewZerologAdapter(zerolog.Nop())
	s.SetLogger(logger)

	s.env = s.NewTestWorkflowEnvironment()
	s.activity = s.NewTestActivityEnvironment()

	client, server := net.Pipe()

	s.omapiPipe = server

	s.configureViaOMAPICalls = [][]any{}

	s.svc = NewDHCPService(
		s.T().Name(),
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
	)

	s.env.RegisterWorkflowWithOptions(MockConfigureDHCPForAgent,
		tworkflow.RegisterOptions{
			Name: "configure-dhcp-for-agent",
		})

	s.activity.RegisterActivityWithOptions(s.svc.configureViaOMAPI,
		activity.RegisterOptions{
			Name: "configure-dhcp-via-omapi",
		})
}

func TestDHCPServiceTestSuite(t *testing.T) {
	suite.Run(t, new(DHCPServiceTestSuite))
}

func (s *DHCPServiceTestSuite) TestConfigurationWorkflowEnabled() {
	s.env.ExecuteWorkflow(s.svc.configure,
		DHCPServiceConfigParam{Enabled: true})

	s.True(s.env.IsWorkflowCompleted())
	s.NoError(s.env.GetWorkflowError())
	s.True(s.svc.running.Load())
}

func (s *DHCPServiceTestSuite) TestConfigurationWorkflowDisabled() {
	s.env.ExecuteWorkflow(s.svc.configure,
		DHCPServiceConfigParam{Enabled: false})

	s.True(s.env.IsWorkflowCompleted())
	s.NoError(s.env.GetWorkflowError())
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

	_, err := s.activity.ExecuteActivity(
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

	_, err := s.activity.ExecuteActivity(
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

	_, err := s.activity.ExecuteActivity(
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

	_, err := s.activity.ExecuteActivity(
		"configure-dhcp-via-omapi",
		ApplyConfigViaOMAPIParam{
			Secret: secret,
			Hosts:  hosts,
		},
	)

	s.Equal(errors.Unwrap(err).Error(), ErrV6NotActive.Error())
}
