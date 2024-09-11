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

	"github.com/snapcore/snapd/systemd"
	"github.com/stretchr/testify/assert"
)

type mockSystemdClient struct {
	systemd.Systemd
	StartCalls    [][]string
	StopCalls     [][]string
	RestartCalls  [][]string
	StatusCalls   [][]string
	StatusReturns [][]*systemd.UnitStatus
}

func (m *mockSystemdClient) Start(args []string) error {
	m.StartCalls = append(m.StartCalls, args)
	return nil
}

func (m *mockSystemdClient) Stop(args []string) error {
	m.StopCalls = append(m.StopCalls, args)
	return nil
}

func (m *mockSystemdClient) Restart(args []string) error {
	m.RestartCalls = append(m.RestartCalls, args)
	return nil
}

func (m *mockSystemdClient) Status(args []string) ([]*systemd.UnitStatus, error) {
	m.StatusCalls = append(m.StatusCalls, args)
	result := m.StatusReturns[0]

	if len(m.StatusReturns) > 1 {
		m.StatusReturns = m.StatusReturns[1:]
	} else {
		m.StatusReturns = [][]*systemd.UnitStatus{}
	}

	return result, nil
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

	assert.Equal(t, [][]string{{"test-unit.service"}}, client.StartCalls)
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

	assert.Equal(t, [][]string{{"test-unit.service"}}, client.StopCalls)
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

	assert.Equal(t, [][]string{{"test-unit.service"}}, client.RestartCalls)
}

func TestSystemdControllerStatus(t *testing.T) {
	expectedout := []ServiceStatus{StatusRunning, StatusStopped}
	client := &mockSystemdClient{
		StatusReturns: [][]*systemd.UnitStatus{
			{
				{
					Active: true,
				},
			},
			{
				{
					Active: false,
				},
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

	assert.Equal(t, len(expectedout), len(client.StatusCalls))
}
