package worker

import (
	"testing"

	"github.com/stretchr/testify/assert"
	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"
)

type fakeWorker struct{}

func (w *fakeWorker) Start() error { return nil }

func (w *fakeWorker) Run(<-chan interface{}) error { return nil }

func (w *fakeWorker) Stop() {}

func (w *fakeWorker) RegisterWorkflow(interface{}) {}

func (w *fakeWorker) RegisterWorkflowWithOptions(interface{}, workflow.RegisterOptions) {}

func (w *fakeWorker) RegisterActivity(interface{}) {}

func (w *fakeWorker) RegisterActivityWithOptions(interface{}, activity.RegisterOptions) {}

var (
	fakeWorkerConstructor = func(c client.Client, tq string,
		opts worker.Options) worker.Worker {
		return &fakeWorker{}
	}
)

func TestWorkerPoolConfigurationOverwrite(t *testing.T) {
	pool := NewWorkerPool("systemID", nil, WithWorkerConstructor(fakeWorkerConstructor))
	pool.workers["tq1"] = &fakeWorker{}
	pool.workers["tq2"] = &fakeWorker{}
	pool.workers["tq3"] = &fakeWorker{}
	assert.Equal(t, 3, len(pool.workers))

	err := pool.configure([]configureParam{
		{TaskQueue: "tq1new"},
		{TaskQueue: "tq2new"},
	})

	assert.NoError(t, err)
	assert.Equal(t, 2, len(pool.workers))
}

func TestWorkerPoolConfiguration(t *testing.T) {
	testcases := map[string]struct {
		pool *WorkerPool
		in   []configureParam
		out  int
		err  string
	}{
		"with allowed activity and workflow": {
			pool: NewWorkerPool("systemID", nil,
				WithWorkerConstructor(fakeWorkerConstructor),
				WithAllowedWorkflows(map[string]interface{}{"workflow": nil}),
				WithAllowedActivities(map[string]interface{}{"activity": nil}),
			),
			in: []configureParam{
				{
					TaskQueue:  "tq",
					Workflows:  []string{"workflow"},
					Activities: []string{"activity"},
				},
			},
			out: 1,
			err: "",
		},
		"with allowed activity and not allowed workflow": {
			pool: NewWorkerPool("systemID", nil,
				WithWorkerConstructor(fakeWorkerConstructor),
				WithAllowedActivities(map[string]interface{}{"activity": nil}),
			),
			in: []configureParam{
				{
					TaskQueue:  "tq",
					Workflows:  []string{"workflow"},
					Activities: []string{"activity"},
				},
			},
			out: 0,
			err: "workflowNotAllowed",
		},
		"with allowed workflow and not allowed activity": {
			pool: NewWorkerPool("systemID", nil,
				WithWorkerConstructor(fakeWorkerConstructor),
				WithAllowedWorkflows(map[string]interface{}{"workflow": nil}),
			),
			in: []configureParam{
				{
					TaskQueue:  "tq",
					Workflows:  []string{"workflow"},
					Activities: []string{"activity"},
				},
			},
			out: 0,
			err: "activityNotAllowed",
		},
		"multiple task queues": {
			pool: NewWorkerPool("systemID", nil,
				WithWorkerConstructor(fakeWorkerConstructor),
				WithAllowedWorkflows(map[string]interface{}{
					"workflow1": nil,
					"workflow2": nil,
				}),
				WithAllowedActivities(map[string]interface{}{
					"activity1": nil,
					"activity2": nil,
				}),
			),
			in: []configureParam{
				{
					TaskQueue:  "tq1",
					Workflows:  []string{"workflow1"},
					Activities: []string{"activity1"},
				},
				{
					TaskQueue:  "tq2",
					Workflows:  []string{"workflow2"},
					Activities: []string{"activity2"},
				},
			},
			out: 2,
			err: "",
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			err := tc.pool.configure(tc.in)
			if tc.err != "" {
				assert.Equal(t, tc.err, err.(*temporal.ApplicationError).Type())
			}
			assert.Equal(t, tc.out, len(tc.pool.workers))
		})
	}
}
