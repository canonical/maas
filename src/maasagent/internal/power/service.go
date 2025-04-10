// Copyright (c) 2023-2025 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

package power

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"reflect"
	"strings"
	"time"

	"go.temporal.io/sdk/activity"
	tworker "go.temporal.io/sdk/worker"
	tworkflow "go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/workflow"
	"maas.io/core/src/maasagent/internal/workflow/log/tag"
	"maas.io/core/src/maasagent/internal/workflow/worker"
)

const powerServiceWorkerPoolGroup = "power-service"

var (
	// ErrWrongPowerState is an error for when a power action executes
	// and the machine is found in an incorrect power state
	ErrWrongPowerState = errors.New("BMC is in the wrong power state")

	// procFactory holds the implementation of a function that will return a
	// command that can be called with Run(). This is used to inject the actual
	// `os/exec`-based implementation within `configure()`, or a mocked
	// implementation for unit testing.
	procFactory powerProcFactory

	// pathFactory holds the implementation of a function that will return a
	// command that attempts to resolve the full path of a program binary.
	// This is used to inject the actual `os/exec`-based implementation within
	// `configure()`, or a mocked implementation for unit testing.
	pathFactory osPathFactory
)

type powerProc interface {
	Run() error
}

type powerProcFactory func(ctx context.Context, stdout, stderr *bytes.Buffer, name string, arg ...string) powerProc

type osPathFactory func(file string) (string, error)

// PowerService is a service that knows how to reach BMC to perform power
// operations. Invocation of this service normally should happen via Temporal.
type PowerService struct {
	pool *worker.WorkerPool
}

func NewPowerService(systemID string, pool *worker.WorkerPool) *PowerService {
	return &PowerService{
		pool: pool,
	}
}

func (s *PowerService) ConfigurationWorkflows() map[string]any {
	return map[string]any{"configure-power-service": s.configure}
}

func (s *PowerService) ConfigurationActivities() map[string]any {
	return map[string]any{}
}

func (s *PowerService) configure(ctx tworkflow.Context, systemID string) error {
	log := tworkflow.GetLogger(ctx)
	log.Info("Configuring power-service")

	// Because we don't support partial updates, we always start configuration
	// with a clean "state" by removing all previously configured workers.
	if err := workflow.RunAsLocalActivity(ctx, func(_ context.Context) error {
		s.pool.RemoveWorkers(powerServiceWorkerPoolGroup)
		return nil
	}); err != nil {
		return err
	}

	type getAgentVLANsParam struct {
		SystemID string `json:"system_id"`
	}

	type getAgentVLANsResult struct {
		VLANs []int `json:"vlans"`
	}

	param := getAgentVLANsParam{SystemID: systemID}

	var vlansResult getAgentVLANsResult
	err := tworkflow.ExecuteActivity(
		tworkflow.WithActivityOptions(ctx,
			tworkflow.ActivityOptions{
				TaskQueue:              "region",
				ScheduleToCloseTimeout: 60 * time.Second,
			}),
		"get-rack-controller-vlans", param).
		Get(ctx, &vlansResult)

	if err != nil {
		return err
	}

	procFactory = func(ctx context.Context, stdout, stderr *bytes.Buffer, name string, arg ...string) powerProc {
		cmd := exec.CommandContext(ctx, name, arg...)
		cmd.Stdout = stdout
		cmd.Stderr = stderr

		return cmd
	}

	//nolint:gocritic // The 'unlambda' check fails if enabled - this interface-based implementation is needed for dependency injection and unit testing
	pathFactory = func(file string) (string, error) {
		return exec.LookPath(file)
	}

	activities := map[string]any{
		"power-on":       s.PowerOn,
		"power-off":      s.PowerOff,
		"power-query":    s.PowerQuery,
		"power-cycle":    s.PowerCycle,
		"power-reset":    s.PowerReset,
		"set-boot-order": s.SetBootOrder,
	}

	// TODO: register workflows once they are moved to the Agent
	workflows := map[string]any{}

	// Register workers listening VLAN specific task queue and a common one
	// for fallback scenario for routable access.
	return workflow.RunAsLocalActivity(ctx,
		func(_ context.Context) error {
			for _, vlan := range vlansResult.VLANs {
				taskQueue := fmt.Sprintf("agent:power@vlan-%d", vlan)
				if err := s.pool.AddWorker(powerServiceWorkerPoolGroup, taskQueue,
					workflows, activities, tworker.Options{}); err != nil {
					s.pool.RemoveWorkers(powerServiceWorkerPoolGroup)

					return err
				}
			}

			taskQueue := fmt.Sprintf("%s@agent:power", systemID)
			if err := s.pool.AddWorker(powerServiceWorkerPoolGroup, taskQueue,
				nil, activities, tworker.Options{}); err != nil {
				s.pool.RemoveWorkers(powerServiceWorkerPoolGroup)

				return err
			}

			log.Info("Started power-service")

			return nil
		})
}

// PowerParam is a generic activity parameter for power management of a host
type PowerParam struct {
	DriverOpts map[string]any `json:"driver_opts"`
	DriverType string         `json:"driver_type"`
	IsDPU      bool           `json:"is_dpu"`
}

// PowerOnParam is the activity parameter for power management of a host
type PowerOnParam struct {
	PowerParam
}

// PowerOnResult is the result of power action
type PowerOnResult struct {
	State string `json:"state"`
}

// PowerOffParam is the activity parameter for power management of a host
type PowerOffParam struct {
	PowerParam
}

// PowerOffResult is the result of power action
type PowerOffResult struct {
	State string `json:"state"`
}

// PowerCycleParam is the activity parameter for power management of a host
type PowerCycleParam struct {
	PowerParam
}

// PowerCycleResult is the result of power action
type PowerCycleResult struct {
	State string `json:"state"`
}

// PowerQueryParam is the activity parameter for power management of a host
type PowerQueryParam struct {
	PowerParam
}

// PowerQueryResult is the result of power action
type PowerQueryResult struct {
	State string `json:"state"`
}

// PowerResetParam is the activity parameter for power management of a host
type PowerResetParam struct {
	PowerParam
}

// PowerResetResult is the result of power action
type PowerResetResult struct {
	State string `json:"state"`
}

func (s *PowerService) PowerOn(ctx context.Context, param PowerOnParam) (*PowerOnResult, error) {
	out, err := powerCommand(ctx, "on", param.IsDPU, param.DriverType, param.DriverOpts)
	if err != nil {
		return nil, err
	}

	out = strings.TrimSpace(out)

	if out != "on" {
		return nil, ErrWrongPowerState
	}

	return &PowerOnResult{State: out}, nil
}
func (s *PowerService) PowerOff(ctx context.Context, param PowerOffParam) (*PowerOffResult, error) {
	out, err := powerCommand(ctx, "off", param.IsDPU, param.DriverType, param.DriverOpts)
	if err != nil {
		return nil, err
	}

	out = strings.TrimSpace(out)

	if out != "off" {
		return nil, ErrWrongPowerState
	}

	return &PowerOffResult{State: out}, nil
}
func (s *PowerService) PowerCycle(ctx context.Context, param PowerCycleParam) (*PowerCycleResult, error) {
	out, err := powerCommand(ctx, "cycle", param.IsDPU, param.DriverType, param.DriverOpts)
	if err != nil {
		return nil, err
	}

	out = strings.TrimSpace(out)

	if out != "on" {
		return nil, ErrWrongPowerState
	}

	return &PowerCycleResult{State: out}, nil
}

func (s *PowerService) PowerQuery(ctx context.Context, param PowerQueryParam) (*PowerQueryResult, error) {
	out, err := powerCommand(ctx, "status", param.IsDPU, param.DriverType, param.DriverOpts)
	if err != nil {
		return nil, err
	}

	out = strings.TrimSpace(out)

	return &PowerQueryResult{State: out}, nil
}

func (s *PowerService) PowerReset(ctx context.Context, param PowerResetParam) (*PowerResetResult, error) {
	out, err := powerCommand(ctx, "reset", param.IsDPU, param.DriverType, param.DriverOpts)
	if err != nil {
		return nil, err
	}

	out = strings.TrimSpace(out)

	if out != "on" {
		return nil, ErrWrongPowerState
	}

	return &PowerResetResult{State: out}, nil
}

type SetBootOrderParam struct {
	SystemID    string           `json:"system_id"`
	PowerParams PowerParam       `json:"power_param"`
	Order       []map[string]any `json:"order"`
}

func (s *PowerService) SetBootOrder(ctx context.Context, param SetBootOrderParam) error {
	log := activity.GetLogger(ctx)

	log.Info("setting boot order of " + param.SystemID)

	_, err := powerCommand(ctx, "set-boot-order", false, param.PowerParams.DriverType, param.PowerParams.DriverOpts)

	return err
}

func powerCommand(ctx context.Context, action string, isDPU bool, driver string, opts map[string]any, bootOrder ...map[string]any) (string, error) {
	log := activity.GetLogger(ctx)

	maasPowerCLI, err := pathFactory(powerCLIExecutableName())

	if err != nil {
		log.Error("MAAS power CLI executable path lookup failure",
			tag.Builder().Error(err).KeyVals...)
		return "", err
	}

	var args []string

	args = append(args, action)

	if isDPU {
		args = append(args, "--is-dpu")
	}

	args = append(args, driver)

	formattedOpts := fmtPowerOpts(opts)

	args = append(args, formattedOpts...)

	if action == "set-boot-order" {
		bootOrderStr := make([]string, len(bootOrder))

		for i, device := range bootOrder {
			var dev []byte

			dev, err = json.Marshal(device)
			if err != nil {
				return "", err
			}

			bootOrderStr[i] = string(dev)
		}

		args = append(args, "--order", "'"+strings.Join(bootOrderStr, ",")+"'")
	}

	log.Debug("Executing MAAS power CLI", tag.Builder().KV("args", args).KeyVals...)

	var stdout, stderr bytes.Buffer

	cmd := procFactory(ctx, &stdout, &stderr, maasPowerCLI, args...)

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

// powerCLIExecutableName returns correct MAAS Power CLI executable name
// depending on the installation type (snap or deb package)
func powerCLIExecutableName() string {
	if os.Getenv("SNAP") == "" {
		return "maas.power"
	}

	return "maas-power"
}

func fmtPowerOpts(opts map[string]any) []string {
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
