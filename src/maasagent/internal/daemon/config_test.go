// Copyright (c) 2026 Canonical Ltd
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

package daemon

import (
	_ "embed"
	"fmt"
	"net/url"
	"testing"
	"time"

	"github.com/spf13/afero"
	"github.com/stretchr/testify/require"
	"gopkg.in/yaml.v3"
)

func TestByteSize(t *testing.T) {
	format := `services:
  http_proxy:
    cache:
      size: %s`

	testcases := map[string]struct {
		out ByteSize[int64]
	}{
		"13370042B": {
			out: ByteSize[int64]{Bytes: 13370042, Raw: "13370042B"},
		},
		"1337KB": {
			out: ByteSize[int64]{Bytes: 1337000, Raw: "1337KB"},
		},
		"0.5GB": {
			out: ByteSize[int64]{Bytes: 500000000, Raw: "0.5GB"},
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			expected := fmt.Appendf(nil, format, name)

			var conf Config
			require.NoError(t, yaml.Unmarshal(expected, &conf))
			require.Equal(t, tc.out, conf.Services.HTTPProxy.Cache.Size)
		})
	}
}

func TestConfig(t *testing.T) {
	controllerURL, err := url.Parse("https://maas.internal:5242")
	require.NoError(t, err)

	fs := afero.NewMemMapFs()
	path := "config.yaml"

	cfg, err := generateConfig(
		fs, path,
		configOptions{
			ControllerURL: controllerURL.String(),
			CacheDir:      "/cache",
			CertDir:       "/certificates",
		},
	)
	require.NoError(t, err)

	loaded, err := loadConfig(fs, path)
	require.NoError(t, err)

	expected := &Config{
		ControllerURL: controllerURL,
		TLS: TLSConfig{
			CertFile: "/certificates/agent.crt",
			KeyFile:  "/certificates/agent.key",
			CAFile:   "/certificates/ca.pem",
		},
		Services: Services{
			HTTPProxy: HTTPProxyConfig{
				Cache: HTTPProxyCache{
					Dir:  "/cache/httpproxy",
					Size: ByteSize[int64]{Bytes: 20000000000, Raw: "20GB"},
				},
			},
			DNS: DNSConfig{
				Cache: DNSCache{
					Size: ByteSize[int64]{Bytes: 50000000, Raw: "50MB"},
				},
				ConnectionPool: 5,
				DialTimeout:    5 * time.Second,
			},
		},
		Observability: ObservabilityConfig{
			Logging: LoggingConfig{Level: "error"},
			Metrics: MetricsConfig{
				Enabled: false,
			},
			Profiling: ProfilingConfig{
				Enabled: false,
			},
		},
	}

	require.Equal(t, expected, cfg)
	require.Equal(t, loaded, cfg)
}
