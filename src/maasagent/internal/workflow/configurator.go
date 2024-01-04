package workflow

// Configurator is an interface defining behavior for structs
// responsible for a Temporal activity for configuration of a service
type Configurator interface {
	CreateConfigActivity() interface{}
}
