package worker

import (
	"context"
	"fmt"
	"os"
	"sync"
	"time"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"
)

const (
	defaultAddWorkerWorkflowName     = "add_worker"
	defaultRemoveWorkerWorkflowName  = "remove_worker"
	defaultConfigurePoolWorkflowName = "configure_worker_pool"
	defaultControlPlaneTaskQueueName = "control_plane"
)

// WorkerPool contains a collection of Temporal Workers that can be added or
// removed during runtime by master worker which is responsible for execution of
// special workflows `add_worker` and `remove_worker`.
type WorkerPool struct {
	fatal  chan error
	client client.Client
	// worker for control plane workflows like Add or Remove workers
	master                    worker.Worker
	workers                   map[string]worker.Worker
	allowedWorkflows          map[string]interface{}
	allowedActivities         map[string]interface{}
	systemID                  string
	addWorkerWorkflowName     string
	removeWorkerWorkflowName  string
	configurePoolWorkflowName string
	controlPlaneTaskQueueName string
	pid                       int
	mutex                     sync.Mutex
}

// NewWorkerPool returns WorkerPool that has a master worker listening to a
// Temporal Task Queue named after systemID
func NewWorkerPool(systemID string, client client.Client,
	options ...WorkerPoolOption) *WorkerPool {
	pool := &WorkerPool{
		systemID:                  systemID,
		pid:                       os.Getpid(),
		client:                    client,
		workers:                   make(map[string]worker.Worker),
		addWorkerWorkflowName:     defaultAddWorkerWorkflowName,
		removeWorkerWorkflowName:  defaultRemoveWorkerWorkflowName,
		configurePoolWorkflowName: defaultConfigurePoolWorkflowName,
		controlPlaneTaskQueueName: defaultControlPlaneTaskQueueName,
	}

	for _, opt := range options {
		opt(pool)
	}

	// master worker is responsible for adding/removing workers to/from the pool
	pool.master = worker.New(client, fmt.Sprintf("agent:%s", systemID), worker.Options{
		Identity:     fmt.Sprintf("%s:master:%d", systemID, pool.pid),
		OnFatalError: func(err error) { pool.fatal <- err },
	})

	pool.master.RegisterWorkflowWithOptions(
		localActivityExec[addWorkerParam](pool.addWorker),
		workflow.RegisterOptions{
			Name: pool.addWorkerWorkflowName,
		},
	)

	pool.master.RegisterWorkflowWithOptions(
		localActivityExec[removeWorkerParam](pool.removeWorker),
		workflow.RegisterOptions{
			Name: pool.removeWorkerWorkflowName,
		},
	)

	return pool
}

// Start starts the master worker process that controls worker pool
func (p *WorkerPool) Start() error {
	return p.master.Start()
}

func (p *WorkerPool) Error() chan error {
	return p.fatal
}

// WorkerPoolOption allows to set additional WorkerPool options
type WorkerPoolOption func(*WorkerPool)

// WithAddWorkerWorkflowName sets custom addWorkerWorkflowName
// (default: "add_worker")
func WithAddWorkerWorkflowName(s string) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.addWorkerWorkflowName = s
	}
}

// WithRemoveWorkerWorkflowName sets custom removeWorkerWorkflowName
// (default: "remove_worker")
func WithRemoveWorkerWorkflowName(s string) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.removeWorkerWorkflowName = s
	}
}

// WithConfigurePoolWorkflowName sets custom configurePoolWorkflowName
// (default: "configure_worker_pool")
func WithConfigurePoolWorkflowName(s string) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.configurePoolWorkflowName = s
	}
}

// WithControlPlaneTaskQueueName sets custom controlPlaneTaskQueueName
// (default: "control_plane")
func WithControlPlaneTaskQueueName(s string) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.controlPlaneTaskQueueName = s
	}
}

// WithAllowedWorkflows sets workflows allowed to be registered
func WithAllowedWorkflows(workflows map[string]interface{}) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.allowedWorkflows = workflows
	}
}

// WithAllowedActivities sets activities allowed to be registered
func WithAllowedActivities(activities map[string]interface{}) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.allowedActivities = activities
	}
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
		ID:        fmt.Sprintf("configure:%s:%d", p.systemID, p.pid),
		TaskQueue: p.controlPlaneTaskQueueName,
	}

	workflowRun, err := p.client.ExecuteWorkflow(ctx, workflowOptions,
		p.configurePoolWorkflowName, configureWorkerPoolParam{SystemID: p.systemID})
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
		return failedToAddWorkerError(param.TaskQueue)
	}

	w := worker.New(p.client, param.TaskQueue, worker.Options{
		Identity:     fmt.Sprintf("%s:%d:%s", p.systemID, p.pid, param.TaskQueue),
		OnFatalError: func(err error) { p.fatal <- err },
	})

	if err := register("workflow", param.Workflows, p.allowedWorkflows,
		func(name string, fn interface{}) {
			w.RegisterWorkflowWithOptions(fn, workflow.RegisterOptions{Name: name})
		}); err != nil {
		return err
	}

	if err := register("activity", param.Activities, p.allowedActivities,
		func(name string, fn interface{}) {
			w.RegisterActivityWithOptions(fn, activity.RegisterOptions{Name: name})
		}); err != nil {
		return err
	}

	if err := w.Start(); err != nil {
		w = nil

		return failedToStartWorkerError(err)
	}

	p.workers[param.TaskQueue] = w

	return nil
}

func register(t string, s []string, allowed map[string]interface{},
	reg func(string, interface{})) error {
	for _, val := range s {
		fn, ok := allowed[val]
		if ok {
			reg(val, fn)
			continue
		}

		return temporal.NewNonRetryableApplicationError(
			fmt.Sprintf("Failed registering %s", t),
			fmt.Sprintf("%sNotAllowed", t),
			fmt.Errorf("%s %q is not allowed", t, val))
	}

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
		return failedToRemoveWorkerError(param.TaskQueue)
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

// failedToAddWorkerError returns a non retryable error
func failedToAddWorkerError(taskQueue string) error {
	return temporal.NewNonRetryableApplicationError("Failed adding worker",
		"failedToAddWorker",
		fmt.Errorf("worker for task queue %q already exists", taskQueue))
}

// failedToRemoveWorkerError returns a non retryable error
func failedToRemoveWorkerError(taskQueue string) error {
	return temporal.NewNonRetryableApplicationError("Failed removing worker",
		"failedToRemoveWorker",
		fmt.Errorf("worker for task queue %q doesn't exist", taskQueue))
}

// failedToStartWorkerError returns a non retryable error
func failedToStartWorkerError(err error) error {
	return temporal.NewNonRetryableApplicationError("Failed to start worker",
		"failedToStartWorker", err)
}
