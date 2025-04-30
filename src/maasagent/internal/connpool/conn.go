// Copyright (c) 2025 Canonical Ltd
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

// The MIT License (MIT)
//
// Copyright (c) 2013 Fatih Arslan
//
// Permission is hereby granted, free of charge, to any person obtaining a copy of
// this software and associated documentation files (the "Software"), to deal in
// the Software without restriction, including without limitation the rights to
// use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
// the Software, and to permit persons to whom the Software is furnished to do so,
// subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in all
// copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
// FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
// COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
// IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
// CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

package connpool

import (
	"net"
	"sync"
)

// Conn is a wrapper around net.Conn to modify the behavior of
// net.Conn's Close() method.
type Conn struct {
	net.Conn
	c        *channelPool
	mu       sync.Mutex
	unusable bool
}

// Close puts the given connection back into the pool instead of closing it.
func (p *Conn) Close() error {
	p.mu.Lock()
	defer p.mu.Unlock()

	if p.unusable {
		if p.Conn != nil {
			return p.Conn.Close()
		}

		return nil
	}

	return p.c.put(p.Conn)
}

// MarkUnusable marks the connection not usable anymore, to let the pool close it instead of returning it to pool.
func (p *Conn) MarkUnusable() {
	p.mu.Lock()
	defer p.mu.Unlock()
	p.unusable = true
}
