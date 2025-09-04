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

package syncpool

import (
	"sync"
)

// Pool is a tiny generic wrapper over sync.Pool for better type-safety.
// Instead of dealing with type assertions, simply Get and Put values of type T
type Pool[T any] struct {
	p sync.Pool
}

// New returns a safe wrapper around sync.Pool
func New[T any](newFn func() T) *Pool[T] {
	return &Pool[T]{
		p: sync.Pool{
			New: func() any {
				return newFn()
			},
		},
	}
}

// Get returns an item of type T
func (p *Pool[T]) Get() T {
	return p.p.Get().(T) //nolint:errcheck // this should never error
}

// Put adds an item of type T to the pool
func (p *Pool[T]) Put(item T) {
	p.p.Put(item)
}
