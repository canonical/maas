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
	"net"
	"sync"
	"time"

	"github.com/rs/zerolog/log"
)

type Notification struct {
	Action    string `json:"action"`
	IPFamily  string `json:"ip_family"`
	Hostname  string `json:"hostname"`
	MAC       string `json:"mac"`
	IP        string `json:"ip"`
	Timestamp int64  `json:"timestamp"`
	LeaseTime int64  `json:"lease_time"`
}

type NotificationListener struct {
	conn     net.Conn
	queue    *NotificationQueue
	buf      chan *Notification
	pool     *sync.Pool
	fn       func(context.Context, []*Notification) error
	interval time.Duration
}

type NotificationListenerOption func(*NotificationListener)

func NewNotificationListener(conn net.Conn, fn func(context.Context, []*Notification) error,
	options ...NotificationListenerOption) *NotificationListener {
	pool := &sync.Pool{
		New: func() interface{} {
			s := make([]*Notification, 0, 1024)
			return &s
		},
	}

	l := &NotificationListener{
		pool:  pool,
		conn:  conn,
		buf:   make(chan *Notification, 1024),
		queue: NewNotificationQueue(),
		fn:    fn,
	}

	for _, opt := range options {
		opt(l)
	}

	return l
}

// WithInterval allows setting custom interval for the buffer-flush timer.
// (default: 5*time.Second)
func WithInterval(d time.Duration) NotificationListenerOption {
	return func(l *NotificationListener) { l.interval = d }
}

func (l *NotificationListener) Listen(ctx context.Context) {
	go l.read(ctx)

	interval := 5 * time.Second
	if l.interval > 0 {
		interval = l.interval
	}

	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case notification := <-l.buf:
			heap.Push(l.queue, notification)
		case <-ticker.C:
			batchPtr, ok := l.pool.Get().(*[]*Notification)
			if !ok {
				panic("wrong type. should be *[]*Notification")
			}

			batch := *batchPtr
			batch = batch[:0]

			now := time.Now().UTC().Unix()

			for l.queue.Len() > 0 {
				notification, ok := heap.Pop(l.queue).(*Notification)
				if !ok {
					panic("wrong type. should be *Notification")
				}

				if now-notification.Timestamp > 1 {
					batch = append(batch, notification)

					continue
				}

				l.queue.Push(notification)

				break
			}

			if len(batch) == 0 {
				l.pool.Put(&batch)
				continue
			}

			copied := make([]*Notification, len(batch))
			copy(copied, batch)
			l.pool.Put(&batch)

			err := l.fn(ctx, copied)
			if err != nil { // failed to send, push leases back
				for _, n := range copied {
					heap.Push(l.queue, n)
				}
			}
		}
	}
}

func (l *NotificationListener) read(ctx context.Context) {
	decoder := json.NewDecoder(l.conn)

	for {
		select {
		case <-ctx.Done():
			if err := l.conn.Close(); err != nil {
				log.Warn().Err(err).Send()
			}

			return
		default:
			var notification Notification

			err := decoder.Decode(&notification)
			if err != nil {
				log.Warn().Err(err).Msg("Malformed DHCP notification")
				// reset the decoder
				decoder = json.NewDecoder(l.conn)

				continue
			}

			l.buf <- &notification
		}
	}
}
