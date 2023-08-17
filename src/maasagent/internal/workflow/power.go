package workflow

import (
	"context"
	"errors"
	"fmt"
	"os/exec"

	"go.temporal.io/sdk/workflow"
)

var (
	ErrWrongPowerState = errors.New("BMC is in wrong power state")
)

// PowerParam is the workflow parameter for power management of a host
type PowerParam struct {
	DriverOpts map[string]interface{} `json:"driver_opts"`
	Driver     string                 `json:"driver"`
}

func fmtPowerOpts(opts map[string]interface{}) []string {
	res := make([]string, len(opts))

	var i int

	for k, v := range opts {
		res[i] = fmt.Sprintf("--%s=%v", k, v)
		i++
	}

	return res
}

type PowerActivityParam struct {
	Operation string `json:"operation"`
	PowerParam
}

type PowerActivityResult struct {
	Status string `json:"status"`
}

// PowerActivity executes power operations via the maas.power CLI
func PowerActivity(ctx context.Context, params PowerActivityParam) (*PowerActivityResult, error) {
	maasPowerCLI, err := exec.LookPath("maas.power")
	if err != nil {
		return nil, err
	}

	driverOpts := fmtPowerOpts(params.DriverOpts)
	args := append([]string{params.Operation, params.Driver}, driverOpts...)
	//nolint:gosec // gosec's G204 flags any command execution using variables
	cmd := exec.CommandContext(ctx, maasPowerCLI, args...)

	out, err := cmd.Output()
	if err != nil {
		return nil, err
	}

	res := &PowerActivityResult{
		Status: string(out),
	}

	return res, nil
}

// PowerOn will power on a host
func PowerOn(ctx workflow.Context, params PowerParam) error {
	activityParams := PowerActivityParam{
		Operation:  "on",
		PowerParam: params,
	}

	var res PowerActivityResult

	err := workflow.ExecuteActivity(ctx, PowerActivity, activityParams).Get(ctx, &res)
	if err != nil {
		return err
	}

	if res.Status != "on" {
		return ErrWrongPowerState
	}

	return nil
}

// PowerOff will power off a host
func PowerOff(ctx workflow.Context, params PowerParam) error {
	activityParams := PowerActivityParam{
		Operation:  "off",
		PowerParam: params,
	}

	var res PowerActivityResult

	err := workflow.ExecuteActivity(ctx, PowerActivity, activityParams).Get(ctx, &res)
	if err != nil {
		return err
	}

	if res.Status != "off" {
		return ErrWrongPowerState
	}

	return nil
}

// PowerCycle will power cycle a host
func PowerCycle(ctx workflow.Context, params PowerParam) error {
	activityParams := PowerActivityParam{
		Operation:  "cycle",
		PowerParam: params,
	}

	var res PowerActivityResult

	err := workflow.ExecuteActivity(ctx, PowerActivity, activityParams).Get(ctx, &res)
	if err != nil {
		return err
	}

	if res.Status != "on" {
		return ErrWrongPowerState
	}

	return nil
}

type PowerQueryResult struct {
	Status string
}

// PowerQuery will query the power state of a host
func PowerQuery(ctx workflow.Context, params PowerParam) (*PowerQueryResult, error) {
	activityParams := PowerActivityParam{
		Operation:  "status",
		PowerParam: params,
	}

	var res PowerActivityResult

	err := workflow.ExecuteActivity(ctx, PowerActivity, activityParams).Get(ctx, &res)
	if err != nil {
		return nil, err
	}

	result := PowerQueryResult(res)

	return &result, nil
}
