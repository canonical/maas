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
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/suite"
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/testsuite"
	"maas.io/core/src/maasagent/internal/workflow/log"
)

type DHCPServiceTestSuite struct {
	suite.Suite
	env *testsuite.TestWorkflowEnvironment
	svc *DHCPService
	testsuite.WorkflowTestSuite
}

func (s *DHCPServiceTestSuite) SetupTest() {
	logger := log.NewZerologAdapter(zerolog.Nop())
	s.SetLogger(logger)

	s.env = s.NewTestWorkflowEnvironment()

	s.svc = NewDHCPService(s.T().Name())
	s.env.RegisterActivityWithOptions(s.svc.update,
		activity.RegisterOptions{
			Name: "update-dhcp-configuration",
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
	s.True(s.svc.running)
}

func (s *DHCPServiceTestSuite) TestConfigurationWorkflowDisabled() {
	s.env.ExecuteWorkflow(s.svc.configure,
		DHCPServiceConfigParam{Enabled: false})

	s.True(s.env.IsWorkflowCompleted())
	s.NoError(s.env.GetWorkflowError())
	s.False(s.svc.running)
}
