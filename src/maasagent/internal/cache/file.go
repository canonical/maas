package cache

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
	size int64
	// required to track if the size of LRU cache (index) should be increased.
	// This is expected to happen because we limit our cache based on the
	// disk space size and not on the items size.
	indexSize int
	mutex     sync.Mutex
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
		// This is just a starting default number. It doesn't limit anything
		// because cache is limited by maxSize property.
		indexSize: 50,
		dir:       dir,
		maxSize:   maxSize,
		progress:  map[string]struct{}{},
	}

	for _, opt := range options {
		opt(cache)
	}

	index, err := lru.New[string, string](cache.indexSize)
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
func WithIndexSize(i int) FileCacheOption {
	return func(c *FileCache) {
		c.indexSize = i
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
	c.mutex.Lock()

	if _, ok := c.progress[key]; ok {
		c.mutex.Unlock()
		return ErrKeySetInProgress
	}

	defer func() {
		if !errors.Is(err, ErrKeySetInProgress) {
			c.mutex.Lock()
			delete(c.progress, key)
			c.mutex.Unlock()
		}
	}()

	c.progress[key] = struct{}{}
	c.mutex.Unlock()

	if valueSize < 0 {
		return ErrNegativeSize
	}

	c.mutex.Lock()

	_, ok := c.index.Get(key)
	c.mutex.Unlock()

	if ok {
		return ErrKeyExist
	}

	if valueSize > c.maxSize && c.size+valueSize > c.maxSize {
		return ErrCacheSizeExceeded
	}

	filePath := path.Join(c.dir, key)
	// Remove oldest files in order to fit new item into cache.
	for c.size+valueSize > c.maxSize {
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
		if err != nil {
			c.mutex.Lock()

			closeErr := f.Close()
			if closeErr != nil {
				err = errors.Join(err, closeErr)
			}

			removeErr := os.Remove(filePath)
			if removeErr != nil && !errors.Is(err, fs.ErrNotExist) {
				err = errors.Join(err, removeErr)
			}

			c.size -= valueSize

			c.mutex.Unlock()
		}
	}()

	n, err := io.Copy(f, value)
	if err != nil || n != valueSize {
		return fmt.Errorf("failed to write value: %w", err)
	}

	if err = f.Sync(); err != nil {
		return err
	}

	c.mutex.Lock()
	c.size += valueSize

	// Extend the size of LRU cache if we hit maxSize.
	// This is expected to happen because we limit our cache based on the
	// disk space size.

	if c.index.Len()+1 > c.indexSize {
		c.indexSize += c.indexSize
		c.index.Resize(c.indexSize)
	}

	// Return value is not checked, because index always grows.
	c.index.Add(key, filePath)
	c.mutex.Unlock()

	return nil
}

func (c *FileCache) get(key string) (io.ReadSeekCloser, error) {
	c.mutex.Lock()
	defer c.mutex.Unlock()

	v, ok := c.index.Get(key)
	if !ok {
		return nil, ErrKeyDoesntExist
	}

	//nolint:gosec // gosec wants string literal file arguments
	return os.OpenFile(v, os.O_RDONLY, 0600)
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

	c.size -= stat.Size()
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

		c.size += stat.Size()
		if c.size > c.maxSize {
			return ErrCacheSizeExceeded
		}

		c.index.Add(stat.Name(), fpath)

		return nil
	})
}
