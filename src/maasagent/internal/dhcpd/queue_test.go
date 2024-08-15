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
	"net"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestNotificationQueue(t *testing.T) {
	testcases := map[string]struct {
		in  []*Notification
		out []*Notification
	}{
		"receive notifications out of order": {
			in: []*Notification{
				{
					MAC: net.HardwareAddr{0x01, 0x01, 0x01, 0x01, 0x01, 0x01},
					IP:  net.ParseIP("10.0.0.1"),
					// Reporting leases in the order they were created is important,
					// so here we test receiving them out of order
					Timestamp: 3,
				},
				{
					MAC:       net.HardwareAddr{0x01, 0x01, 0x01, 0x01, 0x01, 0x02},
					IP:        net.ParseIP("10.0.0.2"),
					Timestamp: 1,
				},
				{
					MAC:       net.HardwareAddr{0x01, 0x01, 0x01, 0x01, 0x01, 0x03},
					IP:        net.ParseIP("10.0.0.3"),
					Timestamp: 4,
				},
				{
					MAC:       net.HardwareAddr{0x01, 0x01, 0x01, 0x01, 0x01, 0x04},
					IP:        net.ParseIP("10.0.0.4"),
					Timestamp: 0,
				},
			},
			out: []*Notification{
				{
					MAC:       net.HardwareAddr{0x01, 0x01, 0x01, 0x01, 0x01, 0x04},
					IP:        net.ParseIP("10.0.0.4"),
					Timestamp: 0,
				},
				{
					MAC:       net.HardwareAddr{0x01, 0x01, 0x01, 0x01, 0x01, 0x02},
					IP:        net.ParseIP("10.0.0.2"),
					Timestamp: 1,
				},
				{
					MAC:       net.HardwareAddr{0x01, 0x01, 0x01, 0x01, 0x01, 0x01},
					IP:        net.ParseIP("10.0.0.1"),
					Timestamp: 3,
				},
				{
					MAC:       net.HardwareAddr{0x01, 0x01, 0x01, 0x01, 0x01, 0x03},
					IP:        net.ParseIP("10.0.0.3"),
					Timestamp: 4,
				},
			},
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			queue := NewNotificationQueue()

			for _, x := range tc.in {
				heap.Push(queue, x)
			}

			for _, p := range tc.out {
				res := heap.Pop(queue)

				notification, _ := res.(*Notification)

				assert.Equal(t, notification, p)
			}
		})
	}
}
