package imagecache

import (
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"path"
	"sync"

	lru "github.com/hashicorp/golang-lru/v2"
)

const (
	// ImageCacheDir is the default location for the FSCache's directory
	ImageCacheDir = "/var/cache/maas/boot-resources"
	// DefaultCacheSize is the default capacity for resources in the cache
	DefaultCacheSize = 4096 * 4096 * 4096 * 4096
	// DefaultIndexSize is the default number of indexes in the LRU, this number will
	// always grow unless indexes were erroneously added, but never shrink under normal use.
	DefaultIndexSize = 16
)

var (
	// ErrIndexSizeExceeded is an error for when the number of indexes created is greater than the configured size
	ErrIndexSizeExceeded = errors.New("number of indexes exceeds max size")
	// ErrUnseekableValue is an error for when the cache is requested to reset the file descriptor's position and
	// the given resource is not seek-able
	ErrUnseekableValue = errors.New("unable to reset value because it is not seekable")
	// ErrNoIndex is returned when an Evict is attempted without any indexes
	ErrNoIndex = errors.New("no indexes within cache")
)

// Cache is an interface defining behaviour for caching resources
type Cache interface {
	Set(string, io.Reader, int64, bool) (io.ReadCloser, error)
	Get(string) (io.ReadCloser, bool, error)
	Evict() error
	EvictAll() error
}

// FSCache implements a file system backed implementation
// of Cache
type FSCache struct {
	index         *lru.Cache[string, string]
	cacheDir      string
	indexSizeMax  int
	indexSizeCurr int
	origCapMax    int64
	capMax        int64
	capCurr       int64
	sync.RWMutex
}

// NewFSCache instantiates a new FSCache.
// If the configured directory does not exist, it will be created, otherwise,
// indexes for existing files will be created.
func NewFSCache(capMax int64, cacheDir string) (*FSCache, error) {
	if capMax <= 0 {
		capMax = DefaultCacheSize
	}

	if cacheDir == "" {
		if os.Getenv("SNAP") != "" {
			cacheDir = path.Join(os.Getenv("SNAP_DATA"), ImageCacheDir)
		} else {
			cacheDir = ImageCacheDir
		}
	}

	index, err := lru.New[string, string](DefaultIndexSize)
	if err != nil {
		return nil, err
	}

	cache := &FSCache{
		origCapMax:   capMax,
		capMax:       capMax,
		indexSizeMax: DefaultIndexSize,
		index:        index,
		cacheDir:     cacheDir,
	}

	_, err = os.Stat(cacheDir)
	if err != nil {
		if os.IsNotExist(err) {
			err = os.MkdirAll(cacheDir, 0750)
			if err != nil {
				return nil, err
			}
		} else {
			return nil, err
		}
	} else {
		err = cache.IndexCurrentCache()
		if err != nil {
			return nil, err
		}
	}

	return cache, nil
}

func (c *FSCache) growIndexIfNeeded() bool {
	if c.indexSizeCurr+1 > c.indexSizeMax {
		c.indexSizeMax += DefaultIndexSize
		c.index.Resize(c.indexSizeMax)

		return true
	}

	return false
}

func (c *FSCache) set(key string, value io.Reader, valueSize int64, resetValueBuffer bool) (io.ReadCloser, error) {
	filePath := path.Join(c.cacheDir, key)

	if c.capCurr+valueSize > c.capMax {
		if valueSize > c.capMax {
			c.capMax = valueSize

			err := c.evictAll()
			if err != nil {
				return nil, fmt.Errorf("failed to clear cache: %w", err)
			}

			c.capCurr = 0
		} else {
			for c.capCurr+valueSize > c.capMax {
				err := c.evict()
				if err != nil {
					return nil, fmt.Errorf("failed to evict oldest value: %w", err)
				}
			}
		}
	}

	//nolint:gosec // gosec wants string literal file arguments only
	f, err := os.OpenFile(filePath, os.O_CREATE|os.O_EXCL|os.O_RDWR, 0600)
	if err != nil {
		return nil, fmt.Errorf("failed opening file %q: %w", filePath, err)
	}

	c.growIndexIfNeeded()

	defer func() {
		if err != nil {
			origErr := err

			err = f.Close()
			if err != nil {
				return
			}

			err = os.Remove(filePath)
			if err != nil {
				return
			} else {
				err = origErr
			}
		}
	}()

	_, err = io.Copy(f, value)
	if err != nil {
		return nil, fmt.Errorf("failed to write value to %q: %w", filePath, err)
	}

	err = f.Sync()
	if err != nil {
		return nil, err
	}

	c.capCurr += valueSize

	if resetValueBuffer {
		seekVal, ok := value.(io.ReadSeeker)
		if !ok {
			return nil, ErrUnseekableValue
		}

		_, err = seekVal.Seek(0, io.SeekStart)
		if err != nil {
			return nil, fmt.Errorf("failed to reset value: %w", err)
		}
	}

	evicted := c.index.Add(key, filePath)

	c.indexSizeCurr++

	if evicted {
		return nil, ErrIndexSizeExceeded
	}

	_, err = f.Seek(0, io.SeekStart)
	if err != nil {
		return nil, fmt.Errorf("failed to reset cache file %q: %w", filePath, err)
	}

	return f, nil
}

// Set sets a value into the cache, writing it to disk and creating an index, Set will evict an older file if capacity
// is exceeded
func (c *FSCache) Set(key string, value io.Reader, valueSize int64, resetValueBuffer bool) (io.ReadCloser, error) {
	c.Lock()
	defer c.Unlock()

	return c.set(key, value, valueSize, resetValueBuffer)
}

func (c *FSCache) get(key string) (io.ReadCloser, bool, error) {
	idx, ok := c.index.Get(key)
	if !ok {
		return nil, ok, nil
	}

	//nolint:gosec // gosec wants string literal file arguments
	f, err := os.OpenFile(idx, os.O_RDONLY, 0600)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, false, err
		}

		return nil, true, err
	}

	return f, true, nil
}

// Get fetches a value from the cache based on the given key, if it is not present,
// the second value returned will be false
func (c *FSCache) Get(key string) (io.ReadCloser, bool, error) {
	c.RLock()
	defer c.RUnlock()

	return c.get(key)
}

func (c *FSCache) evict() error {
	key, idx, ok := c.index.GetOldest()
	if !ok {
		return ErrNoIndex
	}

	stat, err := os.Stat(idx)
	if err != nil {
		return err
	}

	err = os.Remove(idx)
	if err != nil {
		return err
	}

	c.capCurr -= stat.Size()

	if c.capCurr <= c.capMax && c.origCapMax < c.capMax {
		if c.capCurr > c.origCapMax {
			c.capMax = c.capCurr
		} else {
			c.capMax = c.origCapMax
		}
	}

	c.index.Remove(key)

	c.indexSizeCurr--

	return nil
}

// Evict removes the oldest file from the cache
func (c *FSCache) Evict() error {
	c.Lock()
	defer c.Unlock()

	return c.evict()
}

func (c *FSCache) evictAll() error {
	dir := os.DirFS(c.cacheDir)

	return fs.WalkDir(dir, ".", func(fpath string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}

		if fpath == "." {
			return nil
		}

		stat, err := entry.Info()
		if err != nil {
			return err
		}

		fpath = path.Join(c.cacheDir, stat.Name())

		err = os.Remove(fpath)
		if err != nil {
			return err
		}

		c.index.Remove(entry.Name())

		c.indexSizeCurr--

		c.capCurr -= stat.Size()

		if c.origCapMax < c.capMax {
			c.capMax = c.origCapMax
		}

		return nil
	})
}

// EvictAll removes all files from the cache
func (c *FSCache) EvictAll() error {
	c.Lock()
	defer c.Unlock()

	return c.evictAll()
}

func (c *FSCache) indexCurrentCache() error {
	dir := os.DirFS(c.cacheDir)

	return fs.WalkDir(dir, ".", func(fpath string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}

		if fpath == "." {
			return nil
		}

		fpath = path.Join(c.cacheDir, fpath)

		c.growIndexIfNeeded()

		stat, err := entry.Info()
		if err != nil {
			return err
		}

		c.capCurr += stat.Size()

		if c.capCurr > c.capMax {
			c.capMax = c.capCurr
		}

		c.index.Add(entry.Name(), fpath)
		c.indexSizeCurr++

		return nil
	})
}

// IndexCurrentCache walks the configured cache directory, creating indexes for
// files currently present
func (c *FSCache) IndexCurrentCache() error {
	c.Lock()
	defer c.Unlock()

	return c.indexCurrentCache()
}
