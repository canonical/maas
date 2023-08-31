package workflow

import (
	"fmt"

	"go.temporal.io/sdk/workflow"

	"maas.io/core/src/maasagent/internal/workflow/log/tag"
)

// DeployedOSParam are workflow parameters for the DeployedOS workflow
type DeployedOSParam struct {
	SystemID string     `json:"system_id"`
	Power    PowerParam `json:"power"`
}

// DeployedOS is a Temporal workflow for the deployed OS portion of deployment
func DeployedOS(ctx workflow.Context, params DeployedOSParam) error {
	log := workflow.GetLogger(ctx)

	systemIDTag := tag.TargetSystemID(params.SystemID)

	log.Debug("executing PowerCycle", systemIDTag)

	err := workflow.ExecuteChildWorkflow(ctx, PowerCycle, params.Power).Get(ctx, nil)
	if err != nil {
		return err
	}

	leaseSignal := receive[LeaseSignal](ctx, params.SystemID)
	if len(leaseSignal.IP) == 0 || len(leaseSignal.MAC) == 0 {
		return ErrNoLease
	}

	log.Debug(fmt.Sprintf("received lease %s %s for: %s\n", leaseSignal.IP, leaseSignal.MAC, params.SystemID), systemIDTag)

	tftpAckSignal := receive[BootAssetsSignal](ctx, params.SystemID)
	if len(tftpAckSignal.SystemID) == 0 {
		return ErrNoTFTPAck
	}

	log.Debug("received TFTP ACK", systemIDTag)

	cloudInitStartSignal := receive[CloudInitStartSignal](ctx, params.SystemID)
	if len(cloudInitStartSignal.SystemID) == 0 {
		return ErrCloudInitDidNotStart
	}

	log.Debug("cloud-init started", systemIDTag)

	cloudInitFinishedSignal := receive[CloudInitFinishedSignal](ctx, params.SystemID)
	if len(cloudInitFinishedSignal.SystemID) == 0 {
		return ErrCloudInitFailed
	}

	log.Debug("cloud-init finished", systemIDTag)

	return nil
}
