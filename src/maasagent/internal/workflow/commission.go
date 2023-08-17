package workflow

import (
	"go.temporal.io/sdk/workflow"
)

// CommissionParam is a workflow parameter for the CommissionWorkflow
type CommissionParam struct {
	SystemID string `json:"system_id"`
	Queue    string `json:"queue"`
}

// Commission is a Temporal workflow for commissioning a host
func Commission(ctx workflow.Context, params CommissionParam) error {
	future := workflow.ExecuteChildWorkflow(ctx, EphemeralOS, EphemeralOSParam{
		SystemID: params.SystemID,
	})

	if err := future.Get(ctx, nil); err != nil {
		return err
	}

	return nil
}
