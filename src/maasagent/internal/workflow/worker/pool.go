package worker

import (
	"context"
	"fmt"
	"sync"
	"time"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"

	wf "maas.io/core/src/maasagent/internal/workflow"
)

// WorkerPool contains a collection of Temporal Workers that can be added or
// removed during runtime by master worker which is responsible for execution of
// special workflows `add_worker` and `remove_worker`.
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
// Temporal Task Queue named after systemID
func NewWorkerPool(systemID string, client client.Client) (*WorkerPool, error) {
	pool := &WorkerPool{
		systemID: systemID,
		client:   client,
		workers:  make(map[string]worker.Worker),
		workflows: map[string]interface{}{
			"check_ip":              wf.CheckIP,
			"commission":            wf.Commission,
			"deploy":                wf.Deploy,
			"deployed_os_workflow":  wf.DeployedOS,
			"ephemeral_os_workflow": wf.EphemeralOS,
			"power_on":              wf.PowerOn,
			"power_off":             wf.PowerOff,
			"power_query":           wf.PowerQuery,
			"power_cycle":           wf.PowerCycle,
		},
		activities: map[string]interface{}{
			"switch_boot_order": wf.SwitchBootOrderActivity,
			"power":             wf.PowerActivity,
		},
	}

	// master worker is responsible for adding/removing workers to/from the pool
	pool.master = worker.New(client, systemID, worker.Options{})

	var opts workflow.RegisterOptions
	opts = workflow.RegisterOptions{
		Name: "add_worker",
	}
	pool.master.RegisterWorkflowWithOptions(
		localActivityExec[addWorkerParam](pool.addWorker), opts,
	)

	opts = workflow.RegisterOptions{
		Name: "remove_worker",
	}
	pool.master.RegisterWorkflowWithOptions(
		localActivityExec[removeWorkerParam](pool.removeWorker), opts,
	)

	return pool, pool.master.Start()
}

// configureWorkerPoolParam is a parameter that should be provided to the
// `configure_worker_pool` workflow
type configureWorkerPoolParam struct {
	SystemID string `json:"system_id"`
}

// Configure calls `configure_worker_pool` workflow to be executed.
// This workflow will configure WorkerPool with a proper set of workers.
func (p *WorkerPool) Configure(ctx context.Context) error {
	workflowOptions := client.StartWorkflowOptions{
		TaskQueue: "control_plane",
	}

	workflowRun, err := p.client.ExecuteWorkflow(ctx, workflowOptions,
		"configure_worker_pool", configureWorkerPoolParam{SystemID: p.systemID})
	if err != nil {
		return err
	}

	return workflowRun.Get(ctx, nil)
}

type addWorkerParam struct {
	TaskQueue  string   `json:"task_queue"`
	Workflows  []string `json:"workflows"`
	Activities []string `json:"activities"`
}

// addWorker adds worker to the WorkerPool and registers workflows and activities
func (p *WorkerPool) addWorker(param addWorkerParam) error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	if _, ok := p.workers[param.TaskQueue]; ok {
		return fmt.Errorf("worker for TaskQueue %s is already registered in the pool", param.TaskQueue)
	}

	w := worker.New(p.client, param.TaskQueue, worker.Options{})

	for _, wf := range param.Workflows {
		if fn, ok := p.workflows[wf]; ok {
			w.RegisterWorkflowWithOptions(fn, workflow.RegisterOptions{Name: wf})
		}
	}

	for _, act := range param.Activities {
		if fn, ok := p.activities[act]; ok {
			w.RegisterActivityWithOptions(fn, activity.RegisterOptions{Name: act})
		}
	}

	if err := w.Start(); err != nil {
		return err
	}

	p.workers[param.TaskQueue] = w

	return nil
}

type removeWorkerParam struct {
	TaskQueue string `json:"task_queue"`
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

// localActivityExec will execute provided function as Local Activity
func localActivityExec[T any](fn any) func(ctx workflow.Context, param T) error {
	return func(ctx workflow.Context, param T) error {
		lao := workflow.LocalActivityOptions{
			ScheduleToCloseTimeout: 5 * time.Second,
		}
		ctx = workflow.WithLocalActivityOptions(ctx, lao)

		return workflow.ExecuteLocalActivity(ctx, fn, param).Get(ctx, nil)
	}
}
