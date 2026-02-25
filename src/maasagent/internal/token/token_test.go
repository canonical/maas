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

package token_test

import (
	"net/url"
	"testing"

	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"maas.io/core/src/maasagent/internal/token"
)

func TestBootstrapToken_UnmarshalBase64_Invalid(t *testing.T) {
	invalidBase64 := "invalid-base64"
	invalidJSON := "eyJmb28iOiAiYmFy"

	t.Run("invalid base64", func(t *testing.T) {
		var token token.BootstrapToken

		err := token.UnmarshalText(invalidBase64)

		assert.Error(t, err)
	})

	t.Run("invalid JSON", func(t *testing.T) {
		var token token.BootstrapToken

		err := token.UnmarshalText(invalidJSON)

		assert.Error(t, err)
	})
}

func TestBootstrapToken_MarshalUnmarshalBase64(t *testing.T) {
	url, err := url.Parse("https://maas.internal")
	require.NoError(t, err)

	original := token.BootstrapToken{
		Secret:      "s3cr3t",
		URL:         url,
		Fingerprint: "fingerprint",
	}

	b64, err := original.MarshalText()
	require.NoError(t, err)

	var decoded token.BootstrapToken
	require.NoError(t, decoded.UnmarshalText(b64))

	assert.Equal(t, original, decoded)
}

func TestBootstrapToken_MarshalUnmarshalJSON(t *testing.T) {
	u, err := url.Parse("https://maas.internal")
	require.NoError(t, err)

	expected := token.BootstrapToken{
		Secret:      "s3cr3t",
		URL:         u,
		Fingerprint: "fingerprint",
	}

	jsonData, err := expected.MarshalJSON()
	require.NoError(t, err)

	var actual token.BootstrapToken
	require.NoError(t, actual.UnmarshalJSON(jsonData))

	assert.Equal(t, expected.Secret, actual.Secret)
	assert.Equal(t, expected.Fingerprint, actual.Fingerprint)
	assert.Equal(t, expected.URL.String(), actual.URL.String())
}
