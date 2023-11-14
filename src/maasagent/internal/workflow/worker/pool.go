package worker

import (
	"context"
	"fmt"
	"sync"
	"time"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/temporal"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"
)

const (
	defaultAddWorkerWorkflowName     = "add-worker"
	defaultRemoveWorkerWorkflowName  = "remove-worker"
	defaultConfigurePoolWorkflowName = "configure-worker-pool"
	defaultControlPlaneTaskQueueName = "control-plane"
)

// WorkerPool contains a collection of Temporal Workers that can be added or
// removed during runtime by main worker which is responsible for execution of
// special workflows `add-worker` and `remove-worker`.
type WorkerPool struct {
	fatal  chan error
	client client.Client
	// worker for control plane workflows like Add or Remove workers
	main                      worker.Worker
	workers                   map[string]worker.Worker
	allowedWorkflows          map[string]interface{}
	allowedActivities         map[string]interface{}
	systemID                  string
	taskQueue                 string
	addWorkerWorkflowName     string
	removeWorkerWorkflowName  string
	configurePoolWorkflowName string
	controlPlaneTaskQueueName string
	mutex                     sync.Mutex
}

// NewWorkerPool returns WorkerPool that has a main worker listening to a
// Temporal Task Queue named after systemID@main
func NewWorkerPool(systemID string, client client.Client,
	options ...WorkerPoolOption) *WorkerPool {
	pool := &WorkerPool{
		systemID:                  systemID,
		taskQueue:                 fmt.Sprintf("%s@main", systemID),
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

	// main worker is responsible for adding/removing workers to/from the pool
	pool.main = worker.New(client, pool.taskQueue, worker.Options{
		DisableRegistrationAliasing: true,
		OnFatalError:                func(err error) { pool.fatal <- err },
	})

	pool.main.RegisterWorkflowWithOptions(
		exec[addWorkerParam](pool.addWorker),
		workflow.RegisterOptions{
			Name: pool.addWorkerWorkflowName,
		},
	)

	pool.main.RegisterWorkflowWithOptions(
		exec[removeWorkerParam](pool.removeWorker),
		workflow.RegisterOptions{
			Name: pool.removeWorkerWorkflowName,
		},
	)

	return pool
}

// Start starts the main worker process that controls worker pool
func (p *WorkerPool) Start() error {
	return p.main.Start()
}

func (p *WorkerPool) Error() chan error {
	return p.fatal
}

// WorkerPoolOption allows to set additional WorkerPool options
type WorkerPoolOption func(*WorkerPool)

// WithAddWorkerWorkflowName sets custom addWorkerWorkflowName
// (default: "add-worker")
func WithAddWorkerWorkflowName(s string) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.addWorkerWorkflowName = s
	}
}

// WithRemoveWorkerWorkflowName sets custom removeWorkerWorkflowName
// (default: "remove-worker")
func WithRemoveWorkerWorkflowName(s string) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.removeWorkerWorkflowName = s
	}
}

// WithConfigurePoolWorkflowName sets custom configurePoolWorkflowName
// (default: "configure-worker-pool")
func WithConfigurePoolWorkflowName(s string) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.configurePoolWorkflowName = s
	}
}

// WithControlPlaneTaskQueueName sets custom controlPlaneTaskQueueName
// (default: "control-plane")
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

// WithMainWorkerTaskQueueSuffix sets main worker Task Queue suffix
// Main TaskQueue has format: {systemID}@{suffix}
// (default: "main")
func WithMainWorkerTaskQueueSuffix(s string) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.taskQueue = fmt.Sprintf("%s@%s", p.systemID, s)
	}
}

// configureWorkerPoolParam is a parameter that should be provided to the
// `configure-worker-pool` workflow
type configureWorkerPoolParam struct {
	SystemID  string `json:"system_id"`
	TaskQueue string `json:"task_queue"`
}

// Configure calls `configure-worker-pool` workflow to be executed.
// This workflow will configure WorkerPool with a proper set of workers.
func (p *WorkerPool) Configure(ctx context.Context) error {
	workflowOptions := client.StartWorkflowOptions{
		TaskQueue: p.controlPlaneTaskQueueName,
		// If we failed to execute this workflow in 120 seconds, then something bad
		// is going on and we don't want to keep it in a task queue.
		WorkflowExecutionTimeout: 120 * time.Second,
	}

	workflowRun, err := p.client.ExecuteWorkflow(ctx, workflowOptions,
		p.configurePoolWorkflowName, configureWorkerPoolParam{
			SystemID:  p.systemID,
			TaskQueue: p.taskQueue,
		})
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
		DisableRegistrationAliasing: true,
		OnFatalError:                func(err error) { p.fatal <- err },
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
			fmt.Sprintf("failed registering %s. %q is not allowed", t, val),
			fmt.Sprintf("%sNotAllowed", t),
			nil,
		)
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

// exec returns workflow that executes provided function as Local Activity
func exec[T any](fn any) func(ctx workflow.Context, param T) error {
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
	return temporal.NewNonRetryableApplicationError(
		fmt.Sprintf("worker for task queue %q already exists", taskQueue),
		"failedToAddWorker", nil)
}

// failedToRemoveWorkerError returns a non retryable error
func failedToRemoveWorkerError(taskQueue string) error {
	return temporal.NewNonRetryableApplicationError(
		fmt.Sprintf("worker for task queue %q doesn't exist", taskQueue),
		"failedToRemoveWorker", nil)
}

// failedToStartWorkerError returns a non retryable error
func failedToStartWorkerError(err error) error {
	return temporal.NewNonRetryableApplicationError("failed to start worker",
		"failedToStartWorker", err)
}
