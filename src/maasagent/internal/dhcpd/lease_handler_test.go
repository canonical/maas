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
	"container/heap"
	"context"
	"encoding/json"
	"errors"
	"net"
	"reflect"
	"testing"

	"github.com/stretchr/testify/assert"
)

type MockSocketConn struct {
	net.Conn
	Messages [][]byte
}

func (m *MockSocketConn) pop() []byte {
	if len(m.Messages) == 0 {
		return nil
	}

	x := m.Messages[0]
	m.Messages = m.Messages[1:]

	return x
}

func (m *MockSocketConn) Read(b []byte) (int, error) {
	msg := m.pop()

	if len(msg) > 0 {
		copy(b, msg)
	}

	return len(msg), nil
}

func (m *MockSocketConn) Close() error {
	return nil
}

func marshalNotification(n Notification) []byte {
	b, _ := json.Marshal(n)

	return b
}

func TestLeaseHandlerRead(t *testing.T) {
	table := []struct {
		Name     string
		Conn     net.Conn
		Expected []Notification
		Err      error
	}{
		{
			Name: "one_notification_one_packet",
			Conn: &MockSocketConn{
				Messages: [][]byte{
					marshalNotification(
						Notification{
							Action:    "commit",
							MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x05}),
							IPFamily:  "IPv4",
							IP:        net.ParseIP("10.0.0.1"),
							Timestamp: 20,
							LeaseTime: 10,
							Hostname:  "example",
						}),
				},
			},
			Expected: []Notification{
				{
					Action:    "commit",
					MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x05}),
					IPFamily:  "IPv4",
					IP:        net.ParseIP("10.0.0.1"),
					Timestamp: 20,
					LeaseTime: 10,
					Hostname:  "example",
				},
			},
		},
		{
			Name: "multiple_notifications_one_packet_each",
			Conn: &MockSocketConn{
				Messages: [][]byte{
					marshalNotification(
						Notification{
							Action:    "commit",
							MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x05}),
							IPFamily:  "IPv4",
							IP:        net.ParseIP("10.0.0.1"),
							Timestamp: 20,
							LeaseTime: 10,
							Hostname:  "example",
						}),
					marshalNotification(
						Notification{
							Action:    "commit",
							MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x06}),
							IPFamily:  "IPv4",
							IP:        net.ParseIP("10.0.0.2"),
							Timestamp: 21,
							LeaseTime: 10,
							Hostname:  "example",
						}),
				},
			},
			Expected: []Notification{
				{
					Action:    "commit",
					MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x05}),
					IPFamily:  "IPv4",
					IP:        net.ParseIP("10.0.0.1"),
					Timestamp: 20,
					LeaseTime: 10,
					Hostname:  "example",
				},
				{
					Action:    "commit",
					MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x06}),
					IPFamily:  "IPv4",
					IP:        net.ParseIP("10.0.0.2"),
					Timestamp: 21,
					LeaseTime: 10,
					Hostname:  "example",
				},
			},
		},
		{
			Name: "malformed",
			Conn: &MockSocketConn{
				Messages: [][]byte{
					[]byte("{abc}"),
				},
			},
			Expected: make([]Notification, 1), // 1 to force an iteration
			Err:      &json.SyntaxError{},
		},
	}

	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			l := &LeaseHandler{conn: tcase.Conn}

			ctx, cancel := context.WithCancel(context.Background())

			defer cancel()

			deadline, ok := tt.Deadline()
			if ok {
				var cancelDeadline context.CancelFunc

				ctx, cancelDeadline = context.WithDeadline(ctx, deadline)

				defer cancelDeadline()
			}

			notifications, errorChan := l.Read(ctx)

		loop:
			for _, exp := range tcase.Expected {
				select {
				case notification := <-notifications:
					assert.Equal(tt, notification, exp)
				case err := <-errorChan:
					if tcase.Err != nil {
						assert.True(tt, errors.Is(err, tcase.Err) || reflect.TypeOf(err) == reflect.TypeOf(tcase.Err))
						break loop
					}

					if err != nil {
						tt.Fatal(err)
					}
				}
			}
		})
	}
}

func TestLeaseHandlerStart(t *testing.T) {
	table := []struct {
		Name     string
		Conn     net.Conn
		Expected []Notification
	}{
		{
			Name: "one_message",
			Conn: &MockSocketConn{
				Messages: [][]byte{
					marshalNotification(
						Notification{
							Action:    "commit",
							MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x05}),
							IPFamily:  "IPv4",
							IP:        net.ParseIP("10.0.0.1"),
							Timestamp: 20,
							LeaseTime: 10,
							Hostname:  "example",
						}),
				},
			},
			Expected: []Notification{
				{
					Action:    "commit",
					MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x05}),
					IPFamily:  "IPv4",
					IP:        net.ParseIP("10.0.0.1"),
					Timestamp: 20,
					LeaseTime: 10,
					Hostname:  "example",
				},
			},
		},
		{
			Name: "multiple_messages",
			Conn: &MockSocketConn{
				Messages: [][]byte{
					marshalNotification(
						Notification{
							Action:    "commit",
							MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x05}),
							IPFamily:  "IPv4",
							IP:        net.ParseIP("10.0.0.1"),
							Timestamp: 20,
							LeaseTime: 10,
							Hostname:  "example",
						}),
					marshalNotification(
						Notification{
							Action:    "commit",
							MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x06}),
							IPFamily:  "IPv4",
							IP:        net.ParseIP("10.0.0.2"),
							Timestamp: 21,
							LeaseTime: 10,
							Hostname:  "example",
						}),
				},
			},
			Expected: []Notification{
				{
					Action:    "commit",
					MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x05}),
					IPFamily:  "IPv4",
					IP:        net.ParseIP("10.0.0.1"),
					Timestamp: 20,
					LeaseTime: 10,
					Hostname:  "example",
				},
				{
					Action:    "commit",
					MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x06}),
					IPFamily:  "IPv4",
					IP:        net.ParseIP("10.0.0.2"),
					Timestamp: 21,
					LeaseTime: 10,
					Hostname:  "example",
				},
			},
		},
		{
			Name: "out_of_order_messages",
			Conn: &MockSocketConn{
				Messages: [][]byte{
					marshalNotification(
						Notification{
							Action:    "commit",
							MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x06}),
							IPFamily:  "IPv4",
							IP:        net.ParseIP("10.0.0.2"),
							Timestamp: 21,
							LeaseTime: 10,
							Hostname:  "example",
						}),
					marshalNotification(
						Notification{
							Action:    "commit",
							MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x05}),
							IPFamily:  "IPv4",
							IP:        net.ParseIP("10.0.0.1"),
							Timestamp: 20,
							LeaseTime: 10,
							Hostname:  "example",
						}),
				},
			},
			Expected: []Notification{
				{
					Action:    "commit",
					MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x05}),
					IPFamily:  "IPv4",
					IP:        net.ParseIP("10.0.0.1"),
					Timestamp: 20,
					LeaseTime: 10,
					Hostname:  "example",
				},
				{
					Action:    "commit",
					MAC:       net.HardwareAddr([]byte{0x00, 0x01, 0x02, 0x03, 0x04, 0x06}),
					IPFamily:  "IPv4",
					IP:        net.ParseIP("10.0.0.2"),
					Timestamp: 21,
					LeaseTime: 10,
					Hostname:  "example",
				},
			},
		},
	}

	for _, tcase := range table {
		t.Run(tcase.Name, func(tt *testing.T) {
			ls := NewLeaseHeap()
			lh := &LeaseHandler{conn: tcase.Conn, store: ls}

			ctx, cancel := context.WithCancel(context.Background())

			defer cancel()

			deadline, ok := tt.Deadline()
			if ok {
				var cancelDeadline context.CancelFunc

				ctx, cancelDeadline = context.WithDeadline(ctx, deadline)

				defer cancelDeadline()
			}

			go lh.Start(ctx)

			for ls.Len() < len(tcase.Expected) { // block until heap has elements
			}

			for _, exp := range tcase.Expected {
				result := heap.Pop(ls)

				notification := result.(Notification)

				assert.Equal(tt, notification, exp)
			}
		})
	}
}
