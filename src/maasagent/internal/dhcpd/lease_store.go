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

type LeaseHeap []Notification

func NewLeaseHeap() *LeaseHeap {
	var l LeaseHeap

	heap.Init(&l)

	return &l
}

func (l LeaseHeap) Len() int {
	return len(l)
}

func (l LeaseHeap) Less(i, j int) bool {
	return l[i].Timestamp < l[j].Timestamp
}

func (l LeaseHeap) Swap(i, j int) {
	l[i], l[j] = l[j], l[i]
}

func (l *LeaseHeap) Push(elm any) {
	notification, ok := elm.(Notification)
	if !ok {
		return
	}

	*l = append(*l, notification)
}

func (l *LeaseHeap) Pop() any {
	prev := *l
	n := len(prev)
	x := prev[n-1]
	*l = prev[0 : n-1]

	return x
}
