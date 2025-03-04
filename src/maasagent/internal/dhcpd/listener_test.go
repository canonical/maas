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
	"encoding/json"
	"net"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
)

func TestNotificationListener(t *testing.T) {
	type out struct {
		notifications  []*Notification
		remainingItems int
	}

	testcases := map[string]struct {
		in  []*Notification
		out out
	}{
		"one message": {
			in: []*Notification{
				{
					Action:    "commit",
					MAC:       "00:00:00:00:00",
					IPFamily:  "ipv4",
					IP:        "10.0.0.1",
					Timestamp: 20,
					LeaseTime: 10,
					Hostname:  "example",
				},
			},
			out: out{
				notifications: []*Notification{
					{
						Action:    "commit",
						MAC:       "00:00:00:00:00",
						IPFamily:  "ipv4",
						IP:        "10.0.0.1",
						Timestamp: 20,
						LeaseTime: 10,
						Hostname:  "example",
					},
				},
				remainingItems: 0,
			},
		},
		"multiple messages": {
			in: []*Notification{
				{
					Action:    "commit",
					MAC:       "00:00:00:00:00",
					IPFamily:  "ipv4",
					IP:        "10.0.0.1",
					Timestamp: 20,
					LeaseTime: 10,
					Hostname:  "example",
				},
				{
					Action:    "commit",
					MAC:       "00:00:00:00:00",
					IPFamily:  "ipv4",
					IP:        "10.0.0.2",
					Timestamp: 21,
					LeaseTime: 10,
					Hostname:  "example",
				},
			},
			out: out{
				notifications: []*Notification{
					{
						Action:    "commit",
						MAC:       "00:00:00:00:00",
						IPFamily:  "ipv4",
						IP:        "10.0.0.1",
						Timestamp: 20,
						LeaseTime: 10,
						Hostname:  "example",
					},
					{
						Action:    "commit",
						MAC:       "00:00:00:00:00",
						IPFamily:  "ipv4",
						IP:        "10.0.0.2",
						Timestamp: 21,
						LeaseTime: 10,
						Hostname:  "example",
					},
				},
				remainingItems: 0,
			},
		},
		"out of order messages": {
			in: []*Notification{
				{
					Action:    "commit",
					MAC:       "00:00:00:00:00",
					IPFamily:  "ipv4",
					IP:        "10.0.0.2",
					Timestamp: 21,
					LeaseTime: 10,
					Hostname:  "example",
				},
				{
					Action:    "commit",
					MAC:       "00:00:00:00:00",
					IPFamily:  "ipv4",
					IP:        "10.0.0.1",
					Timestamp: 20,
					LeaseTime: 10,
					Hostname:  "example",
				},
			},
			out: out{
				notifications: []*Notification{
					{
						Action:    "commit",
						MAC:       "00:00:00:00:00",
						IPFamily:  "ipv4",
						IP:        "10.0.0.1",
						Timestamp: 20,
						LeaseTime: 10,
						Hostname:  "example",
					},
					{
						Action:    "commit",
						MAC:       "00:00:00:00:00",
						IPFamily:  "ipv4",
						IP:        "10.0.0.2",
						Timestamp: 21,
						LeaseTime: 10,
						Hostname:  "example",
					},
				},
				remainingItems: 0,
			},
		},
		"message from future should be ignored": {
			in: []*Notification{
				{
					Action:    "commit",
					MAC:       "00:00:00:00:00",
					IPFamily:  "ipv4",
					IP:        "10.0.0.1",
					Timestamp: 1,
					LeaseTime: 10,
					Hostname:  "example",
				},
				{
					Action:    "commit",
					MAC:       "00:00:00:00:00",
					IPFamily:  "ipv4",
					IP:        "10.0.0.2",
					Timestamp: time.Now().UTC().Add(1 * time.Hour).Unix(),
					LeaseTime: 10,
					Hostname:  "example",
				},
			},
			out: out{
				notifications: []*Notification{
					{
						Action:    "commit",
						MAC:       "00:00:00:00:00",
						IPFamily:  "ipv4",
						IP:        "10.0.0.1",
						Timestamp: 1,
						LeaseTime: 10,
						Hostname:  "example",
					},
				},
				remainingItems: 1,
			},
		}}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			r, w := net.Pipe()

			var res []*Notification

			done := make(chan struct{})

			ctx, cancel := context.WithCancel(context.Background())

			// Collect result from the Listener into res []*Notification
			// for further inspection
			listener := NewNotificationListener(r, func(
				_ context.Context, notifications []*Notification) error {
				res = append(res, notifications...)

				// Listen() has internal buffer that is flushed by timer. The data is then
				// passed to a handler function that is passed into NewNotificationListener.
				// Block to ensure that all the data that was send into net.Pipe was
				// returned back via handler function.
				if len(res) == len(tc.out.notifications) {
					done <- struct{}{}
				}

				return nil
			}, WithInterval(1*time.Millisecond))

			go listener.Listen(ctx)

			// Use net.Pipe writer to push data (as it would be read from the socket)
			for i := range tc.in {
				b, err := json.Marshal(tc.in[i])
				assert.NoError(t, err)

				_, err = w.Write(b)
				assert.NoError(t, err)
			}

			<-done
			cancel()
			assert.Len(t, res, len(tc.out.notifications))
			assert.Equal(t, tc.out.remainingItems, listener.queue.Len())
		})
	}
}
