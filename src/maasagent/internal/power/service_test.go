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
	"testing"

	"github.com/stretchr/testify/assert"
	"go.temporal.io/sdk/testsuite"
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

	// Define the arguments expect the `maas.power`` command to be called with
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

	// Define the arguments expect the `maas.power`` command to be called with
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

	// Define the arguments expect the `maas.power`` command to be called with
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

	// Define the arguments expect the `maas.power`` command to be called with
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

	// Define the arguments expect the `maas.power`` command to be called with
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
