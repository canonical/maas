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

	pebble "github.com/canonical/pebble/client"
	"github.com/stretchr/testify/assert"
)

func TestNewPebbleController(t *testing.T) {
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

			pebbleCtrlr, err := NewPebbleController("test.service")
			assert.NoError(t, err)

			assert.Equal(t, tc.out.Socket, pebbleCtrlr.config.Socket)
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

	pebbleCtrlr := &PebbleController{
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

	pebbleCtrlr := &PebbleController{
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

	pebbleCtrlr := &PebbleController{
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
	expectedout := []ServiceStatus{
		StatusRunning,
		StatusStopped,
		StatusError,
		StatusError,
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

	pebbleCtrlr := &PebbleController{
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
