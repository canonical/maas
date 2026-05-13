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
	"log/slog"
	"strings"
	"testing"

	"github.com/stretchr/testify/assert"
	"go.temporal.io/sdk/testsuite"
)

// mockSocketClient implements socketClient for testing.
type mockSocketClient struct {
	onResult           map[string]any
	offResult          map[string]any
	cycleResult        map[string]any
	queryResult        map[string]any
	resetResult        map[string]any
	setBootOrderResult map[string]any
	onErr              error
	offErr             error
	cycleErr           error
	queryErr           error
	resetErr           error
	setBootOrderErr    error
}

func (m *mockSocketClient) On(ctx context.Context, systemID string, context map[string]any) (map[string]any, error) {
	return m.onResult, m.onErr
}

func (m *mockSocketClient) Off(ctx context.Context, systemID string, context map[string]any) (map[string]any, error) {
	return m.offResult, m.offErr
}

func (m *mockSocketClient) Cycle(ctx context.Context, systemID string, context map[string]any) (map[string]any, error) {
	return m.cycleResult, m.cycleErr
}

func (m *mockSocketClient) Query(ctx context.Context, systemID string, context map[string]any) (map[string]any, error) {
	return m.queryResult, m.queryErr
}

func (m *mockSocketClient) Reset(ctx context.Context, systemID string, context map[string]any) (map[string]any, error) {
	return m.resetResult, m.resetErr
}

func (m *mockSocketClient) SetBootOrder(ctx context.Context, systemID string, context map[string]any, order []string) (map[string]any, error) {
	return m.setBootOrderResult, m.setBootOrderErr
}

func newTestRegistry(driverName, socketPath string) *Registry {
	reg := NewRegistry()
	reg.Register(SocketDriver{
		Name:       driverName,
		SocketPath: socketPath,
		Metadata:   map[string]any{"name": driverName},
	})
	return reg
}

func newTestLogger() *slog.Logger {
	return slog.New(&discardHandler{})
}

type discardHandler struct{}

func (h discardHandler) Enabled(context.Context, slog.Level) bool { return true }
func (h discardHandler) Handle(ctx context.Context, r slog.Record) error { return nil }
func (h discardHandler) WithAttrs(attrs []slog.Attr) slog.Handler       { return h }
func (h discardHandler) WithGroup(name string) slog.Handler             { return h }

func setupPowerServiceTest(t *testing.T, mock *mockSocketClient) (*PowerService, *testsuite.TestActivityEnvironment) {
	t.Helper()

	reg := newTestRegistry("redfish", "/tmp/redfish.sock")
	logger := newTestLogger()

	ps := &PowerService{
		registry: reg,
		logger:   logger,
	}

	// Override the factory to return our mock
	socketClientFactory = func(logger *slog.Logger, socketPath string) socketClient {
		return mock
	}
	t.Cleanup(func() {
		// Restore default factory
		socketClientFactory = func(logger *slog.Logger, socketPath string) socketClient {
			return NewSocketClient(logger, socketPath)
		}
	})

	testSuite := &testsuite.WorkflowTestSuite{}
	testSuite.SetLogger(nil)

	env := testSuite.NewTestActivityEnvironment()

	return ps, env
}

func TestPowerOn(t *testing.T) {
	param := PowerOnParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "redfish",
		},
	}

	expectedResult := PowerOnResult{State: "on"}

	mock := &mockSocketClient{onResult: map[string]any{"state": "on"}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerOn)

	val, err := env.ExecuteActivity(ps.PowerOn, param)

	assert.NoError(t, err)

	var res PowerOnResult
	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestPowerOnDriverNotFound(t *testing.T) {
	param := PowerOnParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
			},
			DriverType: "unknown",
		},
	}

	reg := NewRegistry()
	logger := newTestLogger()
	ps := &PowerService{
		registry: reg,
		logger:   logger,
	}

	testSuite := &testsuite.WorkflowTestSuite{}

	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(ps.PowerOn)

	_, err := env.ExecuteActivity(ps.PowerOn, param)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not found in registry")
}

func TestPowerOnDefaultState(t *testing.T) {
	param := PowerOnParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
			},
			DriverType: "redfish",
		},
	}

	// Driver returns no state field — should default to "on"
	mock := &mockSocketClient{onResult: map[string]any{}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerOn)

	val, err := env.ExecuteActivity(ps.PowerOn, param)

	assert.NoError(t, err)

	var res PowerOnResult
	assert.NoError(t, val.Get(&res))
	assert.Equal(t, "on", res.State)
}

func TestPowerOnWrongState(t *testing.T) {
	param := PowerOnParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
			},
			DriverType: "redfish",
		},
	}

	mock := &mockSocketClient{onResult: map[string]any{"state": "off"}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerOn)

	_, err := env.ExecuteActivity(ps.PowerOn, param)
	assert.Error(t, err)
	assert.True(t, strings.Contains(err.Error(), "wrong power state"))
}

func TestPowerOff(t *testing.T) {
	param := PowerOffParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "redfish",
		},
	}

	expectedResult := PowerOffResult{State: "off"}

	mock := &mockSocketClient{offResult: map[string]any{"state": "off"}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerOff)

	val, err := env.ExecuteActivity(ps.PowerOff, param)

	assert.NoError(t, err)

	var res PowerOffResult
	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestPowerOffDefaultState(t *testing.T) {
	param := PowerOffParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
			},
			DriverType: "redfish",
		},
	}

	// Driver returns no state field — should default to "off"
	mock := &mockSocketClient{offResult: map[string]any{}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerOff)

	val, err := env.ExecuteActivity(ps.PowerOff, param)

	assert.NoError(t, err)

	var res PowerOffResult
	assert.NoError(t, val.Get(&res))
	assert.Equal(t, "off", res.State)
}

func TestPowerOffWrongState(t *testing.T) {
	param := PowerOffParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
			},
			DriverType: "redfish",
		},
	}

	mock := &mockSocketClient{offResult: map[string]any{"state": "on"}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerOff)

	_, err := env.ExecuteActivity(ps.PowerOff, param)
	assert.Error(t, err)
	assert.True(t, strings.Contains(err.Error(), "wrong power state"))
}

func TestPowerCycle(t *testing.T) {
	param := PowerCycleParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "redfish",
		},
	}

	expectedResult := PowerCycleResult{State: "on"}

	mock := &mockSocketClient{cycleResult: map[string]any{"state": "on"}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerCycle)

	val, err := env.ExecuteActivity(ps.PowerCycle, param)

	assert.NoError(t, err)

	var res PowerCycleResult
	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestPowerCycleDefaultState(t *testing.T) {
	param := PowerCycleParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
			},
			DriverType: "redfish",
		},
	}

	// Driver returns no state field — should default to "on"
	mock := &mockSocketClient{cycleResult: map[string]any{}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerCycle)

	val, err := env.ExecuteActivity(ps.PowerCycle, param)

	assert.NoError(t, err)

	var res PowerCycleResult
	assert.NoError(t, val.Get(&res))
	assert.Equal(t, "on", res.State)
}

func TestPowerCycleWrongState(t *testing.T) {
	param := PowerCycleParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
			},
			DriverType: "redfish",
		},
	}

	mock := &mockSocketClient{cycleResult: map[string]any{"state": "off"}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerCycle)

	_, err := env.ExecuteActivity(ps.PowerCycle, param)
	assert.Error(t, err)
	assert.True(t, strings.Contains(err.Error(), "wrong power state"))
}

func TestPowerQuery(t *testing.T) {
	param := PowerQueryParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "redfish",
		},
	}

	expectedResult := PowerQueryResult{State: "off"}

	mock := &mockSocketClient{queryResult: map[string]any{"state": "off"}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerQuery)

	val, err := env.ExecuteActivity(ps.PowerQuery, param)

	assert.NoError(t, err)

	var res PowerQueryResult
	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestPowerReset(t *testing.T) {
	param := PowerResetParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "redfish",
		},
	}

	expectedResult := PowerResetResult{State: "on"}

	mock := &mockSocketClient{resetResult: map[string]any{"state": "on"}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerReset)

	val, err := env.ExecuteActivity(ps.PowerReset, param)

	assert.NoError(t, err)

	var res PowerResetResult
	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestPowerResetDefaultState(t *testing.T) {
	param := PowerResetParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
			},
			DriverType: "redfish",
		},
	}

	// Driver returns no state field — should default to "on"
	mock := &mockSocketClient{resetResult: map[string]any{}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerReset)

	val, err := env.ExecuteActivity(ps.PowerReset, param)

	assert.NoError(t, err)

	var res PowerResetResult
	assert.NoError(t, val.Get(&res))
	assert.Equal(t, "on", res.State)
}

func TestPowerResetWrongState(t *testing.T) {
	param := PowerResetParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
			},
			DriverType: "redfish",
		},
	}

	mock := &mockSocketClient{resetResult: map[string]any{"state": "off"}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.PowerReset)

	_, err := env.ExecuteActivity(ps.PowerReset, param)
	assert.Error(t, err)
	assert.True(t, strings.Contains(err.Error(), "wrong power state"))
}

func TestSetBootOrder(t *testing.T) {
	param := SetBootOrderParam{
		SystemID: "abc123",
		PowerParams: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
			},
			DriverType: "redfish",
		},
		Order: []map[string]any{
			{"device_index": 0},
			{"device_index": 1},
		},
	}

	mock := &mockSocketClient{setBootOrderResult: map[string]any{}}
	ps, env := setupPowerServiceTest(t, mock)

	env.RegisterActivity(ps.SetBootOrder)

	_, err := env.ExecuteActivity(ps.SetBootOrder, param)
	assert.NoError(t, err)
}

func TestSetBootOrderDriverNotFound(t *testing.T) {
	param := SetBootOrderParam{
		SystemID: "abc123",
		PowerParams: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
			},
			DriverType: "unknown",
		},
		Order: []map[string]any{},
	}

	reg := NewRegistry()
	logger := newTestLogger()
	ps := &PowerService{
		registry: reg,
		logger:   logger,
	}

	testSuite := &testsuite.WorkflowTestSuite{}

	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(ps.SetBootOrder)

	_, err := env.ExecuteActivity(ps.SetBootOrder, param)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not found in registry")
}
