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
	defaultConfigureWorkerPoolWorkflowName = "configure-worker-pool"
	defaultConfigureWorkerPoolActivityName = "configure-worker-pool"
	defaultControlPlaneTaskQueueName       = "control-plane"
)

var (
	defaultWorkerConstructor = worker.New
)

type workerConstructor func(client.Client, string, worker.Options) worker.Worker

// WorkerPool contains a collection of Temporal Workers that can be configured
// at runtime by main worker
type WorkerPool struct {
	fatal  chan error
	client client.Client
	// worker for control plane
	main                            worker.Worker
	workerConstructor               workerConstructor
	workers                         map[string]worker.Worker
	allowedWorkflows                map[string]interface{}
	allowedActivities               map[string]interface{}
	systemID                        string
	taskQueue                       string
	configureWorkerPoolActivityName string
	configureWorkerPoolWorkflowName string
	controlPlaneTaskQueueName       string
	mutex                           sync.Mutex
}

// NewWorkerPool returns WorkerPool that has a main worker polling
// Temporal Task Queue named after systemID@main
func NewWorkerPool(systemID string, client client.Client,
	options ...WorkerPoolOption) *WorkerPool {
	pool := &WorkerPool{
		systemID:                        systemID,
		taskQueue:                       fmt.Sprintf("%s@main", systemID),
		client:                          client,
		workers:                         make(map[string]worker.Worker),
		configureWorkerPoolActivityName: defaultConfigureWorkerPoolActivityName,
		configureWorkerPoolWorkflowName: defaultConfigureWorkerPoolWorkflowName,
		controlPlaneTaskQueueName:       defaultControlPlaneTaskQueueName,
		workerConstructor:               defaultWorkerConstructor,
	}

	for _, opt := range options {
		opt(pool)
	}

	// main worker is responsible for configuring workers in the pool
	pool.main = pool.workerConstructor(client, pool.taskQueue, worker.Options{
		DisableRegistrationAliasing: true,
		OnFatalError:                func(err error) { pool.fatal <- err },
	})

	pool.main.RegisterActivityWithOptions(
		pool.configure,
		activity.RegisterOptions{
			Name: pool.configureWorkerPoolActivityName,
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

// WithConfigureWorkerPoolWorkflowName sets custom configureWorkerPoolWorkflowName
// (default: "configure-worker-pool")
func WithConfigureWorkerPoolWorkflowName(s string) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.configureWorkerPoolWorkflowName = s
	}
}

// WithConfigureWorkerPoolActivityName sets custom configureWorkerPoolActivityName
// (default: "configure-worker-pool")
func WithConfigureWorkerPoolActivityName(s string) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.configureWorkerPoolActivityName = s
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

// WithWorkerConstructor sets constructor function used to construct
// worker.Worker. Can be used to provide alternative constructor for tests
// (default: "worker.New")
func WithWorkerConstructor(fn workerConstructor) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.workerConstructor = fn
	}
}

// configureWorkerPoolParam is a parameter that should be provided to the
// `configure-worker-pool` workflow
type configureWorkerPoolParam struct {
	SystemID string `json:"system_id"`
	// TaskQueue should usually be {systemID}@main
	TaskQueue string `json:"task_queue"`
}

// Configure calls `configure-worker-pool` workflow to be executed.
// This workflow will configure WorkerPool with a proper set of workers.
func (p *WorkerPool) Configure(ctx context.Context) error {
	workflowOptions := client.StartWorkflowOptions{
		TaskQueue: p.controlPlaneTaskQueueName,
		// If we failed to execute this workflow in 120 seconds, then something bad
		// happened and we don't want to keep it in a task queue.
		WorkflowExecutionTimeout: 120 * time.Second,
	}

	workflowRun, err := p.client.ExecuteWorkflow(ctx, workflowOptions,
		p.configureWorkerPoolWorkflowName, configureWorkerPoolParam{
			SystemID:  p.systemID,
			TaskQueue: p.taskQueue,
		})
	if err != nil {
		return err
	}

	return workflowRun.Get(ctx, nil)
}

type configureParam struct {
	TaskQueue  string   `json:"task_queue"`
	Workflows  []string `json:"workflows"`
	Activities []string `json:"activities"`
}

// configure adds requested amount of workers to the WorkerPool
// and each worker registers workflows and activities
func (p *WorkerPool) configure(params []configureParam) error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	// There is no support for incremental changes.
	// Each configuration is applied on a clean state.
	p.cleanup()

	for _, param := range params {
		w := p.workerConstructor(p.client, param.TaskQueue, worker.Options{
			DisableRegistrationAliasing: true,
			OnFatalError:                func(err error) { p.fatal <- err },
		})

		if err := register("workflow", param.Workflows, p.allowedWorkflows,
			func(name string, fn interface{}) {
				w.RegisterWorkflowWithOptions(fn, workflow.RegisterOptions{Name: name})
			}); err != nil {
			p.cleanup()

			return err
		}

		if err := register("activity", param.Activities, p.allowedActivities,
			func(name string, fn interface{}) {
				w.RegisterActivityWithOptions(fn, activity.RegisterOptions{Name: name})
			}); err != nil {
			p.cleanup()

			return err
		}

		if err := w.Start(); err != nil {
			p.cleanup()

			return failedToStartWorkerError(err)
		}

		p.workers[param.TaskQueue] = w
	}

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

// cleanup stops all workers and removes them from the pool
func (p *WorkerPool) cleanup() {
	for k, v := range p.workers {
		v.Stop()
		delete(p.workers, k)
	}
}

// failedToStartWorkerError returns a non retryable error
func failedToStartWorkerError(err error) error {
	return temporal.NewNonRetryableApplicationError("failed to start worker",
		"failedToStartWorker", err)
}
