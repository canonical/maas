// Copyright (c) 2023-2024 Canonical Ltd
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

package servicecontroller

import (
	"context"
	"testing"

	"github.com/stretchr/testify/assert"
)

type mockSystemdClient struct {
	outputCalls         [][]string
	combinedOutputCalls [][]string
	outputReturnValues  []struct {
		out string
		err error
	}
	combinedOutputReturnValues []struct {
		out string
		err error
	}
}

func (m *mockSystemdClient) OutputSystemctlCommand(_ context.Context, args ...string) (string, error) {
	m.outputCalls = append(m.outputCalls, args)

	if len(m.outputReturnValues) > 0 {
		out := m.outputReturnValues[0].out
		err := m.outputReturnValues[0].err

		if len(m.outputReturnValues) > 1 {
			m.outputReturnValues = m.outputReturnValues[1:]
		} else {
			m.outputReturnValues = nil
		}

		return out, err
	}

	return "", nil
}

func (m *mockSystemdClient) CombinedOutputSystemctlCommand(_ context.Context, args ...string) (string, error) {
	m.combinedOutputCalls = append(m.combinedOutputCalls, args)

	if len(m.combinedOutputReturnValues) > 0 {
		out := m.combinedOutputReturnValues[0].out
		err := m.combinedOutputReturnValues[0].err

		if len(m.combinedOutputReturnValues) > 1 {
			m.combinedOutputReturnValues = m.combinedOutputReturnValues[1:]
		} else {
			m.combinedOutputReturnValues = nil
		}

		return out, err
	}

	return "", nil
}

func TestSystemdControllerStart(t *testing.T) {
	client := &mockSystemdClient{}
	systemdCtrlr := &SystemdController{
		unit:   "test-unit.service",
		client: client,
	}

	err := systemdCtrlr.Start(context.TODO())
	if err != nil {
		t.Fatal(err)
	}

	assert.Equal(t, [][]string{{"start", "test-unit.service"}}, client.combinedOutputCalls)
}

func TestSystemdControllerStop(t *testing.T) {
	client := &mockSystemdClient{}
	systemdCtrlr := &SystemdController{
		unit:   "test-unit.service",
		client: client,
	}

	err := systemdCtrlr.Stop(context.TODO())
	if err != nil {
		t.Fatal(err)
	}

	assert.Equal(t, [][]string{{"stop", "test-unit.service"}}, client.combinedOutputCalls)
}

func TestSystemdControllerRestart(t *testing.T) {
	client := &mockSystemdClient{}
	systemdCtrlr := &SystemdController{
		unit:   "test-unit.service",
		client: client,
	}

	err := systemdCtrlr.Restart(context.TODO())
	if err != nil {
		t.Fatal(err)
	}

	assert.Equal(t, [][]string{{"restart", "test-unit.service"}}, client.combinedOutputCalls)
}

func TestSystemdControllerStatus(t *testing.T) {
	expectedout := []ServiceStatus{StatusRunning, StatusStopped}
	client := &mockSystemdClient{
		outputReturnValues: []struct {
			out string
			err error
		}{
			{
				out: "ActiveState=active",
			},
			{
				out: "ActiveState=inactive",
			},
		},
	}
	systemdCtrlr := &SystemdController{
		client: client,
		unit:   "test-unit.service",
	}

	for _, expected := range expectedout {
		result, err := systemdCtrlr.Status(context.TODO())
		if err != nil {
			t.Fatal(err)
		}

		assert.Equal(t, expected, result)
	}

	assert.Equal(t, len(expectedout), len(client.outputCalls))
}
