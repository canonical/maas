// Copyright (c) 2023-2026 Canonical Ltd
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
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"time"

	"go.temporal.io/sdk/activity"
	tworker "go.temporal.io/sdk/worker"
	tworkflow "go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/workflow"
	"maas.io/core/src/maasagent/internal/workflow/worker"
)

const powerServiceWorkerPoolGroup = "power-service"

var (
	// ErrWrongPowerState is an error for when a power action executes
	// and the machine is found in an incorrect power state
	ErrWrongPowerState = errors.New("BMC is in the wrong power state")

	// socketClientFactory is a function that creates a socketClient.
	// It can be overridden in tests to inject a mock client.
	socketClientFactory = func(logger *slog.Logger, socketPath string) socketClient {
		return NewSocketClient(logger, socketPath)
	}
)

// socketClient defines the interface for communicating with a power driver.
type socketClient interface {
	On(ctx context.Context, systemID string, context map[string]any) (map[string]any, error)
	Off(ctx context.Context, systemID string, context map[string]any) (map[string]any, error)
	Cycle(ctx context.Context, systemID string, context map[string]any) (map[string]any, error)
	Query(ctx context.Context, systemID string, context map[string]any) (map[string]any, error)
	Reset(ctx context.Context, systemID string, context map[string]any) (map[string]any, error)
	SetBootOrder(ctx context.Context, systemID string, context map[string]any, order []string) (map[string]any, error)
}

// PowerService is a service that knows how to reach BMC to perform power
// operations. Invocation of this service normally should happen via Temporal.
type PowerService struct {
	pool     *worker.WorkerPool
	systemID string
	registry *Registry
	logger   *slog.Logger
}

func NewPowerService(systemID string, pool *worker.WorkerPool, registry *Registry, logger *slog.Logger) *PowerService {
	return &PowerService{
		pool:     pool,
		systemID: systemID,
		registry: registry,
		logger:   logger,
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
	driver, ok := s.registry.Get(param.DriverType)
	if !ok {
		return nil, fmt.Errorf("power driver %q not found in registry", param.DriverType)
	}

	client := socketClientFactory(s.logger, driver.SocketPath)
	result, err := client.On(ctx, "", param.DriverOpts)
	if err != nil {
		return nil, err
	}

	state, _ := result["state"].(string)
	if state == "" {
		state = "on"
	}

	if state != "on" {
		return nil, ErrWrongPowerState
	}

	return &PowerOnResult{State: state}, nil
}

func (s *PowerService) PowerOff(ctx context.Context, param PowerOffParam) (*PowerOffResult, error) {
	driver, ok := s.registry.Get(param.DriverType)
	if !ok {
		return nil, fmt.Errorf("power driver %q not found in registry", param.DriverType)
	}

	client := socketClientFactory(s.logger, driver.SocketPath)
	result, err := client.Off(ctx, "", param.DriverOpts)
	if err != nil {
		return nil, err
	}

	state, _ := result["state"].(string)
	if state == "" {
		state = "off"
	}

	if state != "off" {
		return nil, ErrWrongPowerState
	}

	return &PowerOffResult{State: state}, nil
}

func (s *PowerService) PowerCycle(ctx context.Context, param PowerCycleParam) (*PowerCycleResult, error) {
	driver, ok := s.registry.Get(param.DriverType)
	if !ok {
		return nil, fmt.Errorf("power driver %q not found in registry", param.DriverType)
	}

	client := socketClientFactory(s.logger, driver.SocketPath)
	result, err := client.Cycle(ctx, "", param.DriverOpts)
	if err != nil {
		return nil, err
	}

	state, _ := result["state"].(string)
	if state == "" {
		state = "on"
	}

	if state != "on" {
		return nil, ErrWrongPowerState
	}

	return &PowerCycleResult{State: state}, nil
}

func (s *PowerService) PowerQuery(ctx context.Context, param PowerQueryParam) (*PowerQueryResult, error) {
	driver, ok := s.registry.Get(param.DriverType)
	if !ok {
		return nil, fmt.Errorf("power driver %q not found in registry", param.DriverType)
	}

	client := socketClientFactory(s.logger, driver.SocketPath)
	result, err := client.Query(ctx, "", param.DriverOpts)
	if err != nil {
		return nil, err
	}

	state, _ := result["state"].(string)

	return &PowerQueryResult{State: state}, nil
}

func (s *PowerService) PowerReset(ctx context.Context, param PowerResetParam) (*PowerResetResult, error) {
	driver, ok := s.registry.Get(param.DriverType)
	if !ok {
		return nil, fmt.Errorf("power driver %q not found in registry", param.DriverType)
	}

	client := socketClientFactory(s.logger, driver.SocketPath)
	result, err := client.Reset(ctx, "", param.DriverOpts)
	if err != nil {
		return nil, err
	}

	state, _ := result["state"].(string)
	if state == "" {
		state = "on"
	}

	if state != "on" {
		return nil, ErrWrongPowerState
	}

	return &PowerResetResult{State: state}, nil
}

type SetBootOrderParam struct {
	SystemID    string           `json:"system_id"`
	PowerParams PowerParam       `json:"power_param"`
	Order       []map[string]any `json:"order"`
}

func (s *PowerService) SetBootOrder(ctx context.Context, param SetBootOrderParam) error {
	log := activity.GetLogger(ctx)

	log.Info("setting boot order of " + param.SystemID)

	driver, ok := s.registry.Get(param.PowerParams.DriverType)
	if !ok {
		return fmt.Errorf("power driver %q not found in registry", param.PowerParams.DriverType)
	}

	// Convert order maps to JSON strings for the socket client
	orderStrs := make([]string, len(param.Order))
	for i, device := range param.Order {
		devData, err := json.Marshal(device)
		if err != nil {
			return fmt.Errorf("marshal boot order device: %w", err)
		}
		orderStrs[i] = string(devData)
	}

	client := socketClientFactory(s.logger, driver.SocketPath)
	_, err := client.SetBootOrder(ctx, param.SystemID, param.PowerParams.DriverOpts, orderStrs)
	return err
}
