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
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"path"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/sdk/instrumentation"
	"go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/metric/metricdata"
	"go.opentelemetry.io/otel/sdk/metric/metricdata/metricdatatest"
)

func TestNewFileCache(t *testing.T) {
	type in struct {
		maxSize int64
		path    string
	}

	testcases := map[string]struct {
		in  in
		out *FileCache
		err error
	}{
		"zero max cache size": {
			in:  in{maxSize: 0, path: ""},
			out: nil,
			err: ErrPositiveMaxCacheSize,
		},
		"negative max cache size": {
			in:  in{maxSize: -1, path: ""},
			out: nil,
			err: ErrPositiveMaxCacheSize,
		},
		"no path provided": {
			in:  in{maxSize: 1, path: ""},
			out: nil,
			err: ErrMissingCacheDir,
		},
		"non existing directory": {
			in: in{maxSize: 1, path: func() string {
				p := fmt.Sprintf("%s-%d", t.Name(), time.Now().Unix())
				return path.Join(os.TempDir(), p)
			}()},
			out: nil,
			err: nil,
		},
		"existing empty directory": {
			in:  in{maxSize: 1, path: t.TempDir()},
			out: nil,
			err: nil,
		},
		"existing directory with files larger than cache size": {
			in: in{
				maxSize: 1,
				path: func() string {
					dir := t.TempDir()
					file, err := os.Create(path.Join(dir, "item"))
					if err != nil {
						t.Fatal(err)
					}
					defer file.Close()

					_, err = file.Write(make([]byte, 2))
					if err != nil {
						t.Fatal(err)
					}

					return dir
				}(),
			},
			out: nil,
			err: ErrCacheSizeExceeded,
		},
		"existing directory with files that fit cache size": {
			in: in{
				maxSize: 2,
				path: func() string {
					dir := t.TempDir()
					file, err := os.Create(path.Join(dir, "item"))
					if err != nil {
						t.Fatal(err)
					}
					defer file.Close()

					_, err = file.Write(make([]byte, 1))
					if err != nil {
						t.Fatal(err)
					}

					return dir
				}(),
			},
			out: nil,
			err: nil,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			_, err := NewFileCache(tc.in.maxSize, tc.in.path)
			assert.Equal(t, tc.err, err)
		})
	}
}

func TestFileCacheAdd(t *testing.T) {
	type in struct {
		cache *FileCache
		items []*strings.Reader
	}

	testcases := map[string]struct {
		in in
		// used to check internal state of the cache
		// should return true if state is valid
		out func(cache *FileCache) bool
		err error
	}{
		"item that does not fit": {
			in: in{
				cache: func() *FileCache {
					cache, err := NewFileCache(1, t.TempDir())
					if err != nil {
						t.Fatal(err)
					}
					return cache
				}(),
				items: []*strings.Reader{
					strings.NewReader("value"),
				},
			},
			out: nil,
			err: ErrCacheSizeExceeded,
		},
		"item that fits": {
			in: in{
				cache: func() *FileCache {
					cache, err := NewFileCache(1, t.TempDir())
					if err != nil {
						t.Fatal(err)
					}
					return cache
				}(),
				items: []*strings.Reader{
					strings.NewReader("x"),
				},
			},
			out: nil,
			err: nil,
		},
		"index size is extended": {
			in: in{
				cache: func() *FileCache {
					cache, err := NewFileCache(2, t.TempDir(), WithIndexSize(1))
					if err != nil {
						t.Fatal(err)
					}
					return cache
				}(),
				items: []*strings.Reader{
					strings.NewReader("x"),
					strings.NewReader("x"),
				},
			},
			out: func(cache *FileCache) bool {
				return cache.indexSize.Load() == 2 && cache.index.Len() == 2
			},
			err: nil,
		},
		"when new item does not fit old item is evicted": {
			in: in{
				cache: func() *FileCache {
					cache, err := NewFileCache(1, t.TempDir(), WithIndexSize(1))
					if err != nil {
						t.Fatal(err)
					}
					return cache
				}(),
				items: []*strings.Reader{
					strings.NewReader("o"),
					strings.NewReader("x"),
				},
			},
			out: func(cache *FileCache) bool {
				return cache.indexSize.Load() == 1 && cache.index.Len() == 1
			},
			err: nil,
		},
		"on evict item is deleted from file system and index": {
			in: in{
				cache: func() *FileCache {
					cache, err := NewFileCache(1, t.TempDir(), WithIndexSize(1))
					if err != nil {
						t.Fatal(err)
					}
					return cache
				}(),
				items: []*strings.Reader{
					strings.NewReader("o"),
					strings.NewReader("x"),
				},
			},
			out: func(cache *FileCache) bool {
				_, ok := cache.index.Get("0")
				_, err := os.Stat(path.Join(cache.dir, "0"))

				return !ok && errors.Is(err, os.ErrNotExist)
			},
			err: nil,
		},
		"add same key twice": {
			in: in{
				cache: func() *FileCache {
					cache, err := NewFileCache(2, t.TempDir(), WithIndexSize(2))
					if err != nil {
						t.Fatal(err)
					}
					cache.Set("0", strings.NewReader("x"), 1)
					return cache
				}(),
				items: []*strings.Reader{
					strings.NewReader("x"),
				},
			},
			out: nil,
			err: ErrKeyExist,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			for i, item := range tc.in.items {
				err := tc.in.cache.Set(strconv.Itoa(i), item, item.Size())
				assert.Equal(t, tc.err, err)
			}

			if tc.out != nil {
				assert.True(t, tc.out(tc.in.cache))
			}
		})
	}
}

func TestFileCacheGet(t *testing.T) {
	type in struct {
		cache *FileCache
		items map[string][]byte
	}

	testcases := map[string]struct {
		in  in
		out map[string][]byte
		err error
	}{
		"get item that does not exist": {
			in: in{
				cache: func() *FileCache {
					cache, err := NewFileCache(1, t.TempDir())
					if err != nil {
						t.Fatal(err)
					}
					return cache
				}(),
			},
			out: map[string][]byte{
				"x": []byte("x"),
			},
			err: ErrKeyDoesntExist,
		},
		"get existing item": {
			in: in{
				cache: func() *FileCache {
					cache, err := NewFileCache(5, t.TempDir())
					if err != nil {
						t.Fatal(err)
					}
					return cache
				}(),
				items: map[string][]byte{
					"x": []byte("value"),
				},
			},
			out: map[string][]byte{
				"x": []byte("value"),
			},
			err: nil,
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			t.Parallel()

			for k, v := range tc.in.items {
				err := tc.in.cache.Set(k, bytes.NewReader(v), int64(len(v)))
				assert.NoError(t, err)
			}

			for k, v := range tc.out {
				data, err := tc.in.cache.Get(k)
				assert.Equal(t, tc.err, err)

				if tc.err == nil {
					assert.NotNil(t, data)

					result := make([]byte, len(v))
					_, err := data.Read(result)
					assert.NoError(t, err)
					assert.Equal(t, v, result)
				}
			}
		})
	}
}

type lockedReader struct {
	ch chan struct{}
}

func newLockedReader() lockedReader {
	return lockedReader{make(chan struct{})}
}

func (r *lockedReader) Read(b []byte) (int, error) {
	<-r.ch
	return 1, io.EOF
}

func (r *lockedReader) unlock() {
	close(r.ch)
}

func TestFileCacheConcurrentSet(t *testing.T) {
	cache, err := NewFileCache(1, t.TempDir())
	if err != nil {
		t.Fatal(err)
	}

	lr := newLockedReader()
	key := "key"

	ch := make(chan error)

	go func() {
		if err := cache.Set(key, &lr, 1); err != nil {
			ch <- err
		}
	}()

	go func() {
		if err := cache.Set(key, &lr, 1); err != nil {
			ch <- err
		}
	}()

	assert.Error(t, ErrKeySetInProgress, <-ch)

	lr.unlock()
}

func TestFileCacheMetrics(t *testing.T) {
	metricReader := metric.NewManualReader()
	meterProvider := metric.NewMeterProvider(metric.WithReader(metricReader))

	cache, err := NewFileCache(1, t.TempDir(),
		WithMetricMeter(meterProvider.Meter("test")))
	if err != nil {
		t.Fatal(err)
	}

	v := []byte("x")

	_ = cache.Set("key1", bytes.NewReader(v), int64(len(v)))
	_, _ = cache.Get("key1")
	_ = cache.Set("key2", bytes.NewReader(v), int64(len(v)))
	_, _ = cache.Get("key2")
	_, _ = cache.Get("key1")

	expected := metricdata.ScopeMetrics{
		Scope: instrumentation.Scope{
			Name: "test",
		},

		Metrics: []metricdata.Metrics{
			{
				Name: "cache.size",
				Unit: "byte",
				Data: metricdata.Gauge[int64]{
					DataPoints: []metricdata.DataPoint[int64]{
						{
							Attributes: attribute.NewSet(attribute.String("type", "current")),
							Value:      1,
						},
						{
							Attributes: attribute.NewSet(attribute.String("type", "max")),
							Value:      1,
						},
					},
				},
			},
			{
				Name: "cache.usage",
				Unit: "{count}",
				Data: metricdata.Sum[int64]{
					DataPoints: []metricdata.DataPoint[int64]{
						{
							Attributes: attribute.NewSet(attribute.String("type", "hits")),
							Value:      3,
						},
						{
							Attributes: attribute.NewSet(attribute.String("type", "misses")),
							Value:      1,
						},
						{
							Attributes: attribute.NewSet(attribute.String("type", "errors")),
							Value:      0,
						},
					},
					Temporality: metricdata.CumulativeTemporality,
					IsMonotonic: true,
				},
			},
		},
	}

	rm := metricdata.ResourceMetrics{}
	err = metricReader.Collect(context.Background(), &rm)
	assert.NoError(t, err)
	require.Len(t, rm.ScopeMetrics, 1)

	metricdatatest.AssertEqual(
		t,
		expected,
		rm.ScopeMetrics[0],
		metricdatatest.IgnoreTimestamp())
}
