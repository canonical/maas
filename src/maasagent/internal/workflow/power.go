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

	"go.temporal.io/sdk/activity"
	"maas.io/core/src/maasagent/internal/workflow/log/tag"
)

var (
	// ErrWrongPowerState is an error for when a power action executes
	// and the machine is found in an incorrect power state
	ErrWrongPowerState = errors.New("BMC is in the wrong power state")
)

// PowerOnParam is the activity parameter for power management of a host
type PowerOnParam struct {
	DriverOpts map[string]interface{} `json:"driver_opts"`
	DriverType string                 `json:"driver_type"`
}

// PowerOnResult is the result of power action
type PowerOnResult struct {
	State string `json:"state"`
}

// PowerOffParam is the activity parameter for power management of a host
type PowerOffParam struct {
	DriverOpts map[string]interface{} `json:"driver_opts"`
	DriverType string                 `json:"driver_type"`
}

// PowerOffResult is the result of power action
type PowerOffResult struct {
	State string `json:"state"`
}

// PowerCycleParam is the activity parameter for power management of a host
type PowerCycleParam struct {
	DriverOpts map[string]interface{} `json:"driver_opts"`
	DriverType string                 `json:"driver_type"`
}

// PowerCycleResult is the result of power action
type PowerCycleResult struct {
	State string `json:"state"`
}

// PowerQueryParam is the activity parameter for power management of a host
type PowerQueryParam struct {
	DriverOpts map[string]interface{} `json:"driver_opts"`
	DriverType string                 `json:"driver_type"`
}

// PowerQueryResult is the result of power action
type PowerQueryResult struct {
	State string `json:"state"`
}

// powerCLIExecutableName returns correct MAAS Power CLI executable name
// depending on the installation type (snap or deb package)
func powerCLIExecutableName() string {
	if os.Getenv("SNAP") == "" {
		return "maas.power"
	}

	return "maas-power"
}

func fmtPowerOpts(opts map[string]interface{}) []string {
	var res []string

	for k, v := range opts {
		// skip 'system_id' as it is not required by any power driver contract.
		// it is added by the region when driver is called directly (not via CLI)
		// also skip 'null' values (some power options might have them empty)
		if k == "system_id" || v == nil {
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

func PowerOn(ctx context.Context, param PowerOnParam) (*PowerOnResult, error) {
	out, err := powerCommand(ctx, "on", param.DriverType, param.DriverOpts)
	if err != nil {
		return nil, err
	}

	out = strings.TrimSpace(out)

	if out != "on" {
		return nil, ErrWrongPowerState
	}

	return &PowerOnResult{State: out}, nil
}
func PowerOff(ctx context.Context, param PowerOffParam) (*PowerOffResult, error) {
	out, err := powerCommand(ctx, "off", param.DriverType, param.DriverOpts)
	if err != nil {
		return nil, err
	}

	out = strings.TrimSpace(out)

	if out != "off" {
		return nil, ErrWrongPowerState
	}

	return &PowerOffResult{State: out}, nil
}
func PowerCycle(ctx context.Context, param PowerCycleParam) (*PowerCycleResult, error) {
	out, err := powerCommand(ctx, "cycle", param.DriverType, param.DriverOpts)
	if err != nil {
		return nil, err
	}

	out = strings.TrimSpace(out)

	if out != "on" {
		return nil, ErrWrongPowerState
	}

	return &PowerCycleResult{State: out}, nil
}

func PowerQuery(ctx context.Context, param PowerQueryParam) (*PowerQueryResult, error) {
	out, err := powerCommand(ctx, "status", param.DriverType, param.DriverOpts)
	if err != nil {
		return nil, err
	}

	out = strings.TrimSpace(out)

	return &PowerQueryResult{State: out}, nil
}

func powerCommand(ctx context.Context, action, driver string, opts map[string]interface{}) (string, error) {
	log := activity.GetLogger(ctx)

	maasPowerCLI, err := exec.LookPath(powerCLIExecutableName())

	if err != nil {
		log.Error("MAAS power CLI executable path lookup failure",
			tag.Builder().Error(err).KeyVals...)
		return "", err
	}

	formattedOpts := fmtPowerOpts(opts)

	args := append([]string{action, driver}, formattedOpts...)

	log.Debug("Executing MAAS power CLI", tag.Builder().KV("args", args).KeyVals...)

	//nolint:gosec // gosec's G204 flags any command execution using variables
	cmd := exec.CommandContext(ctx, maasPowerCLI, args...)

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err = cmd.Run()
	if err != nil {
		t := tag.Builder().Error(err)
		if stdout.String() != "" {
			t = t.KV("stdout", stdout.String())
		}

		if stderr.String() != "" {
			t = t.KV("stderr", stderr.String())
		}

		log.Error("Error executing power command", t.KeyVals...)

		return "", err
	}

	return stdout.String(), nil
}
