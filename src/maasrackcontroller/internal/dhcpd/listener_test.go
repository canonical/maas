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
	"net"
	"sync"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

// Lease is redefined here to avoid a circular import
type Lease struct {
	ID         int
	IP         net.IP
	MACAddress net.HardwareAddr
	DUID       string
	CreatedAt  int
	UpdatedAt  int
	Lifetime   int
	State      int
	RangeID    int
	NeedsSync  bool
}

// Expiration is redefined here to avoid a circular import
type Expiration struct {
	ID         int
	IP         net.IP
	MACAddress net.HardwareAddr
	DUID       string
	CreatedAt  int
}

func TestSync(t *testing.T) {
	testcases := map[string]struct {
		in struct {
			notifications []*Notification
			returnError   bool
		}
		out struct {
			sentCount      int
			queueRemaining int
			shouldError    bool
		}
	}{
		"no duplicates - all old notifications sent": {
			in: struct {
				notifications []*Notification
				returnError   bool
			}{
				notifications: []*Notification{
					{
						Action:    "commit",
						IP:        "10.0.0.1",
						MAC:       "00:11:22:33:44:55",
						IPFamily:  "ipv4",
						Timestamp: time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix(),
						LeaseTime: 300,
					},
					{
						Action:    "commit",
						IP:        "10.0.0.2",
						MAC:       "00:11:22:33:44:66",
						IPFamily:  "ipv4",
						Timestamp: time.Date(2025, 10, 22, 0, 0, 5, 0, time.UTC).Unix(),
						LeaseTime: 300,
					},
					{
						Action:    "expiry",
						IP:        "10.0.0.3",
						MAC:       "00:11:22:33:44:77",
						IPFamily:  "ipv4",
						Timestamp: time.Date(2025, 10, 22, 0, 0, 10, 0, time.UTC).Unix(),
						LeaseTime: 0,
					},
				},
				returnError: false,
			},
			out: struct {
				sentCount      int
				queueRemaining int
				shouldError    bool
			}{
				sentCount:      3,
				queueRemaining: 0,
				shouldError:    false,
			},
		},
		"respects timestamp - too new notifications remain in queue": {
			in: struct {
				notifications []*Notification
				returnError   bool
			}{
				notifications: []*Notification{
					{
						Action:    "commit",
						IP:        "10.0.0.1",
						MAC:       "00:11:22:33:44:55",
						IPFamily:  "ipv4",
						Timestamp: time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix(),
						LeaseTime: 300,
					},
					{
						Action:    "commit",
						IP:        "10.0.0.2",
						MAC:       "00:11:22:33:44:66",
						IPFamily:  "ipv4",
						Timestamp: time.Date(3025, 10, 22, 0, 0, 0, 0, time.UTC).Unix(),
						LeaseTime: 300,
					},
				},
				returnError: false,
			},
			out: struct {
				sentCount      int
				queueRemaining int
				shouldError    bool
			}{
				sentCount:      1,
				queueRemaining: 1,
				shouldError:    false,
			},
		},
		"error retry - failed send pushes notifications back": {
			in: struct {
				notifications []*Notification
				returnError   bool
			}{
				notifications: []*Notification{
					{
						Action:    "commit",
						IP:        "10.0.0.1",
						MAC:       "00:11:22:33:44:55",
						IPFamily:  "ipv4",
						Timestamp: time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix(),
						LeaseTime: 300,
					},
					{
						Action:    "commit",
						IP:        "10.0.0.2",
						MAC:       "00:11:22:33:44:66",
						IPFamily:  "ipv4",
						Timestamp: time.Date(2025, 10, 22, 0, 0, 5, 0, time.UTC).Unix(),
						LeaseTime: 300,
					},
				},
				returnError: true,
			},
			out: struct {
				sentCount      int
				queueRemaining int
				shouldError    bool
			}{
				sentCount:      2,
				queueRemaining: 2,
				shouldError:    true,
			},
		},
		"success removes from queue": {
			in: struct {
				notifications []*Notification
				returnError   bool
			}{
				notifications: []*Notification{
					{
						Action:    "commit",
						IP:        "10.0.0.1",
						MAC:       "00:11:22:33:44:55",
						IPFamily:  "ipv4",
						Timestamp: time.Date(2025, 10, 22, 0, 0, 0, 0, time.UTC).Unix(),
						LeaseTime: 300,
					},
					{
						Action:    "commit",
						IP:        "10.0.0.2",
						MAC:       "00:11:22:33:44:66",
						IPFamily:  "ipv4",
						Timestamp: time.Date(2025, 10, 22, 0, 0, 5, 0, time.UTC).Unix(),
						LeaseTime: 300,
					},
				},
				returnError: false,
			},
			out: struct {
				sentCount      int
				queueRemaining int
				shouldError    bool
			}{
				sentCount:      2,
				queueRemaining: 0,
				shouldError:    false,
			},
		},
	}

	for tname, tc := range testcases {
		t.Run(tname, func(t *testing.T) {
			ctx := context.Background()

			var sentBatch []*Notification

			pool := &sync.Pool{
				New: func() any {
					s := make([]*Notification, 0, 1024)
					return &s
				},
			}

			nl := &NotificationListener{
				pool:  pool,
				queue: NewNotificationQueue(),
				fn: func(ctx context.Context, notifications []*Notification) error {
					sentBatch = make([]*Notification, len(notifications))
					copy(sentBatch, notifications)

					if tc.in.returnError {
						return assert.AnError
					}

					return nil
				},
			}

			for _, n := range tc.in.notifications {
				heap.Push(nl.queue, n)
			}

			err := nl.sync(ctx)

			if tc.out.shouldError {
				require.Error(t, err)
			} else {
				require.NoError(t, err)
			}

			assert.Len(t, sentBatch, tc.out.sentCount, "Should send expected number of notifications")
			assert.Equal(t, tc.out.queueRemaining, nl.queue.Len(), "Queue should have expected remaining notifications")

			// Verify no duplicates in sent batch
			if len(sentBatch) > 0 {
				foundIPs := make(map[string]int)
				for _, n := range sentBatch {
					foundIPs[n.IP]++
				}

				for ip, count := range foundIPs {
					assert.Equal(t, 1, count, "IP %s should appear exactly once in batch", ip)
				}
			}

			// Verify no duplicates in remaining queue
			if nl.queue.Len() > 0 {
				foundIPs := make(map[string]int)

				for nl.queue.Len() > 0 {
					n := heap.Pop(nl.queue).(*Notification)
					foundIPs[n.IP]++
				}

				for ip, count := range foundIPs {
					assert.Equal(t, 1, count, "IP %s should appear exactly once in queue", ip)
				}
			}
		})
	}
}
