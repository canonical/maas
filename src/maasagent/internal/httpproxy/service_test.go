package httpproxy

import (
	"context"
	"io"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"testing"

	"github.com/rs/zerolog"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/testsuite"
	"maas.io/core/src/maasagent/internal/cache"
	"maas.io/core/src/maasagent/internal/workflow/log"
)

// We don't have definition of "get-region-endpoints" because this is a workflow
// that is implemented in Python. Because of the limitation of the test library
// we need to introduce a dummy activity to match function signature:
// https://community.temporal.io/t/workflow-unit-tests-questions-why-use-dummy-activities-how-to-ensure-activity-was-not-called-how-to-create-an-instance-of-workflow-context/756
func getRegionEndpointsActivity(_ context.Context) (getRegionEndpointsResult, error) {
	return getRegionEndpointsResult{}, nil
}

func TestConfigurationWorkflow(t *testing.T) {
	// HTTPProxyService Configure workflow might be called multiple times,
	// and we want to ensure that there is no state that we could depend on, or
	// that would lead to errors if Configure workflow is invoked multiple times
	svc := NewHTTPProxyService(t.TempDir(), cache.NewFakeFileCache())

	upstream := httptest.NewServer(http.HandlerFunc(
		func(w http.ResponseWriter, _ *http.Request) {
			w.Write([]byte("hello world"))
		}))

	// Start subsequent calls in their own t.Run(),
	// otherwise Temporal tests will panic with:
	//   Current TestWorkflowEnvironment is used to execute Configure.
	//   Please create a new TestWorkflowEnvironment for Configure.
	// Call it several times, just to ensure we have nothing in the state that we
	// would depend on.
	for i := 0; i < 3; i++ {
		t.Run(t.Name(), func(t *testing.T) {
			wfTestSuite := testsuite.WorkflowTestSuite{}
			logger := log.NewZerologAdapter(zerolog.Nop())
			wfTestSuite.SetLogger(logger)
			env := wfTestSuite.NewTestWorkflowEnvironment()

			env.RegisterActivityWithOptions(getRegionEndpointsActivity, activity.RegisterOptions{
				Name: "get-region-controller-endpoints",
			})

			env.OnActivity("get-region-controller-endpoints", mock.Anything,
				mock.Anything).Return(
				getRegionEndpointsResult{Endpoints: []string{upstream.URL}}, nil)

			env.ExecuteWorkflow(svc.Configure, t.Name())
			assert.NoError(t, env.GetWorkflowError())

			httpc := http.Client{
				Transport: &http.Transport{
					DialContext: func(_ context.Context, _, _ string) (net.Conn, error) {
						return net.Dial("unix", svc.socketPath)
					},
				},
			}

			//nolint:noctx // this is okay not to have a context here
			response, err := httpc.Get("http://unix/")
			assert.NoError(t, err)
			body, err := io.ReadAll(response.Body)
			assert.NoError(t, err)

			assert.Equal(t, []byte("hello world"), body)
		})
	}
}

func TestConfigurationWorkflowWithUnreachableEndpoint(t *testing.T) {
	svc := NewHTTPProxyService(t.TempDir(), cache.NewFakeFileCache())

	nonExistingEndpoint, err := url.Parse("http://maas.invalid:5240")
	assert.NoError(t, err)

	wfTestSuite := testsuite.WorkflowTestSuite{}

	logger := log.NewZerologAdapter(zerolog.Nop())

	wfTestSuite.SetLogger(logger)

	env := wfTestSuite.NewTestWorkflowEnvironment()

	env.RegisterActivityWithOptions(getRegionEndpointsActivity, activity.RegisterOptions{
		Name: "get-region-controller-endpoints",
	})

	env.OnActivity("get-region-controller-endpoints", mock.Anything,
		mock.Anything).Return(
		getRegionEndpointsResult{Endpoints: []string{
			nonExistingEndpoint.String(),
		}}, nil)

	env.ExecuteWorkflow(svc.Configure, t.Name())
	assert.Error(t, env.GetWorkflowError())
	assert.ErrorContains(t, env.GetWorkflowError(), "targets cannot be empty")
}
