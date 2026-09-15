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
	"bytes"
	"context"
	"encoding/json"
	"testing"

	"github.com/stretchr/testify/assert"
	tlog "go.temporal.io/sdk/log"
	"go.temporal.io/sdk/testsuite"
	"maas.io/core/src/maasagent/internal/logger"
)

const expectedMAASCLIName = "maas.power"

type testPowerProc struct {
	name string
	arg  []string
}

func (t testPowerProc) Run() error {
	return nil
}

func TestFmtPowerOpts(t *testing.T) {
	testcases := map[string]struct {
		in  map[string]any
		out []string
	}{
		"single numeric argument": {
			in:  map[string]any{"key1": 1},
			out: []string{"--key1", "1"},
		},
		"single string argument": {
			in:  map[string]any{"key1": "value1"},
			out: []string{"--key1", "value1"},
		},
		"multiple string arguments": {
			in:  map[string]any{"key1": "value1", "key2": "value2"},
			out: []string{"--key1", "value1", "--key2", "value2"},
		},
		"multi choice string argument": {
			in:  map[string]any{"key1": []string{"value1", "value2"}},
			out: []string{"--key1", "value1", "--key1", "value2"},
		},
		"argument value with line breaks": {
			in:  map[string]any{"key1": "multi\nline\nstring"},
			out: []string{"--key1", "multi\nline\nstring"},
		},
		"ignore system_id": {
			in:  map[string]any{"system_id": "value1"},
			out: []string{},
		},
		"ignore null": {
			in:  map[string]any{"key1": nil},
			out: []string{},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			res := fmtPowerOpts(tc.in)
			assert.ElementsMatch(t, tc.out, res)
		})
	}
}

func TestPowerOn(t *testing.T) {
	// Setup a redfish power on activity input
	param := PowerOnParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "Redfish",
		},
	}

	// Define the arguments expect the `maas.power` command to be called with
	expectedArgs := append([]string{"on", param.DriverType}, fmtPowerOpts(param.DriverOpts)...)

	expectedResult := PowerOnResult{
		State: "on",
	}

	// Override the factories defined in service.go with mocks
	var mockedPowerProc testPowerProc

	procFactory = func(_ context.Context, stdout, _ *bytes.Buffer, name string, arg ...string) powerProc {
		mockedPowerProc = testPowerProc{
			name: name,
			arg:  arg,
		}

		stdout.WriteString("on")

		return mockedPowerProc
	}

	pathFactory = func(_ string) (string, error) {
		return expectedMAASCLIName, nil
	}

	ps := PowerService{}

	// Setup the environment to test a temporal activity with
	testSuite := &testsuite.WorkflowTestSuite{}
	testSuite.SetLogger(tlog.NewStructuredLogger(logger.Noop()))

	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(ps.PowerOn)

	// Run the activity/test
	val, err := env.ExecuteActivity(ps.PowerOn, param)

	// Ensure the powerCommand was called correctly
	assert.Equal(t, expectedMAASCLIName, mockedPowerProc.name)
	assert.ElementsMatch(t, expectedArgs, mockedPowerProc.arg)

	// Ensure the power command returns the anticipated state, without error
	assert.NoError(t, err)

	var res PowerOnResult

	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestPowerOff(t *testing.T) {
	// Setup a redfish power off activity input
	param := PowerOffParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "Redfish",
		},
	}

	// Define the arguments expect the `maas.power` command to be called with
	expectedArgs := append([]string{"off", param.DriverType}, fmtPowerOpts(param.DriverOpts)...)

	expectedResult := PowerOffResult{
		State: "off",
	}

	// Override the factories defined in service.go with mocks
	var mockedPowerProc testPowerProc

	procFactory = func(_ context.Context, stdout, _ *bytes.Buffer, name string, arg ...string) powerProc {
		mockedPowerProc = testPowerProc{
			name: name,
			arg:  arg,
		}

		stdout.WriteString("off")

		return mockedPowerProc
	}

	pathFactory = func(_ string) (string, error) {
		return expectedMAASCLIName, nil
	}

	ps := PowerService{}

	// Setup the environment to test a temporal activity with
	testSuite := &testsuite.WorkflowTestSuite{}
	testSuite.SetLogger(tlog.NewStructuredLogger(logger.Noop()))

	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(ps.PowerOff)

	// Run the activity/test
	val, err := env.ExecuteActivity(ps.PowerOff, param)

	// Ensure the powerCommand was called correctly
	assert.Equal(t, expectedMAASCLIName, mockedPowerProc.name)
	assert.ElementsMatch(t, expectedArgs, mockedPowerProc.arg)

	// Ensure the power command returns the anticipated state, without error
	assert.NoError(t, err)

	var res PowerOffResult

	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestPowerCycle(t *testing.T) {
	// Setup a redfish power cycle activity input
	param := PowerCycleParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "Redfish",
		},
	}

	// Define the arguments expect the `maas.power` command to be called with
	expectedArgs := append([]string{"cycle", param.DriverType}, fmtPowerOpts(param.DriverOpts)...)

	expectedResult := PowerCycleResult{
		State: "on",
	}

	// Override the factories defined in service.go with mocks
	var mockedPowerProc testPowerProc

	procFactory = func(_ context.Context, stdout, _ *bytes.Buffer, name string, arg ...string) powerProc {
		mockedPowerProc = testPowerProc{
			name: name,
			arg:  arg,
		}

		stdout.WriteString("on")

		return mockedPowerProc
	}

	pathFactory = func(_ string) (string, error) {
		return expectedMAASCLIName, nil
	}

	ps := PowerService{}

	// Setup the environment to test a temporal activity with
	testSuite := &testsuite.WorkflowTestSuite{}
	testSuite.SetLogger(tlog.NewStructuredLogger(logger.Noop()))

	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(ps.PowerCycle)

	// Run the activity/test
	val, err := env.ExecuteActivity(ps.PowerCycle, param)

	// Ensure the powerCommand was called correctly
	assert.Equal(t, expectedMAASCLIName, mockedPowerProc.name)
	assert.ElementsMatch(t, expectedArgs, mockedPowerProc.arg)

	// Ensure the power command returns the anticipated state, without error
	assert.NoError(t, err)

	var res PowerCycleResult

	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestPowerQuery(t *testing.T) {
	// Setup a redfish power query activity input
	param := PowerQueryParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "Redfish",
		},
	}

	// Define the arguments expect the `maas.power` command to be called with
	expectedArgs := append([]string{"status", param.DriverType}, fmtPowerOpts(param.DriverOpts)...)

	expectedResult := PowerQueryResult{
		State: "off",
	}

	// Override the factories defined in service.go with mocks
	var mockedPowerProc testPowerProc

	procFactory = func(_ context.Context, stdout, _ *bytes.Buffer, name string, arg ...string) powerProc {
		mockedPowerProc = testPowerProc{
			name: name,
			arg:  arg,
		}

		stdout.WriteString("off")

		return mockedPowerProc
	}

	pathFactory = func(_ string) (string, error) {
		return expectedMAASCLIName, nil
	}

	ps := PowerService{}

	// Setup the environment to test a temporal activity with
	testSuite := &testsuite.WorkflowTestSuite{}
	testSuite.SetLogger(tlog.NewStructuredLogger(logger.Noop()))

	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(ps.PowerQuery)

	// Run the activity/test
	val, err := env.ExecuteActivity(ps.PowerQuery, param)

	// Ensure the powerCommand was called correctly
	assert.Equal(t, expectedMAASCLIName, mockedPowerProc.name)
	assert.ElementsMatch(t, expectedArgs, mockedPowerProc.arg)

	// Ensure the power command returns the anticipated state, without error
	assert.NoError(t, err)

	var res PowerQueryResult

	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestPowerReset(t *testing.T) {
	// Setup a redfish power reset activity input
	// The example below would be typical for a power reset trigger for a DPU
	param := PowerResetParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "Redfish",
		},
	}

	// Define the arguments expect the `maas.power` command to be called with
	expectedArgs := append([]string{"reset", param.DriverType}, fmtPowerOpts(param.DriverOpts)...)

	expectedResult := PowerResetResult{
		State: "on",
	}

	// Override the factories defined in service.go with mocks
	var mockedPowerProc testPowerProc

	procFactory = func(_ context.Context, stdout, _ *bytes.Buffer, name string, arg ...string) powerProc {
		mockedPowerProc = testPowerProc{
			name: name,
			arg:  arg,
		}

		stdout.WriteString("on")

		return mockedPowerProc
	}

	pathFactory = func(_ string) (string, error) {
		return expectedMAASCLIName, nil
	}

	ps := PowerService{}

	// Setup the environment to test a temporal activity with
	testSuite := &testsuite.WorkflowTestSuite{}
	testSuite.SetLogger(tlog.NewStructuredLogger(logger.Noop()))

	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(ps.PowerReset)

	// Run the activity/test
	val, err := env.ExecuteActivity(ps.PowerReset, param)

	// Ensure the powerCommand was called correctly
	assert.Equal(t, expectedMAASCLIName, mockedPowerProc.name)
	assert.ElementsMatch(t, expectedArgs, mockedPowerProc.arg)

	// Ensure the power command returns the anticipated state, without error
	assert.NoError(t, err)

	var res PowerResetResult

	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestPowerOnDPU(t *testing.T) {
	// Setup a redfish power on activity input
	param := PowerOnParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "Redfish",
			IsDPU:      true,
		},
	}

	// Define the arguments expect the `maas.power` command to be called with
	expectedArgs := append([]string{"on", param.DriverType, "--is-dpu"}, fmtPowerOpts(param.DriverOpts)...)

	expectedResult := PowerOnResult{
		State: "on",
	}

	// Override the factories defined in service.go with mocks
	var mockedPowerProc testPowerProc

	procFactory = func(_ context.Context, stdout, _ *bytes.Buffer, name string, arg ...string) powerProc {
		mockedPowerProc = testPowerProc{
			name: name,
			arg:  arg,
		}

		stdout.WriteString("on")

		return mockedPowerProc
	}

	pathFactory = func(_ string) (string, error) {
		return expectedMAASCLIName, nil
	}

	ps := PowerService{}

	// Setup the environment to test a temporal activity with
	testSuite := &testsuite.WorkflowTestSuite{}
	testSuite.SetLogger(tlog.NewStructuredLogger(logger.Noop()))

	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(ps.PowerOn)

	// Run the activity/test
	val, err := env.ExecuteActivity(ps.PowerOn, param)

	// Ensure the powerCommand was called correctly
	assert.Equal(t, expectedMAASCLIName, mockedPowerProc.name)
	assert.ElementsMatch(t, expectedArgs, mockedPowerProc.arg)

	// Ensure the power command returns the anticipated state, without error
	assert.NoError(t, err)

	var res PowerOnResult

	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestPowerCycleDPU(t *testing.T) {
	// Setup a redfish power cycle activity input
	param := PowerCycleParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "Redfish",
			IsDPU:      true,
		},
	}

	// Define the arguments expect the `maas.power` command to be called with
	expectedArgs := append([]string{"cycle", param.DriverType, "--is-dpu"}, fmtPowerOpts(param.DriverOpts)...)

	expectedResult := PowerCycleResult{
		State: "on",
	}

	// Override the factories defined in service.go with mocks
	var mockedPowerProc testPowerProc

	procFactory = func(_ context.Context, stdout, _ *bytes.Buffer, name string, arg ...string) powerProc {
		mockedPowerProc = testPowerProc{
			name: name,
			arg:  arg,
		}

		stdout.WriteString("on")

		return mockedPowerProc
	}

	pathFactory = func(_ string) (string, error) {
		return expectedMAASCLIName, nil
	}

	ps := PowerService{}

	// Setup the environment to test a temporal activity with
	testSuite := &testsuite.WorkflowTestSuite{}
	testSuite.SetLogger(tlog.NewStructuredLogger(logger.Noop()))

	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(ps.PowerCycle)

	// Run the activity/test
	val, err := env.ExecuteActivity(ps.PowerCycle, param)

	// Ensure the powerCommand was called correctly
	assert.Equal(t, expectedMAASCLIName, mockedPowerProc.name)
	assert.ElementsMatch(t, expectedArgs, mockedPowerProc.arg)

	// Ensure the power command returns the anticipated state, without error
	assert.NoError(t, err)

	var res PowerCycleResult

	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestPowerResetDPU(t *testing.T) {
	// Setup a redfish power reset activity input
	// The example below would be typical for a power reset trigger for a DPU
	param := PowerResetParam{
		PowerParam: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "redfish",
			IsDPU:      true,
		},
	}

	// Define the arguments expect the `maas.power` command to be called with
	expectedArgs := append([]string{"reset", param.DriverType, "--is-dpu"}, fmtPowerOpts(param.DriverOpts)...)

	expectedResult := PowerResetResult{
		State: "on",
	}

	// Override the factories defined in service.go with mocks
	var mockedPowerProc testPowerProc

	procFactory = func(_ context.Context, stdout, _ *bytes.Buffer, name string, arg ...string) powerProc {
		mockedPowerProc = testPowerProc{
			name: name,
			arg:  arg,
		}

		stdout.WriteString("on")

		return mockedPowerProc
	}

	pathFactory = func(_ string) (string, error) {
		return expectedMAASCLIName, nil
	}

	ps := PowerService{}

	// Setup the environment to test a temporal activity with
	testSuite := &testsuite.WorkflowTestSuite{}
	testSuite.SetLogger(tlog.NewStructuredLogger(logger.Noop()))

	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(ps.PowerReset)

	// Run the activity/test
	val, err := env.ExecuteActivity(ps.PowerReset, param)

	// Ensure the powerCommand was called correctly
	assert.Equal(t, expectedMAASCLIName, mockedPowerProc.name)
	assert.ElementsMatch(t, expectedArgs, mockedPowerProc.arg)

	// Ensure the power command returns the anticipated state, without error
	assert.NoError(t, err)

	var res PowerResetResult

	assert.NoError(t, val.Get(&res))
	assert.Equal(t, expectedResult.State, res.State)
}

func TestSetBootOrder(t *testing.T) {
	// Setup a set-boot-order activity input. The driver type and options are
	// carried inside the nested PowerParams (unlike the flat power actions).
	param := SetBootOrderParam{
		SystemID: "abc123",
		PowerParams: PowerParam{
			DriverOpts: map[string]any{
				"power_address": "0.0.0.0",
				"power_user":    "maas",
				"power_pass":    "maas",
			},
			DriverType: "hmcz",
		},
		Order: []map[string]any{{"id": 1}},
	}

	// The CLI is invoked with the driver taken from PowerParams and the boot
	// order forwarded as a JSON array. If the PowerParams were not decoded
	// (e.g. json tag drift), DriverType would be empty and the driver argument
	// would be "".
	orderJSON, err := json.Marshal(param.Order)
	assert.NoError(t, err)

	expectedArgs := append(
		[]string{"set-boot-order", param.PowerParams.DriverType},
		fmtPowerOpts(param.PowerParams.DriverOpts)...,
	)
	expectedArgs = append(expectedArgs, "--order", string(orderJSON))

	// Override the factories defined in service.go with mocks
	var mockedPowerProc testPowerProc

	procFactory = func(_ context.Context, _, _ *bytes.Buffer, name string, arg ...string) powerProc {
		mockedPowerProc = testPowerProc{
			name: name,
			arg:  arg,
		}

		return mockedPowerProc
	}

	pathFactory = func(_ string) (string, error) {
		return expectedMAASCLIName, nil
	}

	ps := PowerService{}

	// Setup the environment to test a temporal activity with
	testSuite := &testsuite.WorkflowTestSuite{}
	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(ps.SetBootOrder)

	// Run the activity/test
	_, err = env.ExecuteActivity(ps.SetBootOrder, param)

	// Ensure the powerCommand was called correctly
	assert.Equal(t, expectedMAASCLIName, mockedPowerProc.name)
	assert.ElementsMatch(t, expectedArgs, mockedPowerProc.arg)
	assert.NoError(t, err)
}

// TestSetBootOrderEmptyOrderOmitsFlag ensures no empty "--order ”" is emitted
// when the boot order is empty; an empty --order is rejected by the maas.power
// CLI (unrecognized argument).
func TestSetBootOrderEmptyOrderOmitsFlag(t *testing.T) {
	param := SetBootOrderParam{
		SystemID: "abc123",
		PowerParams: PowerParam{
			DriverOpts: map[string]any{"power_address": "0.0.0.0"},
			DriverType: "hmcz",
		},
		Order: nil,
	}

	var mockedPowerProc testPowerProc

	procFactory = func(_ context.Context, _, _ *bytes.Buffer, name string, arg ...string) powerProc {
		mockedPowerProc = testPowerProc{
			name: name,
			arg:  arg,
		}

		return mockedPowerProc
	}

	pathFactory = func(_ string) (string, error) {
		return expectedMAASCLIName, nil
	}

	ps := PowerService{}

	testSuite := &testsuite.WorkflowTestSuite{}
	env := testSuite.NewTestActivityEnvironment()
	env.RegisterActivity(ps.SetBootOrder)

	_, err := env.ExecuteActivity(ps.SetBootOrder, param)

	assert.NoError(t, err)
	assert.NotContains(t, mockedPowerProc.arg, "--order")
}

// TestSetBootOrderParamJSONContract pins the Go struct to the wire contract
// produced by the Python workflow
// (maastemporalworker.workflow.deploy.SetBootOrderParam). Python serializes the
// nested power parameters under the key "power_params"; the Go activity MUST
// decode that exact key. A drift in the json tag (e.g. "power_param") would
// silently leave PowerParams empty and break set-boot-order at runtime.
//
// This must decode a literal payload rather than round-trip a Go value: a Go
// marshal/unmarshal round-trip uses the same (possibly wrong) tag in both
// directions and is therefore symmetric, so it cannot detect the mismatch.
func TestSetBootOrderParamJSONContract(t *testing.T) {
	// Mirrors exactly what the Python side emits, including the extra
	// system_id/task_queue fields on PowerParam that Go does not declare and
	// harmlessly ignores.
	raw := []byte(`{
		"system_id": "abc123",
		"power_params": {
			"system_id": "abc123",
			"driver_type": "hmcz",
			"driver_opts": {"power_address": "10.0.0.1", "power_user": "maas"},
			"task_queue": "agent:power@vlan-1",
			"is_dpu": false
		},
		"order": [{"id": 1}]
	}`)

	var param SetBootOrderParam

	assert.NoError(t, json.Unmarshal(raw, &param))

	assert.Equal(t, "abc123", param.SystemID)
	// The key assertion: the nested power params decoded from "power_params".
	assert.Equal(t, "hmcz", param.PowerParams.DriverType)
	assert.Equal(t, "10.0.0.1", param.PowerParams.DriverOpts["power_address"])
	assert.False(t, param.PowerParams.IsDPU)
	assert.Len(t, param.Order, 1)
}
