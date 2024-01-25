package workflow

// Configurator is an interface defining behavior for structs
// responsible for a Temporal activity for configuration of a service.
type Configurator interface {
	// Configure should return a function that will be registered
	// as an activity within the main worker (e.g. system-id@agent:main)
	// Activity will be registered with a prefix `configure-`
	Configure() interface{}
}
