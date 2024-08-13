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

package dhcpd

import (
	"context"
	"testing"

	pebble "github.com/canonical/pebble/client"
	"github.com/snapcore/snapd/systemd"
	"github.com/stretchr/testify/assert"
)

func TestNewDhcpdController(t *testing.T) {
	testcases := map[string]struct {
		env map[string]string
		in  DhcpdVersion
		out DhcpdController
	}{
		"deb dhcpd": {
			in: DhcpdVersion4,
			out: &systemdController{
				unit: "dhcpd.service",
			},
		},
		"deb dhcpd6": {
			in: DhcpdVersion6,
			out: &systemdController{
				unit: "dhcpd6.service",
			},
		},
		"snap dhcpd": {
			env: map[string]string{"SNAP": "1"},
			in:  DhcpdVersion4,
			out: &pebbleController{
				service: "dhcpd",
			},
		},
		"snap dhcpd6": {
			env: map[string]string{"SNAP": "1"},
			in:  DhcpdVersion6,
			out: &pebbleController{
				service: "dhcpd6",
			},
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			var err error

			for k, v := range tc.env {
				t.Setenv(k, v)
			}

			controller, err := NewDhcpdController(tc.in)
			if err != nil {
				t.Fatal(err)
			}

			if expected, ok := tc.out.(*systemdController); ok {
				ctrlr, ok := controller.(*systemdController)

				assert.True(t, ok)

				assert.Equal(t, expected.unit, ctrlr.unit)
			} else {
				expected, ok := tc.out.(*pebbleController)
				if !ok {
					t.Fatal("invalid expected type")
				}

				ctrlr, ok := controller.(*pebbleController)

				assert.True(t, ok)

				assert.Equal(t, expected.service, ctrlr.service)
			}
		})
	}
}

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
	systemdCtrlr := &systemdController{
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
	systemdCtrlr := &systemdController{
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
	systemdCtrlr := &systemdController{
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
	expectedout := []DhcpdStatus{DhcpdStatusRunning, DhcpdStatusStopped}
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
	systemdCtrlr := &systemdController{
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

func TestNewPebbleConfigFromEnv(t *testing.T) {
	testcases := map[string]struct {
		env map[string]string
		out *pebble.Config
	}{
		"no env set": {
			out: &pebble.Config{
				Socket: ".pebble.socket",
			},
		},
		"PEBBLE set": {
			env: map[string]string{"PEBBLE": "/testpath"},
			out: &pebble.Config{
				Socket: "/testpath/.pebble.socket",
			},
		},
		"PEBBLE_SOCKET set": {
			env: map[string]string{"PEBBLE_SOCKET": "/testpath/test.sock"},
			out: &pebble.Config{
				Socket: "/testpath/test.sock",
			},
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			for k, v := range tc.env {
				t.Setenv(k, v)
			}

			cfg := newPebbleConfigFromEnv()

			assert.Equal(t, tc.out.Socket, cfg.Socket)
		})
	}
}

type mockPebbleClient struct {
	StartCalls      []*pebble.ServiceOptions
	StartReturns    []string
	StopCalls       []*pebble.ServiceOptions
	StopReturns     []string
	RestartCalls    []*pebble.ServiceOptions
	RestartReturns  []string
	ServicesCalls   []*pebble.ServicesOptions
	ServicesReturns [][]*pebble.ServiceInfo
	WaitChangeCalls []struct {
		ChangeID string
		Opts     *pebble.WaitChangeOptions
	}
}

func (m *mockPebbleClient) Start(opts *pebble.ServiceOptions) (string, error) {
	m.StartCalls = append(m.StartCalls, opts)

	result := m.StartReturns[0]

	if len(m.StartReturns) > 1 {
		m.StartReturns = m.StartReturns[1:]
	} else {
		m.StartReturns = []string{}
	}

	return result, nil
}

func (m *mockPebbleClient) Stop(opts *pebble.ServiceOptions) (string, error) {
	m.StopCalls = append(m.StopCalls, opts)

	result := m.StopReturns[0]

	if len(m.StopReturns) > 1 {
		m.StopReturns = m.StartReturns[1:]
	} else {
		m.StopReturns = []string{}
	}

	return result, nil
}

func (m *mockPebbleClient) Restart(opts *pebble.ServiceOptions) (string, error) {
	m.RestartCalls = append(m.RestartCalls, opts)

	result := m.RestartReturns[0]

	if len(m.RestartReturns) > 1 {
		m.RestartReturns = m.RestartReturns[1:]
	} else {
		m.RestartReturns = []string{}
	}

	return result, nil
}

func (m *mockPebbleClient) WaitChange(changeID string, opts *pebble.WaitChangeOptions) (*pebble.Change, error) {
	m.WaitChangeCalls = append(m.WaitChangeCalls, struct {
		ChangeID string
		Opts     *pebble.WaitChangeOptions
	}{
		ChangeID: changeID,
		Opts:     opts,
	})

	//nolint:nilnil // while not idiomatic, this is just a test client satisfying an interface, safe to ignore
	return nil, nil
}

func (m *mockPebbleClient) Services(opts *pebble.ServicesOptions) ([]*pebble.ServiceInfo, error) {
	m.ServicesCalls = append(m.ServicesCalls, opts)

	result := m.ServicesReturns[0]

	if len(m.ServicesReturns) > 1 {
		m.ServicesReturns = m.ServicesReturns[1:]
	} else {
		m.ServicesReturns = [][]*pebble.ServiceInfo{}
	}

	return result, nil
}

func TestPebbleControllerStart(t *testing.T) {
	client := &mockPebbleClient{
		StartReturns: []string{"a"},
	}

	pebbleCtrlr := &pebbleController{
		client:  client,
		service: "test",
	}

	err := pebbleCtrlr.Start(context.TODO())
	if err != nil {
		t.Fatal(err)
	}

	assert.Equal(t, 1, len(client.StartCalls))
	assert.Equal(t, pebble.ServiceOptions{Names: []string{pebbleCtrlr.service}},
		*client.StartCalls[0])
	assert.Equal(t, 1, len(client.WaitChangeCalls))
	assert.Equal(t, "a", client.WaitChangeCalls[0].ChangeID)
}

func TestPebbleControllerStop(t *testing.T) {
	client := &mockPebbleClient{
		StopReturns: []string{"a"},
	}

	pebbleCtrlr := &pebbleController{
		client:  client,
		service: "test",
	}

	err := pebbleCtrlr.Stop(context.TODO())
	if err != nil {
		t.Fatal(err)
	}

	assert.Equal(t, 1, len(client.StopCalls))
	assert.Equal(t, pebble.ServiceOptions{Names: []string{pebbleCtrlr.service}},
		*client.StopCalls[0])
	assert.Equal(t, 1, len(client.WaitChangeCalls))
	assert.Equal(t, "a", client.WaitChangeCalls[0].ChangeID)
}

func TestPebbleControllerRestart(t *testing.T) {
	client := &mockPebbleClient{
		RestartReturns: []string{"a"},
	}

	pebbleCtrlr := &pebbleController{
		client:  client,
		service: "test",
	}

	err := pebbleCtrlr.Restart(context.TODO())
	if err != nil {
		t.Fatal(err)
	}

	assert.Equal(t, 1, len(client.RestartCalls))
	assert.Equal(t, pebble.ServiceOptions{Names: []string{pebbleCtrlr.service}},
		*client.RestartCalls[0])
	assert.Equal(t, 1, len(client.WaitChangeCalls))
	assert.Equal(t, "a", client.WaitChangeCalls[0].ChangeID)
}

func TestPebbleControllerStatus(t *testing.T) {
	expectedout := []DhcpdStatus{
		DhcpdStatusRunning,
		DhcpdStatusStopped,
		DhcpdStatusError,
		DhcpdStatusError,
	}

	client := &mockPebbleClient{
		ServicesReturns: [][]*pebble.ServiceInfo{
			{
				&pebble.ServiceInfo{
					Current: pebble.StatusActive,
				},
			},
			{
				&pebble.ServiceInfo{
					Current: pebble.StatusInactive,
				},
			},
			{
				&pebble.ServiceInfo{
					Current: pebble.StatusBackoff,
				},
			},
			{
				&pebble.ServiceInfo{
					Current: pebble.StatusError,
				},
			},
		},
	}

	pebbleCtrlr := &pebbleController{
		client:  client,
		service: "test",
	}

	for _, expected := range expectedout {
		result, err := pebbleCtrlr.Status(context.TODO())
		if err != nil {
			t.Fatal(err)
		}

		assert.Equal(t, expected, result)
	}

	assert.Equal(t, len(expectedout), len(client.ServicesCalls))
}
