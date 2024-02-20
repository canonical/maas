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
