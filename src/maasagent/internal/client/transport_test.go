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

//go:debug rsa1024min=0

package client

import (
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/require"
	"maas.io/core/src/maasagent/internal/testing/cert"
)

func TestNewTLSConfigWithFingerprintPinning(t *testing.T) {
	srv := httptest.NewUnstartedServer(http.HandlerFunc(
		func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("ok"))
		}))

	srv.StartTLS()
	defer srv.Close()

	leafCert := srv.TLS.Certificates[0].Leaf
	hash := sha256.Sum256(leafCert.Raw)
	fingerprint := hex.EncodeToString(hash[:])

	t.Run("accepts pinned fingerprint", func(t *testing.T) {
		client := &http.Client{
			Transport: &http.Transport{
				TLSClientConfig: NewTLSConfigWithFingerprintPinning(fingerprint),
			},
		}

		req, err := http.NewRequestWithContext(t.Context(), http.MethodGet,
			srv.URL, nil)
		require.NoError(t, err)
		resp, err := client.Do(req)
		require.NoError(t, err)

		defer resp.Body.Close()

		require.Equal(t, http.StatusOK, resp.StatusCode)
	})

	t.Run("rejects mismatched fingerprint", func(t *testing.T) {
		client := &http.Client{
			Transport: &http.Transport{
				TLSClientConfig: NewTLSConfigWithFingerprintPinning("foo"),
			},
		}

		req, err := http.NewRequestWithContext(t.Context(), http.MethodGet, srv.URL, nil)
		require.NoError(t, err)

		_, err = client.Do(req)
		require.Error(t, err, "expected fingerprint mismatch error")
	})

	t.Run("rejects untrusted", func(t *testing.T) {
		client := &http.Client{}

		req, err := http.NewRequestWithContext(t.Context(), http.MethodGet, srv.URL, nil)
		require.NoError(t, err)

		_, err = client.Do(req)
		require.Error(t, err, "expected certificate validation error")
	})
}

func TestNewTLSConfigWithCAValidationOnly(t *testing.T) {
	trustedCA := cert.GenerateTestCA(t)
	trustedPool := x509.NewCertPool()
	trustedX509, err := x509.ParseCertificate(trustedCA.Certificate[0])
	require.NoError(t, err)
	trustedPool.AddCert(trustedX509)

	untrustedCA := cert.GenerateTestCA(t)

	tests := []struct {
		name     string
		serverCA tls.Certificate
		wantErr  bool
	}{
		{
			name:     "trusted CA accepts connection",
			serverCA: cert.GenerateTestCertificate(t, cert.WithCA(trustedCA)),
			wantErr:  false,
		},
		{
			name:     "untrusted CA rejects connection",
			serverCA: cert.GenerateTestCertificate(t, cert.WithCA(untrustedCA)),
			wantErr:  true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()

			ts := httptest.NewUnstartedServer(http.HandlerFunc(
				func(w http.ResponseWriter, r *http.Request) {
					w.WriteHeader(http.StatusOK)
				}))
			ts.TLS = &tls.Config{Certificates: []tls.Certificate{tc.serverCA}}

			ts.StartTLS()
			defer ts.Close()

			client := ts.Client()
			client.Transport.(*http.Transport).TLSClientConfig =
				NewTLSConfigWithCAValidationOnly(
					cert.GenerateTestCertificate(t), trustedPool)

			req, err := http.NewRequestWithContext(t.Context(), http.MethodGet, ts.URL, nil)
			require.NoError(t, err)

			_, err = client.Do(req)
			if tc.wantErr {
				require.Error(t, err)
			} else {
				require.NoError(t, err)
			}
		})
	}
}
