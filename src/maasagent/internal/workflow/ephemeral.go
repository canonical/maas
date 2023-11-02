package workflow

import (
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

// EphemeralOSParam is a workflow parameter for the EphemeralOS workflow
type EphemeralOSParam struct {
	Power        PowerParam `json:"power"`
	SystemID     string     `json:"system_id"`
	SetBootOrder bool       `json:"set_boot_order"`
}

// EphemeralOS is a Temporal workflow for the ephemeral OS portion of deployment
func EphemeralOS(ctx workflow.Context, params EphemeralOSParam) error {
	log := workflow.GetLogger(ctx)

	var powerStatus PowerResult

	log.Debug("Querying power status", tag.Builder().TargetSystemID(params.SystemID).KeyVals...)

	err := workflow.ExecuteChildWorkflow(ctx, PowerQuery, params.Power).Get(ctx, &powerStatus)
	if err != nil {
		return err
	}

	log.Debug("Powering on machine", tag.Builder().TargetSystemID(params.SystemID).KeyVals...)

	if powerStatus.State == "on" {
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
			"Received lease %s %s for: %s\n",
			leaseSignal.IP,
			leaseSignal.MAC,
			params.SystemID,
		),
		tag.Builder().TargetSystemID(params.SystemID).KeyVals...,
	)

	bootAssetsSignal := receive[BootAssetsSignal](ctx, params.SystemID)
	if len(bootAssetsSignal.SystemID) == 0 {
		return ErrBootAssetsNotRequested
	}

	log.Debug("Boot assets downloaded", tag.Builder().TargetSystemID(params.SystemID).KeyVals...)

	curtinDownloadSignal := receive[CurtinDownloadSignal](ctx, params.SystemID)
	if len(curtinDownloadSignal.SystemID) == 0 {
		return ErrCurtinNotDownloaded
	}

	log.Debug("Curtin downloaded", tag.Builder().TargetSystemID(params.SystemID).KeyVals...)

	curtinFinishedSignal := receive[CurtinFinishedSignal](ctx, params.SystemID)
	if !curtinFinishedSignal.Success {
		return ErrCurtinFailed
	}

	log.Debug("Curtin finished", tag.Builder().TargetSystemID(params.SystemID).KeyVals...)

	if params.SetBootOrder {
		log.Debug("Setting boot order to local first", tag.Builder().TargetSystemID(params.SystemID).KeyVals...)

		bootOrderOpts := workflow.ActivityOptions{
			StartToCloseTimeout: 10 * time.Second,
		}

		ctx = workflow.WithActivityOptions(ctx, bootOrderOpts)

		bootOrderParams := SwitchBootOrderParam{
			SystemID:    params.SystemID,
			NetworkBoot: false,
		}

		var bootOrderResults SwitchBootOrderResult

		err := workflow.ExecuteActivity(ctx, "switch-boot-order", bootOrderParams).Get(ctx, &bootOrderResults)
		if err != nil {
			return err
		}

		if !bootOrderResults.Success {
			return ErrSwitchBootOrderFailed
		}
	}

	return nil
}
