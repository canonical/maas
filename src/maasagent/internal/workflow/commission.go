package workflow

import (
	"go.temporal.io/sdk/workflow"
)

// CommissionParam is a workflow parameter for the Commission workflow
type CommissionParam struct {
	SystemID string `json:"system_id"`
	Queue    string `json:"queue"`
}

// Commission is a Temporal workflow for commissioning a host
func Commission(ctx workflow.Context, params CommissionParam) error {
	return workflow.ExecuteChildWorkflow(ctx, EphemeralOS, EphemeralOSParam{
		SystemID: params.SystemID,
	}).Get(ctx, nil)
}
