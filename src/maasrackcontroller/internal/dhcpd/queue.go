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
)

// NotificationQueue is a Priority queue implementation taken from:
// https://pkg.go.dev/container/heap#example-package-PriorityQueue
type NotificationQueue []*Notification

// NewNotificationQueue returns a min-heap priority queue designed to manage
// DHCP notification events coming from ISC DHCP:
// - on commit
// - on expiry
// - on release
// This structure ensures that DHCP events, which may arrive in an
// unordered fashion, are processed in the correct chronological order.
func NewNotificationQueue() *NotificationQueue {
	var q NotificationQueue

	heap.Init(&q)

	return &q
}

func (q NotificationQueue) Len() int {
	return len(q)
}

func (q NotificationQueue) Less(i, j int) bool {
	return q[i].Timestamp < q[j].Timestamp
}

func (q NotificationQueue) Swap(i, j int) {
	q[i], q[j] = q[j], q[i]
}

func (q *NotificationQueue) Push(x any) {
	notification, ok := x.(*Notification)
	if !ok {
		panic("x sould be of type *Notification")
	}

	*q = append(*q, notification)
}

func (q *NotificationQueue) Pop() any {
	prev := *q
	n := len(prev)
	x := prev[n-1]
	prev[n-1] = nil
	*q = prev[0 : n-1]

	return x
}
