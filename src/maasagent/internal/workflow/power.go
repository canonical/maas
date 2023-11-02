package workflow

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"reflect"
	"strings"
	"time"

	"go.temporal.io/sdk/activity"
	"go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/workflow/log/tag"
)

const (
	powerActivityDuration = 60 * time.Second
)

var (
	// ErrWrongPowerState is an error for when a power operation executes
	// and the machine is found in an incorrect power state
	ErrWrongPowerState = errors.New("BMC is in the wrong power state")
)

var (
	// power parameters fetched from the DB contain extra
	// parameters the CLI does not need and will cause errors in the CLI
	// so we ignore them
	ignoredPowerOptions = map[string]struct{}{
		"power_id":       {},
		"system_id":      {},
		"boot_mode":      {},
		"power_off_mode": {},
	}

	// these driver types do not take a MAC address argument on the CLI
	ignoredMACDriverTypes = map[string]struct{}{
		"lxd":   {},
		"virsh": {},
	}
)

// PowerParam is the workflow parameter for power management of a host
type PowerParam struct {
	SystemID   string                 `json:"system_id"`
	Action     string                 `json:"action"`
	Queue      string                 `json:"queue"`
	DriverOpts map[string]interface{} `json:"params"`
	Driver     string                 `json:"power_type"`
}

func shouldIgnoreMACDriverType(driver, key string) bool {
	_, ignore := ignoredMACDriverTypes[driver]
	return ignore && key == "mac_address"
}

func shouldIgnorePowerOption(key string) bool {
	_, ignore := ignoredPowerOptions[key]
	return ignore
}

// powerCLIExecutableName returns correct MAAS Power CLI executable name
// depending on the installation type (snap or deb package)
func powerCLIExecutableName() string {
	if os.Getenv("SNAP") == "" {
		return "maas.power"
	}

	return "maas-power"
}

func fmtPowerOpts(driver string, opts map[string]interface{}) []string {
	var res []string

	for k, v := range opts {
		if shouldIgnoreMACDriverType(driver, k) || shouldIgnorePowerOption(k) {
			continue
		}

		k = strings.ReplaceAll(k, "_", "-")

		switch reflect.TypeOf(v).Kind() {
		case reflect.Slice:
			s := reflect.ValueOf(v)
			for i := 0; i < s.Len(); i++ {
				vStr := fmt.Sprintf("%v", s.Index(i))

				res = append(res, fmt.Sprintf("--%s", k), vStr)
			}
		default:
			vStr := fmt.Sprintf("%v", v)
			if len(vStr) == 0 {
				continue
			}

			res = append(res, fmt.Sprintf("--%s", k), vStr)
		}
	}

	return res
}

// PowerActivityParam is the activity parameter for PowerActivity
type PowerActivityParam struct {
	Operation string `json:"operation"`
	PowerParam
}

// PowerResult is the result of power actions
type PowerResult struct {
	State string `json:"state"`
}

// PowerActivity executes power operations via the maas.power CLI
func PowerActivity(ctx context.Context, params PowerActivityParam) (*PowerResult, error) {
	log := activity.GetLogger(ctx)

	maasPowerCLI, err := exec.LookPath(powerCLIExecutableName())

	if err != nil {
		log.Error("MAAS power CLI executable path lookup failure",
			tag.Builder().Error(err).KeyVals...)
		return nil, err
	}

	driverOpts := fmtPowerOpts(params.Driver, params.DriverOpts)
	args := append([]string{params.Operation, params.Driver}, driverOpts...)

	log.Debug("Executing MAAS power CLI", tag.Builder().KV("args", args).KeyVals...)

	//nolint:gosec // gosec's G204 flags any command execution using variables
	cmd := exec.CommandContext(ctx, maasPowerCLI, args...)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err = cmd.Run()
	if err != nil {
		log.Error(
			"Error executing power command",
			tag.Builder().Error(err).
				KV("stdout", stdout.String()).
				KV("stderr", stderr.String()).KeyVals...)

		return nil, err
	}

	res := &PowerResult{
		State: strings.TrimSpace(stdout.String()),
	}

	return res, nil
}

func execPowerActivity(ctx workflow.Context, params PowerActivityParam) workflow.Future {
	ctx = workflow.WithActivityOptions(ctx, workflow.ActivityOptions{
		StartToCloseTimeout: powerActivityDuration,
	})

	return workflow.ExecuteActivity(ctx, PowerActivity, params)
}

// PowerOn will power on a host
func PowerOn(ctx workflow.Context, params PowerParam) (*PowerResult, error) {
	log := workflow.GetLogger(ctx)

	log.Info("Powering on", tag.Builder().TargetSystemID(params.SystemID).KeyVals...)

	activityParams := PowerActivityParam{
		Operation:  "on",
		PowerParam: params,
	}

	var res PowerResult

	err := execPowerActivity(ctx, activityParams).Get(ctx, &res)
	if err != nil {
		return nil, err
	}

	if res.State != "on" {
		return nil, ErrWrongPowerState
	}

	return &res, nil
}

// PowerOff will power off a host
func PowerOff(ctx workflow.Context, params PowerParam) (*PowerResult, error) {
	log := workflow.GetLogger(ctx)

	log.Info("Powering off", tag.Builder().TargetSystemID(params.SystemID).KeyVals...)

	activityParams := PowerActivityParam{
		Operation:  "off",
		PowerParam: params,
	}

	var res PowerResult

	err := execPowerActivity(ctx, activityParams).Get(ctx, &res)
	if err != nil {
		return nil, err
	}

	if res.State != "off" {
		return nil, ErrWrongPowerState
	}

	return &res, nil
}

// PowerCycle will power cycle a host
func PowerCycle(ctx workflow.Context, params PowerParam) (*PowerResult, error) {
	log := workflow.GetLogger(ctx)

	log.Info("Cycling power", tag.Builder().TargetSystemID(params.SystemID).KeyVals...)

	activityParams := PowerActivityParam{
		Operation:  "cycle",
		PowerParam: params,
	}

	var res PowerResult

	err := execPowerActivity(ctx, activityParams).Get(ctx, &res)
	if err != nil {
		return nil, err
	}

	if res.State != "on" {
		return nil, ErrWrongPowerState
	}

	return &res, nil
}

// PowerQuery will query the power state of a host
func PowerQuery(ctx workflow.Context, params PowerParam) (*PowerResult, error) {
	log := workflow.GetLogger(ctx)

	log.Info("Querying power status", tag.Builder().TargetSystemID(params.SystemID).KeyVals...)

	activityParams := PowerActivityParam{
		Operation:  "status",
		PowerParam: params,
	}

	var res PowerResult

	err := execPowerActivity(ctx, activityParams).Get(ctx, &res)
	if err != nil {
		return nil, err
	}

	return &res, nil
}
