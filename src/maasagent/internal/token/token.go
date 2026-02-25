// Copyright (c) 2025-2026 Canonical Ltd
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

package token

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/url"
)

// BootstrapToken is used to authenticate during enrollment.
// It includes the secret for validation, API endpoint URL and the fingerprint
// used to validate the controller's TLS certificate.
type BootstrapToken struct {
	Secret      string   `json:"secret"`
	URL         *url.URL `json:"-"`
	Fingerprint string   `json:"fingerprint"`
}

// ParseBootstrapToken parses and validates a bootstrap token string.
// It returns an error if the token is malformed.
func ParseBootstrapToken(s string) (BootstrapToken, error) {
	token := BootstrapToken{}
	return token, token.UnmarshalText(s)
}

// MarshalText encodes BootstrapToken into Base64 encoded JSON
func (t *BootstrapToken) MarshalText() (string, error) {
	jsonBytes, err := json.Marshal(t)
	if err != nil {
		return "", fmt.Errorf("failed to marshal JSON: %w", err)
	}

	return base64.StdEncoding.EncodeToString(jsonBytes), nil
}

// UnmarshalText decodes base64 encoded JSON into the BootstrapToken
func (t *BootstrapToken) UnmarshalText(data string) error {
	decoded, err := base64.StdEncoding.DecodeString(data)
	if err != nil {
		return fmt.Errorf("failed to decode base64: %w", err)
	}

	if err := json.Unmarshal(decoded, t); err != nil {
		return fmt.Errorf("failed to unmarshal JSON: %w", err)
	}

	return nil
}

// MarshalJSON implements the json.Marshaler interface for BootstrapToken.
// It converts the Controller to JSON format, including the URL as a string.
func (t *BootstrapToken) MarshalJSON() ([]byte, error) {
	var url string

	if t.URL != nil {
		url = t.URL.String()
	}

	return json.Marshal(
		struct {
			Secret      string `json:"secret"`
			Fingerprint string `json:"fingerprint"`
			URL         string `json:"url"`
		}{
			Secret:      t.Secret,
			Fingerprint: t.Fingerprint,
			URL:         url,
		},
	)
}

// UnmarshalJSON implements the json.Unmarshaler interface for BootstrapToken.
// It parses JSON data into a BootstrapToken, converting the URL string to a url.URL.
func (t *BootstrapToken) UnmarshalJSON(data []byte) error {
	var tt struct {
		Secret      string `json:"secret"`
		Fingerprint string `json:"fingerprint"`
		URL         string `json:"url"`
	}

	if err := json.Unmarshal(data, &tt); err != nil {
		return err
	}

	url, err := url.Parse(tt.URL)
	if err != nil {
		return fmt.Errorf("invalid URL: %w", err)
	}

	t.Secret = tt.Secret
	t.Fingerprint = tt.Fingerprint
	t.URL = url

	return nil
}
