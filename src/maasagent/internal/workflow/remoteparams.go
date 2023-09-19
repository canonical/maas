package workflow

// SwitchBootOrderParam is an activity parameter for switching boot order
type SwitchBootOrderParam struct {
	SystemID    string `json:"system_id"`
	NetworkBoot bool   `json:"network_boot"`
}

// SwitchBootOrderResult is a value returned by the SwitchBootOrderActivity
type SwitchBootOrderResult struct {
	Success bool `json:"success"`
}
