package worker

import (
	"fmt"
	"sync"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/client"
	"go.temporal.io/sdk/worker"
	"go.temporal.io/sdk/workflow"
)

var (
	// Override defaultWorkerConstructor using WithWorkerConstructor for tests.
	defaultWorkerConstructor = worker.New
)

// Configurator is an interface that wraps configuration methods.
// Configure will be registered as a Temporal workflow for service configuration.
type Configurator interface {
	// Configure is an entrypoint. It is registered as a Temporal workflow.
	Configure(ctx workflow.Context, systemID string) error
	ConfiguratorName() string
}

type workerConstructor func(client.Client, string, worker.Options) worker.Worker

// WorkerPool contains a collection of Temporal Workers that can be configured
// at runtime by executing workflows on the main worker.
// WithConfigurator can be used to provide additional configuration workflows
// that will be attached to the main worker.
type WorkerPool struct {
	fatal  chan error
	client client.Client
	// worker for control plane
	main              worker.Worker
	workerConstructor workerConstructor
	workers           map[string][]worker.Worker
	configurators     map[string]func(workflow.Context, string) error
	systemID          string
	taskQueue         string
	mutex             sync.Mutex
}

// NewWorkerPool returns WorkerPool that has a main worker polling
// Temporal Task Queue named after systemID@main
// Main worker will execute any configurator workflow provided
func NewWorkerPool(systemID string, client client.Client,
	options ...WorkerPoolOption) *WorkerPool {
	pool := &WorkerPool{
		systemID:          systemID,
		taskQueue:         fmt.Sprintf("%s@main", systemID),
		client:            client,
		workers:           make(map[string][]worker.Worker),
		configurators:     make(map[string]func(workflow.Context, string) error),
		workerConstructor: defaultWorkerConstructor,
	}

	for _, opt := range options {
		opt(pool)
	}

	// main worker is responsible for configuring workers in the pool
	pool.main = pool.workerConstructor(client, pool.taskQueue, worker.Options{
		DisableRegistrationAliasing:            true,
		MaxConcurrentWorkflowTaskPollers:       2,
		MaxConcurrentWorkflowTaskExecutionSize: 2,
		// Used to catch runtime errors from main
		OnFatalError: func(err error) { pool.fatal <- err },
	})

	for k, configurator := range pool.configurators {
		pool.main.RegisterWorkflowWithOptions(
			configurator,
			workflow.RegisterOptions{
				Name: k,
			},
		)
	}

	return pool
}

// Start starts the main worker process that controls worker pool
func (p *WorkerPool) Start() error {
	return p.main.Start()
}

func (p *WorkerPool) Error() chan error {
	return p.fatal
}

// AddWorker adds new worker to the worker pool with registered workflows
// and activities. This method allows you to create several workers
// listening on the same task queue (because this is a valid case).
// However that might be not desired in certain scenarios.
// Named group can be used to track workers registered for specific use cases.
// If there is a need to remove workers, usage of a group might be handy,
// because RemoveWorkers method is doing removal of all workers inside the group.
func (p *WorkerPool) AddWorker(group, taskQueue string,
	workflows, activities map[string]interface{}, opts worker.Options) error {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	opts.OnFatalError = func(err error) { p.fatal <- err }
	opts.DisableRegistrationAliasing = true

	w := p.workerConstructor(p.client, taskQueue, opts)

	for name, fn := range workflows {
		w.RegisterWorkflowWithOptions(fn, workflow.RegisterOptions{Name: name})
	}

	for name, fn := range activities {
		w.RegisterActivityWithOptions(fn, activity.RegisterOptions{Name: name})
	}

	if err := w.Start(); err != nil {
		w = nil
		return err
	}

	p.workers[group] = append(p.workers[group], w)

	return nil
}

// RemoveWorkers stops all the workers of a certain group and
// removes them from the pool.
func (p *WorkerPool) RemoveWorkers(group string) {
	p.mutex.Lock()
	defer p.mutex.Unlock()

	workers, ok := p.workers[group]
	if ok {
		for _, w := range workers {
			w.Stop()
		}

		delete(p.workers, group)
	}
}

// WorkerPoolOption allows to set additional WorkerPool options
type WorkerPoolOption func(*WorkerPool)

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

// WithConfigurator adds Configurator that will be registered as a workflow
func WithConfigurator(configurator Configurator) WorkerPoolOption {
	return func(p *WorkerPool) {
		p.configurators[configurator.ConfiguratorName()] = configurator.Configure
	}
}
