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

package resolver

import (
	"context"
	"net"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/testsuite"
	"maas.io/core/src/maasagent/internal/workflow/log"
)

type mockHandler struct {
	Handler
}

func (m *mockHandler) SetUpstreams(_ string, _ []string) error {
	return nil
}

func getResolverConfigActivity(_ context.Context) (GetResolverConfigResult, error) {
	return GetResolverConfigResult{}, nil
}

func TestConfigurationWorkflow(t *testing.T) {
	handler := &mockHandler{}
	svc := NewResolverService(handler)

	// test multiple calls
	for i := 0; i < 3; i++ {
		t.Run(t.Name(), func(t *testing.T) {
			wfTestSuite := testsuite.WorkflowTestSuite{}
			logger := log.NewZerologAdapter(zerolog.Nop())
			wfTestSuite.SetLogger(logger)
			env := wfTestSuite.NewTestWorkflowEnvironment()

			env.RegisterActivityWithOptions(getResolverConfigActivity, activity.RegisterOptions{
				Name: "get-resolver-config",
			})

			var bindIPs []string

			ifaces, err := net.Interfaces()
			assert.NoError(t, err)

			for _, iface := range ifaces {
				addrs, err := iface.Addrs()
				assert.NoError(t, err)

				for _, addr := range addrs {
					if addr.String() == "127.0.0.1" || addr.String() == "::1" {
						bindIPs = append(bindIPs, addr.String())
					}
				}
			}

			env.OnActivity("get-resolver-config", mock.Anything, mock.Anything).Return(
				GetResolverConfigResult{
					Enabled: true,
					BindIPs: bindIPs,
					Servers: []string{"127.0.0.1:5353"},
				},
				nil,
			)

			env.ExecuteWorkflow(
				svc.ConfigurationWorkflows()["configure-resolver-service"],
				t.Name(),
			)

			// TODO assert query receives answer once Handler is implemented
			assert.NoError(t, env.GetWorkflowError())
		})
	}
}
