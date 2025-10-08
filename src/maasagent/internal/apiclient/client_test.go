// Copyright (c) 2025 Canonical Ltd
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

package apiclient

import (
	"crypto/sha256"
	"encoding/hex"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestTLSConfigWithFingerprintPinning(t *testing.T) {
	srv := httptest.NewUnstartedServer(http.HandlerFunc(
		func(w http.ResponseWriter, r *http.Request) {
			w.WriteHeader(http.StatusOK)
			_, _ = w.Write([]byte("ok"))
		}))

	srv.StartTLS()
	defer srv.Close()

	cert := srv.TLS.Certificates[0].Leaf
	hash := sha256.Sum256(cert.Raw)
	fingerprint := hex.EncodeToString(hash[:])

	t.Run("accepts pinned fingerprint", func(t *testing.T) {
		client := &http.Client{
			Transport: &http.Transport{
				TLSClientConfig: TLSConfigWithFingerprintPinning([]string{fingerprint}),
			},
		}

		//nolint:noctx // this is okay not to have a context here
		resp, err := client.Get(srv.URL)
		assert.NoError(t, err, "expected success")

		defer resp.Body.Close()

		assert.Equal(t, http.StatusOK, resp.StatusCode)
	})

	t.Run("rejects mismatched fingerprint", func(t *testing.T) {
		client := &http.Client{
			Transport: &http.Transport{
				TLSClientConfig: TLSConfigWithFingerprintPinning([]string{"foo"}),
			},
		}

		//nolint:noctx // this is okay not to have a context here
		_, err := client.Get(srv.URL)
		assert.Error(t, err, "expected fingerprint mismatch error")
	})

	t.Run("rejects untrusted", func(t *testing.T) {
		client := &http.Client{}

		//nolint:noctx // this is okay not to have a context here
		_, err := client.Get(srv.URL)
		assert.Error(t, err, "expected certificate validation error")
	})
}
