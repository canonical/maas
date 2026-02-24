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
package daemon

import (
	"crypto/x509"
	"encoding/pem"
	"testing"

	"github.com/spf13/afero"
	"github.com/stretchr/testify/require"
	"maas.io/core/src/maasagent/internal/certutil"
	"maas.io/core/src/maasagent/internal/testing/cert"
)

func TestGenerateIdentity_New(t *testing.T) {
	fs := afero.NewMemMapFs()

	identity, err := generateIdentity(fs, "null.crt", "null.key", withKeySize(512))
	require.NoError(t, err)
	require.NotNil(t, identity)

	// Verify UUID exists and is formatted correctly
	require.Len(t, identity.ID, 36)

	require.NotNil(t, identity.Certificate.PrivateKey)
	require.NotEmpty(t, len(identity.CSR))

	// Parse the CSR to ensure it's valid and contains the UUID as the Subject
	block, _ := pem.Decode(identity.CSR)
	csr, err := x509.ParseCertificateRequest(block.Bytes)
	require.NoError(t, err)

	require.Equal(t, csr.Subject.CommonName, identity.ID)
}

func TestGenerateIdentity_Existing(t *testing.T) {
	certFile := "existing.crt"
	keyFile := "existing.key"

	crt := cert.GenerateTestCertificate(t)

	t.Run("existing cert and key", func(t *testing.T) {
		fs := afero.NewMemMapFs()

		require.NoError(t, certutil.WriteCertificate(fs, certFile, crt))
		require.NoError(t, certutil.WritePrivateKey(fs, keyFile, crt.PrivateKey))

		identity, err := generateIdentity(fs, certFile, keyFile, withKeySize(512))
		require.NoError(t, err)
		require.NotNil(t, identity)

		require.NotNil(t, identity.Certificate.PrivateKey)
		require.NotNil(t, identity.Certificate.Certificate)
		require.Nil(t, identity.CSR)
	})

	t.Run("missing cert", func(t *testing.T) {
		fs := afero.NewMemMapFs()

		require.NoError(t, certutil.WritePrivateKey(fs, keyFile, crt.PrivateKey))

		identity, err := generateIdentity(fs, certFile, keyFile, withKeySize(512))
		require.NoError(t, err)
		require.NotNil(t, identity)

		require.NotNil(t, identity.Certificate.PrivateKey)
		require.Nil(t, identity.Certificate.Certificate)
		require.NotNil(t, identity.CSR)
	})

	t.Run("missing key", func(t *testing.T) {
		fs := afero.NewMemMapFs()

		require.NoError(t, certutil.WriteCertificate(fs, certFile, crt))

		identity, err := generateIdentity(fs, certFile, keyFile, withKeySize(512))
		require.NoError(t, err)
		require.NotNil(t, identity)

		require.NotNil(t, identity.Certificate.PrivateKey)
		require.Nil(t, identity.Certificate.Certificate)
		require.NotNil(t, identity.CSR)
	})
}
