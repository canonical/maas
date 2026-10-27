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

package cache

import (
	"io"
	"sync"
)

type FakeFileCache struct {
	storage map[string]io.ReadSeekCloser
	mutex   sync.RWMutex
}

func NewFakeFileCache() *FakeFileCache {
	return &FakeFileCache{storage: make(map[string]io.ReadSeekCloser)}
}

func (c *FakeFileCache) Set(key string, value io.Reader, valueSize int64) error {
	c.mutex.Lock()
	defer c.mutex.Unlock()

	data, err := io.ReadAll(value)
	if err != nil {
		return err
	}

	buf := NewBuffer(data)
	c.storage[key] = &buf

	return nil
}

func (c *FakeFileCache) Get(key string) (io.ReadSeekCloser, error) {
	c.mutex.RLock()
	defer c.mutex.RUnlock()

	data, ok := c.storage[key]
	if !ok {
		return nil, ErrKeyDoesntExist
	}

	return data, nil
}
