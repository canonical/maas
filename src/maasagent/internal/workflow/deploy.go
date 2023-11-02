package workflow

import (
	"net/netip"

	"go.temporal.io/sdk/workflow"

	"maas.io/core/src/maasagent/internal/workflow/log/tag"
)

// DeployParam is a workflow parameter for the Deploy workflow
type DeployParam struct {
	Power        PowerParam `json:"power"`
	SystemID     string     `json:"system_id"`
	Queue        string     `json:"queue"`
	RequestedIPs []string   `json:"requested_ips"`
}

// Deploy is a Temporal workflow that is reasonable for deploying a host
func Deploy(ctx workflow.Context, params DeployParam) error {
	log := workflow.GetLogger(ctx)

	log.Info("Starting deployment", tag.Builder().TargetSystemID(params.SystemID).KeyVals...)

	var err error

	ipsToCheck := make([]netip.Addr, len(params.RequestedIPs))

	for i, ipStr := range params.RequestedIPs {
		ipsToCheck[i], err = netip.ParseAddr(ipStr)
		if err != nil {
			return err
		}
	}

	future := workflow.ExecuteChildWorkflow(ctx, CheckIP, CheckIPParam{
		IPs: ipsToCheck,
	})

	if err := future.Get(ctx, nil); err != nil {
		return err
	}

	future = workflow.ExecuteChildWorkflow(ctx, EphemeralOS, EphemeralOSParam{
		SystemID:     params.SystemID,
		SetBootOrder: true,
		Power:        params.Power,
	})

	if err := future.Get(ctx, nil); err != nil {
		return err
	}

	future = workflow.ExecuteChildWorkflow(ctx, DeployedOS, DeployedOSParam{
		SystemID: params.SystemID,
		Power:    params.Power,
	})

	if err := future.Get(ctx, nil); err != nil {
		return err
	}

	log.Info("Deployment successful", tag.Builder().TargetSystemID(params.SystemID).KeyVals...)

	return nil
}
