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

package cluster

import (
	"context"
	"path/filepath"
	"strings"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.temporal.io/sdk/testsuite"
	"maas.io/core/src/maasagent/internal/workflow/log"
)

func TestConfigurationWorkflow(t *testing.T) {
	systemID := strings.ReplaceAll(t.Name(), "/", "-")
	dataPath := t.TempDir()

	svc, err := NewClusterService(systemID,
		WithDataPathFactory(func(path string) string {
			return filepath.Join(dataPath, path)
		}),
	)

	require.NoError(t, err)

	wfTestSuite := testsuite.WorkflowTestSuite{}
	logger := log.NewZerologAdapter(zerolog.Nop())

	wfTestSuite.SetLogger(logger)
	env := wfTestSuite.NewTestWorkflowEnvironment()

	env.ExecuteWorkflow(svc.ConfigurationWorkflows()["configure-cluster-service"],
		ClusterServiceConfigParam{})
	assert.NoError(t, env.GetWorkflowError())

	_, batch, err := svc.cluster.SQL(context.TODO(), "select name from core_cluster_members")

	assert.NoError(t, err)
	assert.Len(t, batch.Results, 1)
	assert.Equal(t, systemID, batch.Results[0].Rows[0][0])
}
