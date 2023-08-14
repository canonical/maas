package worker

import (
	"context"
	"fmt"
	"sync"
	"time"

	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"

	wf "launchpad.net/maas/maas/src/maasagent/internal/workflow"
)

// WorkerPool contains a collection of Temporal Workers that can be added or
// removed in runtime, through master worker that is responsible for execution of
// special workflows AddWorker and RemoveWorker.
// WorkerPool allows to register specific Workflows and Activities for the
// added workers.
type WorkerPool struct {
	client client.Client
	// worker for control plane workflows like Add or Remove workers
	master worker.Worker
	// collection of workflows allowed for registration
	workflows map[string]interface{}
	// collection of activities allowed for registration
	activities map[string]interface{}
	workers    map[string]worker.Worker
	systemID   string
	mutex      sync.Mutex
}

// NewWorkerPool returns WorkerPool that has a master worker listening to a
// Temporal Task Queue {systemID}
func NewWorkerPool(systemID string, client client.Client) (*WorkerPool, error) {
	pool := &WorkerPool{
		systemID: systemID,
		client:   client,
		workers:  make(map[string]worker.Worker),
		workflows: map[string]interface{}{
			"CheckIP": wf.CheckIP,
		},
		activities: map[string]interface{}{},
	}

	// master worker responsible for adding/removing workers from the pool
	pool.master = worker.New(client, systemID, worker.Options{})

	var opts workflow.RegisterOptions
	opts = workflow.RegisterOptions{
		Name: "AddWorker",
	}
	pool.master.RegisterWorkflowWithOptions(
		exec[addWorkerParam](pool.addWorker), opts,
	)

	opts = workflow.RegisterOptions{
		Name: "RemoveWorker",
	}
	pool.master.RegisterWorkflowWithOptions(
		exec[removeWorkerParam](pool.removeWorker), opts,
	)

	return pool, pool.master.Start()
}

// configureParam is a parameter that should be provided to Configure workflow
type configureParam struct {
	SystemID string
}

// Configure calls Configure workflow to be executed.
// This workflow will configure WorkerPool with a proper set of workers.
// E.g. it will call AddWorker and RemoveWorker workflows.
func (p *WorkerPool) Configure(ctx context.Context) error {
	workflowOptions := client.StartWorkflowOptions{
		TaskQueue: "control-plane",
	}

	workflowRun, err := p.client.ExecuteWorkflow(ctx, workflowOptions,
		"Configure", configureParam{SystemID: p.systemID})
	if err != nil {
		return err
	}

	return workflowRun.Get(ctx, nil)
}

type addWorkerParam struct {
	TaskQueue  string
	Workflows  []string
	Activities []string
}

// addWorker adds worker to the WorkerPool and registers workflows and activities
func (p *WorkerPool) addWorker(param addWorkerParam) error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	if _, ok := p.workers[param.TaskQueue]; ok {
		return fmt.Errorf("worker for TaskQueue %s is already registered in the pool", param.TaskQueue)
	}

	w := worker.New(p.client, param.TaskQueue, worker.Options{})

	for _, workflow := range param.Workflows {
		if fn, ok := p.workflows[workflow]; ok {
			w.RegisterWorkflow(fn)
		}
	}

	for _, activity := range param.Activities {
		if fn, ok := p.activities[activity]; ok {
			w.RegisterActivity(fn)
		}
	}

	if err := w.Start(); err != nil {
		return err
	}

	p.workers[param.TaskQueue] = w

	return nil
}

type removeWorkerParam struct {
	TaskQueue string
}

// removeWorker stops worker of a certain TaskQueue and removes it from the pool
func (p *WorkerPool) removeWorker(param removeWorkerParam) error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	w, ok := p.workers[param.TaskQueue]

	if !ok {
		return nil
	}

	w.Stop()
	delete(p.workers, param.TaskQueue)

	return nil
}

// exec will execute provide function as Local Activity
func exec[T any](fn any) func(ctx workflow.Context, param T) error {
	return func(ctx workflow.Context, param T) error {
		lao := workflow.LocalActivityOptions{
			ScheduleToCloseTimeout: 5 * time.Second,
		}
		ctx = workflow.WithLocalActivityOptions(ctx, lao)

		return workflow.ExecuteLocalActivity(ctx, fn, param).Get(ctx, nil)
	}
}
