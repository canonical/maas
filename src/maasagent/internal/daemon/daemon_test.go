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
	"context"
	"crypto/tls"
	"encoding/pem"
	"net/url"
	"testing"

	"github.com/spf13/afero"
	"github.com/stretchr/testify/require"
	"maas.io/core/src/maasagent/internal/certutil"
	"maas.io/core/src/maasagent/internal/client"
	certtest "maas.io/core/src/maasagent/internal/testing/cert"
	"maas.io/core/src/maasagent/internal/testing/faultyfs"
	"maas.io/core/src/maasagent/internal/token"
)

func newBootstrapTokenString(t *testing.T, u string) string {
	t.Helper()

	controllerURL, err := url.Parse(u)
	require.NoError(t, err)

	bt := token.BootstrapToken{
		Secret:      "s3cr3t",
		URL:         controllerURL,
		Fingerprint: t.Name(),
	}

	b, err := bt.MarshalText()
	require.NoError(t, err)

	return b
}

func exists(t *testing.T, fs afero.Fs, path string) bool {
	t.Helper()

	ok, err := afero.Exists(fs, path)
	require.NoError(t, err)

	return ok
}

type MockEnroller struct {
	cert string
	ca   string
}

func (c *MockEnroller) Enroll(ctx context.Context,
	req client.EnrollRequest) (*client.EnrollResponse, error) {
	return &client.EnrollResponse{
		Certificate: c.cert,
		CA:          c.ca,
	}, nil
}

func TestBootstrap(t *testing.T) {
	cert := certtest.GenerateTestCertificate(t)
	ca := certtest.GenerateTestCA(t)

	cfgFile := "config.yaml"

	certPEM := pem.EncodeToMemory(&pem.Block{
		Type:  "CERTIFICATE",
		Bytes: cert.Leaf.Raw,
	})
	caPEM := pem.EncodeToMemory(&pem.Block{
		Type:  "CERTIFICATE",
		Bytes: ca.Leaf.Raw,
	})

	controllerURL := "https://maas.internal"
	tok := newBootstrapTokenString(t, controllerURL)

	mockEnroller := func(_ *url.URL, _ *tls.Config) enroller {
		return &MockEnroller{
			cert: string(certPEM),
			ca:   string(caPEM),
		}
	}

	t.Run("happy path", func(t *testing.T) {
		fs := afero.NewMemMapFs()

		d := New()
		d.fs = fs
		d.enroller = mockEnroller

		require.NoError(t, d.Bootstrap(t.Context(), BootstrapOptions{
			Token:      tok,
			ConfigFile: cfgFile,
			CacheDir:   "cache",
			CertDir:    "certs",
		}))

		require.True(t, exists(t, fs, cfgFile), "missing config file")

		cfg, err := loadConfig(fs, cfgFile)
		require.NoError(t, err)

		require.True(t, exists(t, fs, cfg.TLS.KeyFile), "missing key file")
		require.True(t, exists(t, fs, cfg.TLS.CertFile), "missing cert file")
		require.True(t, exists(t, fs, cfg.TLS.CAFile), "missing CA file")
		require.Equal(t, controllerURL, cfg.ControllerURL.String())
	})

	t.Run("cleans on failure", func(t *testing.T) {
		// We want to fail writes to the actual path that Bootstrap will use
		// Derive them from the config template by running generateConfig.
		base := afero.NewMemMapFs()
		cfg, err := generateConfig(base, cfgFile, configOptions{
			ControllerURL: controllerURL,
			CacheDir:      "cache",
			CertDir:       "certs",
		})
		require.NoError(t, err)

		failures := map[string]string{
			"fail writing config": cfgFile,
			"fail writing ca":     cfg.TLS.CAFile,
			"fail writing key":    cfg.TLS.KeyFile,
			"fail writing cert":   cfg.TLS.CertFile,
		}

		for name, failPath := range failures {
			t.Run(name, func(t *testing.T) {
				fs := faultyfs.NewFs(afero.NewMemMapFs())
				fs.SetFailPath(failPath)

				d := New()
				d.fs = fs
				d.enroller = mockEnroller

				require.ErrorContains(t, d.Bootstrap(t.Context(), BootstrapOptions{
					Token:      tok,
					ConfigFile: cfgFile,
					CacheDir:   "cache",
					CertDir:    "certs",
				}), "injected fault for")

				require.False(t, exists(t, fs, cfg.TLS.KeyFile))
				require.False(t, exists(t, fs, cfg.TLS.CertFile))
				require.False(t, exists(t, fs, cfg.TLS.CAFile))
				require.False(t, exists(t, fs, cfgFile))
			})
		}
	})

	t.Run("keep custom files on failure", func(t *testing.T) {
		// Derive expected TLS file paths
		base := afero.NewMemMapFs()
		cfg, err := generateConfig(base, cfgFile, configOptions{
			ControllerURL: controllerURL,
			CacheDir:      "cache",
			CertDir:       "certs",
		})
		require.NoError(t, err)

		failures := map[string]string{
			"fail writing config": cfgFile,
			"fail writing ca":     cfg.TLS.CAFile,
		}

		for name, failPath := range failures {
			t.Run(name, func(t *testing.T) {
				fs := faultyfs.NewFs(afero.NewMemMapFs())
				fs.SetFailPath(failPath)

				// Precreate key/cert at the paths Bootstrap will use
				require.NoError(t, certutil.WritePrivateKey(fs, cfg.TLS.KeyFile, cert.PrivateKey))
				require.NoError(t, certutil.WriteCertificate(fs, cfg.TLS.CertFile, cert))

				customEnroller := func(_ *url.URL, _ *tls.Config) enroller {
					return &MockEnroller{ca: string(caPEM)}
				}

				d := New()
				d.fs = fs
				d.enroller = customEnroller

				require.ErrorContains(t, d.Bootstrap(t.Context(), BootstrapOptions{
					Token:      tok,
					ConfigFile: cfgFile,
					CacheDir:   "cache",
					CertDir:    "certs",
				}), "injected fault for")

				// Custom key/cert should remain.
				require.True(t, exists(t, fs, cfg.TLS.KeyFile))
				require.True(t, exists(t, fs, cfg.TLS.CertFile))

				// CA + config should be rolled back.
				require.False(t, exists(t, fs, cfg.TLS.CAFile))
				require.False(t, exists(t, fs, cfgFile))
			})
		}
	})
}
