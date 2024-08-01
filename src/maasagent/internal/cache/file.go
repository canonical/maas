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
	"context"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path"
	"sync"
	"sync/atomic"

	lru "github.com/hashicorp/golang-lru/v2"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
)

const (
	Kilobyte = 1024
	Megabyte = 1024 * Kilobyte
	Gigabyte = 1024 * Megabyte
)

var (
	ErrKeyExist             = errors.New("key already exist")
	ErrFileDoesntExist      = errors.New("file doesn't exist")
	ErrCacheSizeExceeded    = errors.New("cache size exceeded")
	ErrMissingCacheDir      = errors.New("missing cache directory")
	ErrPositiveMaxCacheSize = errors.New("cache size must be positive")
	ErrKeyDoesntExist       = errors.New("key doesn't exist")
	ErrKeySetInProgress     = errors.New("key set is in progress")
	ErrNegativeSize         = errors.New("value size is negative")
)

type fileCacheStats struct {
	hits   atomic.Int64
	misses atomic.Int64
	errors atomic.Int64
}

// FileCache implements a file system backed cache, which makes it possible
// to store values as files on disk. Total cache size is specified by the
// total size of the data, rather than the amount of items.
// FileCache maintains index of all the items in a in-memory LRU cache, that
// allows to free up space by evicting oldest items.
type FileCache struct {
	// index keeps information about added keys
	index    *lru.Cache[string, string]
	progress map[string]struct{}

	// directory used to store cached items
	dir string
	// max cache size
	maxSize int64
	// current cache size
	size atomic.Int64
	// required to track if the size of LRU cache (index) should be increased.
	// This is expected to happen because we limit our cache based on the
	// disk space size and not on the items size.
	indexSize atomic.Int64
	stats     fileCacheStats
	mutex     sync.RWMutex
}

// NewFileCache instantiates a new instance of FileCache.
// If the provided path does not exist, it will be created,
// otherwise existing files will be indexed and served from cache.
func NewFileCache(maxSize int64, dir string, options ...FileCacheOption) (*FileCache, error) {
	if maxSize <= 0 {
		return nil, ErrPositiveMaxCacheSize
	}

	if dir == "" {
		return nil, ErrMissingCacheDir
	}

	cache := &FileCache{
		dir:      dir,
		maxSize:  maxSize,
		progress: map[string]struct{}{},
		stats:    fileCacheStats{},
	}

	// This is just a starting default number. It doesn't limit anything
	// because cache is limited by maxSize property.
	cache.indexSize.Store(40)

	for _, opt := range options {
		opt(cache)
	}

	index, err := lru.New[string, string](int(cache.indexSize.Load()))
	if err != nil {
		return nil, err
	}

	cache.index = index

	if _, err := os.Stat(dir); err != nil {
		if errors.Is(err, fs.ErrNotExist) && os.Mkdir(dir, 0750) == nil {
			return cache, nil
		}

		return nil, err
	}

	// Because cache directory is not empty, we need to build index
	// of existing files.
	return cache, cache.reindex()
}

// FileCacheOption allows to set additional FileCache options
type FileCacheOption func(*FileCache)

// WithIndexSize allows to set maximum index size.
// Normally this is required only in tests.
func WithIndexSize(i int64) FileCacheOption {
	return func(c *FileCache) {
		c.indexSize.Store(i)
	}
}

func must[T any](v T, err error) T {
	if err != nil {
		panic(err)
	}

	return v
}

// WithMetricMeter allows to set OpenTelemetry metric.Meter
// to collect cache stats.
func WithMetricMeter(meter metric.Meter) FileCacheOption {
	return func(c *FileCache) {
		hits := attribute.String("type", "hits")
		misses := attribute.String("type", "misses")
		errors := attribute.String("type", "errors")

		must(meter.Int64ObservableCounter("cache.usage",
			metric.WithUnit("{count}"),
			metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
				o.Observe(c.stats.hits.Load(), metric.WithAttributes(hits))
				o.Observe(c.stats.misses.Load(), metric.WithAttributes(misses))
				o.Observe(c.stats.errors.Load(), metric.WithAttributes(errors))

				return nil
			})))

		must(meter.Int64ObservableGauge("cache.size",
			metric.WithUnit("byte"),
			metric.WithInt64Callback(func(_ context.Context, o metric.Int64Observer) error {
				o.Observe(c.size.Load(), metric.WithAttributes(attribute.String("type", "current")))
				o.Observe(c.maxSize, metric.WithAttributes(attribute.String("type", "max")))

				return nil
			})))
	}
}

func (c *FileCache) Set(key string, value io.Reader, valueSize int64) error {
	return c.set(key, value, valueSize)
}

// Get returns io.ReadSeekCloser that can be used to read contents from the disk.
func (c *FileCache) Get(key string) (io.ReadSeekCloser, error) {
	return c.get(key)
}

func (c *FileCache) set(key string, value io.Reader, valueSize int64) (err error) {
	// Because of the cleanup logic that happens in defer func() we have to use
	// named return variable here, so we can return error happened during cleanup.
	c.mutex.RLock()

	_, ok := c.progress[key]
	c.mutex.RUnlock()

	if ok {
		// There might be a situation when same key is being set by multiple clients.
		// We don't want to block parallel calls with a global lock, so we simply
		// return an error indicating an ongoing set operation for the same key,
		// so the client can retry the operation.
		return ErrKeySetInProgress
	}

	defer func() {
		c.mutex.Lock()
		delete(c.progress, key)
		c.mutex.Unlock()
	}()

	c.mutex.Lock()
	c.progress[key] = struct{}{}
	c.mutex.Unlock()

	if valueSize < 0 {
		return ErrNegativeSize
	}

	_, ok = c.index.Get(key)
	if ok {
		return ErrKeyExist
	}

	if valueSize > c.maxSize && c.size.Load()+valueSize > c.maxSize {
		return ErrCacheSizeExceeded
	}

	filePath := path.Join(c.dir, key)
	// Remove oldest files in order to fit new item into cache.
	for c.size.Load()+valueSize > c.maxSize {
		c.mutex.Lock()
		err = c.evict()
		c.mutex.Unlock()

		if err != nil {
			return fmt.Errorf("failed to evict oldest value: %w", err)
		}
	}

	var f *os.File
	//nolint:gosec // gosec wants string literal file arguments only
	f, err = os.OpenFile(filePath, os.O_CREATE|os.O_EXCL|os.O_RDWR, 0600)
	if err != nil {
		return fmt.Errorf("failed opening file: %w", err)
	}

	defer func() {
		origErr := err
		closeErr := f.Close()

		if closeErr != nil {
			err = errors.Join(err, closeErr)
		}

		if origErr != nil {
			removeErr := os.Remove(filePath)
			if removeErr != nil && !errors.Is(err, fs.ErrNotExist) {
				err = errors.Join(err, removeErr)
			}

			c.size.Add(-1 * valueSize)
		}
	}()

	c.size.Add(valueSize)

	n, err := io.Copy(f, value)
	if err != nil {
		return fmt.Errorf("failed to write value: %w", err)
	}

	if n != valueSize {
		return fmt.Errorf("failed to write value: %d of %d bytes copied", n, valueSize)
	}

	if err = f.Sync(); err != nil {
		return err
	}

	// Extend the size of LRU cache if we hit maxSize.
	// This is expected to happen because we limit our cache based on the
	// disk space size.
	if c.index.Len()+1 > int(c.indexSize.Load()) {
		c.indexSize.Add(c.indexSize.Load())
		c.index.Resize(int(c.indexSize.Load()))
	}

	// Return value is not checked, because index always grows.
	c.index.Add(key, filePath)

	return nil
}

func (c *FileCache) get(key string) (io.ReadSeekCloser, error) {
	c.stats.hits.Add(1)

	v, ok := c.index.Get(key)
	if !ok {
		c.stats.misses.Add(1)
		return nil, ErrKeyDoesntExist
	}

	//nolint:gosec // gosec wants string literal file arguments
	file, err := os.OpenFile(v, os.O_RDONLY, 0600)
	if err != nil {
		c.stats.errors.Add(1)
	}

	return file, err
}

// evict removes the oldest item from cache.
// Should be used only during add operation if new item doesn't fit.
func (c *FileCache) evict() error {
	key, idx, _ := c.index.GetOldest()

	stat, err := os.Stat(idx)
	if err != nil {
		return err
	}

	if err := os.Remove(idx); err != nil {
		return err
	}

	c.size.Add(-1 * stat.Size())
	c.index.Remove(key)

	return nil
}

// reindex walks the configured cache directory, creating
// index for files currently present in cache directory.
// If the size of existing files is bigger than cache maxSize,
// ErrCacheSizeExceeded is returned.
// Normally should be used only within NewFileCache function call
func (c *FileCache) reindex() error {
	dir := os.DirFS(c.dir)

	return fs.WalkDir(dir, ".", func(fpath string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}

		if fpath == "." {
			return nil
		}

		fpath = path.Join(c.dir, fpath)

		stat, err := entry.Info()
		if err != nil {
			return err
		}

		c.size.Add(stat.Size())

		if c.size.Load() > c.maxSize {
			return ErrCacheSizeExceeded
		}

		c.index.Add(stat.Name(), fpath)

		return nil
	})
}
