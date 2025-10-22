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

package apiclient

import (
	"bytes"
	"context"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/url"
	"slices"
)

type APIClient struct {
	baseURL    *url.URL
	httpClient *http.Client
}

func NewAPIClient(baseURL *url.URL, httpClient *http.Client) *APIClient {
	return &APIClient{
		baseURL:    baseURL,
		httpClient: httpClient,
	}
}

// Request is a generic method for making HTTP requests to the internal MAAS API.
func (c *APIClient) Request(ctx context.Context, method, path string,
	body []byte) (*http.Response, error) {
	url, err := url.JoinPath(c.baseURL.String(), path)
	if err != nil {
		return nil, fmt.Errorf("wrong URL path: %s", path)
	}

	req, err := http.NewRequestWithContext(ctx, method, url, bytes.NewBuffer(body))
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}

	return resp, nil
}

// TLSConfigWithFingerprintPinning returns a *tls.Config that only accepts
// server certificates matching the given SHA256 fingerprint.
func TLSConfigWithFingerprintPinning(fingerprints []string) *tls.Config {
	return &tls.Config{
		InsecureSkipVerify: true, //nolint:gosec // G402: we verify fingerprint manually
		VerifyPeerCertificate: func(rawCerts [][]byte,
			verifiedChains [][]*x509.Certificate) error {
			if len(rawCerts) == 0 {
				return fmt.Errorf("no server certificates")
			}
			// We are interested in a leaf certificate only
			cert := rawCerts[0]
			hash := sha256.Sum256(cert)
			got := hex.EncodeToString(hash[:])

			if slices.Contains(fingerprints, got) {
				return nil
			}

			return fmt.Errorf("certificate fingerprint mismatch: got %s", got)
		},
	}
}
