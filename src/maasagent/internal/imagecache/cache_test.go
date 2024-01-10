package imagecache

import (
	"bytes"
	"io"
	"os"
	"path"
	"testing"

	"github.com/stretchr/testify/assert"
)

type mockValue struct {
	value    []byte
	position int
	readErr  error
	seekErr  error
}

func (m *mockValue) Read(b []byte) (int, error) {
	if m.readErr != nil {
		return 0, m.readErr
	}

	copy(b, m.value)

	m.position = len(m.value)

	return m.position, io.EOF
}

func (m *mockValue) Seek(offset int64, whence int) (int64, error) {
	if m.seekErr != nil {
		return 0, m.seekErr
	}

	orig := m.position

	m.position = 0

	return int64(orig), nil
}

type testCacheCfg struct {
	MaxSize  int64
	Existing map[string]struct {
		Value []byte
	}
}

type testFSCacheSetArgs struct {
	Key   string
	Value io.ReadSeeker
	Size  int64
	Reset bool
}

type testFSCacheSetResult struct {
	ExpectedCapCurr   int64
	ExpectedCapMax    int64
	ExpectedIndexSize int
	ExpectedIndexMax  int
	ValueExists       bool
	ValuePosition     int
}

func setupCacheDir(cacheCfg testCacheCfg) (string, error) {
	cacheDir, err := os.MkdirTemp("/tmp", "cache-*")
	if err != nil {
		return "", err
	}

	for key, val := range cacheCfg.Existing {
		err = func(k string, v []byte) error {
			filepath := path.Join(cacheDir, k)

			var f *os.File

			f, err = os.OpenFile(filepath, os.O_CREATE|os.O_WRONLY, 0600)
			if err != nil {
				return err
			}

			defer f.Close()

			_, err = f.Write(v)
			if err != nil {
				return err
			}

			return nil
		}(key, val.Value)

		if err != nil {
			return "", err
		}
	}

	return cacheDir, nil
}

func TestFSCacheSet(t *testing.T) {
	table := map[string]struct {
		CacheCfg testCacheCfg
		In       testFSCacheSetArgs
		Out      testFSCacheSetResult
	}{
		"adds_file_with_capacity_no_index_resize_no_reset": {
			CacheCfg: testCacheCfg{
				MaxSize: 32,
			},
			In: testFSCacheSetArgs{
				Key: "testfile",
				Value: &mockValue{
					value: make([]byte, 10),
				},
				Size: 10,
			},
			Out: testFSCacheSetResult{
				ExpectedCapCurr:   10,
				ExpectedCapMax:    32,
				ExpectedIndexSize: 1,
				ExpectedIndexMax:  16,
				ValueExists:       true,
				ValuePosition:     10,
			},
		},
		"adds_file_with_capacity_index_resize_no_reset": {
			CacheCfg: testCacheCfg{
				MaxSize: 32,
				Existing: map[string]struct{ Value []byte }{
					"0":  {Value: []byte{0}},
					"1":  {Value: []byte{0}},
					"2":  {Value: []byte{0}},
					"3":  {Value: []byte{0}},
					"4":  {Value: []byte{0}},
					"5":  {Value: []byte{0}},
					"6":  {Value: []byte{0}},
					"7":  {Value: []byte{0}},
					"8":  {Value: []byte{0}},
					"9":  {Value: []byte{0}},
					"10": {Value: []byte{0}},
					"11": {Value: []byte{0}},
					"12": {Value: []byte{0}},
					"13": {Value: []byte{0}},
					"14": {Value: []byte{0}},
					"15": {Value: []byte{0}},
				},
			},
			In: testFSCacheSetArgs{
				Key: "testfile2",
				Value: &mockValue{
					value: make([]byte, 1),
				},
				Size: 1,
			},
			Out: testFSCacheSetResult{
				ExpectedCapCurr:   17,
				ExpectedCapMax:    32,
				ExpectedIndexSize: 17,
				ExpectedIndexMax:  32,
				ValueExists:       true,
				ValuePosition:     1,
			},
		},
		"adds_file_with_capacity_no_index_resize_reset": {
			CacheCfg: testCacheCfg{
				MaxSize: 32,
			},
			In: testFSCacheSetArgs{
				Key: "testfile",
				Value: &mockValue{
					value: make([]byte, 10),
				},
				Size:  10,
				Reset: true,
			},
			Out: testFSCacheSetResult{
				ExpectedCapCurr:   10,
				ExpectedCapMax:    32,
				ExpectedIndexSize: 1,
				ExpectedIndexMax:  16,
				ValueExists:       true,
			},
		},
		"adds_file_greater_than_capacity": {
			CacheCfg: testCacheCfg{
				MaxSize: 16,
			},
			In: testFSCacheSetArgs{
				Key: "testfile3",
				Value: &mockValue{
					value: make([]byte, 18),
				},
				Size:  18,
				Reset: true,
			},
			Out: testFSCacheSetResult{
				ExpectedCapCurr:   18,
				ExpectedCapMax:    18,
				ExpectedIndexSize: 1,
				ExpectedIndexMax:  16,
				ValueExists:       true,
			},
		},
		"adds_file_over_capacity": {
			CacheCfg: testCacheCfg{
				MaxSize: 16,
				Existing: map[string]struct{ Value []byte }{
					"0":  {Value: []byte{0}},
					"1":  {Value: []byte{0}},
					"2":  {Value: []byte{0}},
					"3":  {Value: []byte{0}},
					"4":  {Value: []byte{0}},
					"5":  {Value: []byte{0}},
					"6":  {Value: []byte{0}},
					"7":  {Value: []byte{0}},
					"8":  {Value: []byte{0}},
					"9":  {Value: []byte{0}},
					"10": {Value: []byte{0}},
					"11": {Value: []byte{0}},
					"12": {Value: []byte{0}},
					"13": {Value: []byte{0}},
					"14": {Value: []byte{0}},
					"15": {Value: []byte{0}},
				},
			},
			In: testFSCacheSetArgs{
				Key: "testfile4",
				Value: &mockValue{
					value: make([]byte, 1),
				},
				Size: 1,
			},
			Out: testFSCacheSetResult{
				ExpectedCapCurr:   16,
				ExpectedCapMax:    16,
				ExpectedIndexSize: 16,
				ExpectedIndexMax:  16,
				ValueExists:       true,
				ValuePosition:     1,
			},
		},
	}

	for tname, tcase := range table {
		t.Run(tname, func(tt *testing.T) {
			cacheDir, err := setupCacheDir(tcase.CacheCfg)
			if err != nil {
				tt.Fatal(err)
			}

			cache, err := NewFSCache(tcase.CacheCfg.MaxSize, cacheDir)
			if err != nil {
				tt.Fatal(err)
			}

			_, err = cache.Set(tcase.In.Key, tcase.In.Value, tcase.In.Size, tcase.In.Reset)
			if err != nil {
				tt.Fatal(err)
			}

			assert.Equal(tt, tcase.Out.ExpectedCapCurr, cache.capCurr)
			assert.Equal(tt, tcase.Out.ExpectedCapMax, cache.capMax)
			assert.Equal(tt, tcase.Out.ExpectedIndexSize, cache.indexSizeCurr)
			assert.Equal(tt, tcase.Out.ExpectedIndexMax, cache.indexSizeMax)
			assert.Equal(tt, tcase.Out.ValuePosition, tcase.In.Value.(*mockValue).position)

			_, ok, err := cache.Get(tcase.In.Key)

			assert.Equal(tt, tcase.Out.ValueExists, ok)

			if err != nil {
				if os.IsNotExist(err) && !ok {
					return
				}
				tt.Fatal(err)
			}
		})
	}
}

func TestFSCacheGet(t *testing.T) {
	table := map[string]struct {
		CacheCfg testCacheCfg
		In       string
		Out      []byte
		Err      error
	}{
		"basic_get": {
			CacheCfg: testCacheCfg{
				MaxSize: 1,
				Existing: map[string]struct {
					Value []byte
				}{
					"testfile": {Value: []byte{0}},
				},
			},
			In:  "testfile",
			Out: []byte{0},
		},
		"not_found": {
			CacheCfg: testCacheCfg{
				MaxSize: 1,
			},
			In:  "testfile",
			Out: nil,
		},
	}

	for tname, tcase := range table {
		t.Run(tname, func(tt *testing.T) {
			cacheDir, err := setupCacheDir(tcase.CacheCfg)
			if err != nil {
				tt.Fatal(err)
			}

			cache, err := NewFSCache(tcase.CacheCfg.MaxSize, cacheDir)
			if err != nil {
				tt.Fatal(err)
			}

			result, ok, err := cache.Get(tcase.In)
			if err != nil {
				if tcase.Err != nil {
					assert.ErrorAs(tt, tcase.Err, err)
				} else {
					tt.Fatal(err)
				}
			}

			if !ok {
				if tcase.Out != nil {
					tt.Fatal("no result found")
				}

				return
			}

			defer result.Close()

			buf := make([]byte, len(tcase.Out))
			_, err = result.Read(buf)
			if err != nil {
				tt.Fatal(err)
			}

			assert.Equal(tt, tcase.Out, buf)
		})
	}
}

func TestFSCacheEvict(t *testing.T) {
	table := map[string]struct {
		CacheCfg        testCacheCfg
		In              []map[string][]byte // order matters
		ManipulateCache func(Cache) error
		Out             map[string][]byte // order does not matter
		Err             error
	}{
		"basic_in_order_eviction": {
			In: []map[string][]byte{
				{
					"file1": []byte("file1"),
				},
				{
					"file2": []byte("file2"),
				},
			},
			Out: map[string][]byte{
				"file2": []byte("file2"),
			},
		},
		"no_indexes": {
			Err: ErrNoIndex,
		},
		"keeps_most_recently_accessed": {
			In: []map[string][]byte{
				{
					"file1": []byte("file1"),
				},
				{
					"file2": []byte("file2"),
				},
			},
			ManipulateCache: func(cache Cache) error {
				f, _, err := cache.Get("file1")
				if err != nil {
					return err
				}

				return f.Close()
			},
			Out: map[string][]byte{
				"file1": []byte("file1"),
			},
		},
	}

	for tname, tcase := range table {
		t.Run(tname, func(tt *testing.T) {
			cacheDir, err := setupCacheDir(tcase.CacheCfg)
			if err != nil {
				tt.Fatal(err)
			}

			cache, err := NewFSCache(tcase.CacheCfg.MaxSize, cacheDir)
			if err != nil {
				tt.Fatal(err)
			}

			for _, file := range tcase.In {
				for name, content := range file {
					var f io.ReadCloser

					f, err = cache.Set(name, bytes.NewBuffer(content), int64(len(content)), false)
					if err != nil {
						tt.Fatal(err)
					}

					err = f.Close()
					if err != nil {
						tt.Fatal(err)
					}
				}
			}

			if tcase.ManipulateCache != nil {
				err = tcase.ManipulateCache(cache)
				if err != nil {
					tt.Fatal(err)
				}
			}

			err = cache.Evict()
			if tcase.Err != nil {
				assert.ErrorIs(tt, tcase.Err, err)
			} else if err != nil {
				tt.Fatal(err)
			}

			for name, content := range tcase.Out {
				f, ok, err := cache.Get(name)
				if err != nil {
					tt.Fatal(err)
				}

				assert.True(tt, ok)

				buf := make([]byte, len(content))

				_, err = f.Read(buf)
				if err != nil {
					tt.Fatal(err)
				}

				assert.Equal(tt, buf, content)
			}
		})
	}
}

func TestFSCacheEvictAll(t *testing.T) {
	table := map[string]struct {
		CacheCfg testCacheCfg
		Err      error
	}{
		"basic_eviction": {
			CacheCfg: testCacheCfg{
				Existing: map[string]struct{ Value []byte }{
					"file1": {
						Value: []byte("file1"),
					},
					"file2": {
						Value: []byte("file2"),
					},
				},
			},
		},
	}

	for tname, tcase := range table {
		t.Run(tname, func(tt *testing.T) {
			cacheDir, err := setupCacheDir(tcase.CacheCfg)
			if err != nil {
				tt.Fatal(err)
			}

			cache, err := NewFSCache(tcase.CacheCfg.MaxSize, cacheDir)
			if err != nil {
				tt.Fatal(err)
			}

			err = cache.EvictAll()
			if tcase.Err != nil {
				assert.ErrorIs(tt, err, tcase.Err)
			} else if err != nil {
				tt.Fatal(err)
			}

			for key := range tcase.CacheCfg.Existing {
				f, ok, err := cache.Get(key)
				if err != nil {
					tt.Fatal(err)
				}

				if ok {
					err = f.Close()
					if err != nil {
						tt.Error(err)
					}
				}

				assert.False(tt, ok)
			}
		})
	}
}
