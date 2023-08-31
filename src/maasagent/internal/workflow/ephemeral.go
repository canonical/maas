package workflow

import (
	"context"
	"errors"
	"fmt"
	"time"

	"go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/workflow/log/tag"
)

var (
	// ErrSwitchBootOrderFailed is an error for when the workflow failed to switch boot order
	ErrSwitchBootOrderFailed = errors.New("boot order was not switched")
)

// SwitchBootOrderParam is an activity parameter for switching boot order
type SwitchBootOrderParam struct {
	SystemID string `json:"system_id"`
}

// SwitchBootOrderResult is a value returned by the SwitchBootOrderActivity
type SwitchBootOrderResult struct {
	Success bool `json:"success"`
}

// SwitchBootOrderActivity is a Temporal activity for switching boot order of a host
func SwitchBootOrderActivity(ctx context.Context, params SwitchBootOrderParam) error {
	fmt.Printf("reach out to MAAS to update boot order for: %s\n", params.SystemID)
	return nil
}

// EphemeralOSParam is a workflow parameter for the EphemeralOS workflow
type EphemeralOSParam struct {
	Power        PowerParam `json:"power"`
	SystemID     string     `json:"system_id"`
	SetBootOrder bool       `json:"set_boot_order"`
}

// EphemeralOS is a Temporal workflow for the ephemeral OS portion of deployment
func EphemeralOS(ctx workflow.Context, params EphemeralOSParam) error {
	log := workflow.GetLogger(ctx)

	systemIDTag := tag.TargetSystemID(params.SystemID)

	var powerStatus PowerQueryResult

	log.Debug("querying power status", systemIDTag)

	err := workflow.ExecuteChildWorkflow(ctx, PowerQuery, params.Power).Get(ctx, &powerStatus)
	if err != nil {
		return err
	}

	log.Debug("powering on machine", systemIDTag)

	if powerStatus.Status == "on" {
		err = workflow.ExecuteChildWorkflow(ctx, PowerCycle, params.Power).Get(ctx, nil)
	} else {
		err = workflow.ExecuteChildWorkflow(ctx, PowerOn, params.Power).Get(ctx, nil)
	}

	if err != nil {
		return err
	}

	leaseSignal := receive[LeaseSignal](ctx, params.SystemID)
	if len(leaseSignal.IP) == 0 || len(leaseSignal.MAC) == 0 {
		return ErrNoLease
	}

	log.Debug(
		fmt.Sprintf(
			"received lease %s %s for: %s\n",
			leaseSignal.IP,
			leaseSignal.MAC,
			params.SystemID,
		),
		systemIDTag,
	)

	bootAssetsSignal := receive[BootAssetsSignal](ctx, params.SystemID)
	if len(bootAssetsSignal.SystemID) == 0 {
		return ErrBootAssetsNotRequested
	}

	log.Debug("boot assets downloaded", systemIDTag)

	curtinDownloadSignal := receive[CurtinDownloadSignal](ctx, params.SystemID)
	if len(curtinDownloadSignal.SystemID) == 0 {
		return ErrCurtinNotDownloaded
	}

	log.Debug("curtin downloaded", systemIDTag)

	curtinFinishedSignal := receive[CurtinFinishedSignal](ctx, params.SystemID)
	if !curtinFinishedSignal.Success {
		return ErrCurtinFailed
	}

	log.Debug("curtin finished", systemIDTag)

	if params.SetBootOrder {
		log.Debug("setting boot order to local first", systemIDTag)

		bootOrderOpts := workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Second,
		}

		ctx = workflow.WithActivityOptions(ctx, bootOrderOpts)

		bootOrderParams := SwitchBootOrderParam{
			SystemID: params.SystemID,
		}

		var bootOrderResults SwitchBootOrderResult

		err := workflow.ExecuteActivity(ctx, SwitchBootOrderActivity, bootOrderParams).Get(ctx, &bootOrderResults)
		if err != nil {
			return err
		}

		if !bootOrderResults.Success {
			return ErrSwitchBootOrderFailed
		}
	}

	return nil
}
