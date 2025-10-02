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

package certutil_test

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"math/big"
	"os"
	"path/filepath"
	"testing"
	"time"

	"maas.io/core/src/maasagent/internal/certutil"

	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	"github.com/stretchr/testify/suite"
)

// GenerateTestKeyPair returns a generated RSA private key and a self-signed
// certificate
func GenerateTestKeyPair(t *testing.T) (*rsa.PrivateKey, *x509.Certificate) {
	t.Helper()

	key, err := rsa.GenerateKey(rand.Reader, 1024) // 1024 is enough for tests
	if err != nil {
		t.Fatalf("failed to generate private key: %v", err)
	}

	tmpl := &x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject:      pkix.Name{CommonName: t.Name()},
		NotBefore:    time.Now(),
		NotAfter:     time.Now().Add(24 * time.Hour),

		KeyUsage:    x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature,
		ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}

	der, err := x509.CreateCertificate(rand.Reader, tmpl, tmpl, &key.PublicKey, key)
	if err != nil {
		t.Fatalf("failed to create certificate: %v", err)
	}

	cert, err := x509.ParseCertificate(der)
	if err != nil {
		t.Fatalf("failed to parse generated certificate: %v", err)
	}

	return key, cert
}

// GenerateTestKeyPair returns a generated RSA private key
func GenerateTestKey(t *testing.T) *rsa.PrivateKey {
	t.Helper()

	key, err := rsa.GenerateKey(rand.Reader, 1024) // 1024 is enough for tests
	if err != nil {
		t.Fatalf("failed to generate private key: %v", err)
	}

	return key
}

// GenerateTestKeyPair returns a generated RSA private key.
func GenerateTestCertificate(t *testing.T, key *rsa.PrivateKey) *x509.Certificate {
	t.Helper()

	tmpl := &x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject:      pkix.Name{CommonName: t.Name()},
		NotBefore:    time.Now(),
		NotAfter:     time.Now().Add(24 * time.Hour),
		KeyUsage:     x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageClientAuth},
	}

	der, err := x509.CreateCertificate(rand.Reader, tmpl, tmpl, &key.PublicKey, key)
	if err != nil {
		t.Fatalf("failed to create certificate: %v", err)
	}

	cert, err := x509.ParseCertificate(der)
	if err != nil {
		t.Fatalf("failed to parse generated certificate: %v", err)
	}

	return cert
}

// writePEM is an internal helper that writes a PEM block to a file.
func writePEM(t *testing.T, fs afero.Fs,
	path, blockType string, bytes []byte, perm os.FileMode) {
	t.Helper()

	f, err := fs.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, perm)
	if err != nil {
		t.Fatalf("failed to open file %s: %v", path, err)
	}
	defer f.Close()

	if err := pem.Encode(f, &pem.Block{Type: blockType, Bytes: bytes}); err != nil {
		t.Fatalf("failed to encode %s to %s: %v", blockType, path, err)
	}
}

// WritePrivateKeyPEM writes a private key to the given path in PEM format.
func WritePrivateKeyPEM(t *testing.T, fs afero.Fs,
	path string, priv *rsa.PrivateKey) {
	writePEM(t, fs, path, "RSA PRIVATE KEY",
		x509.MarshalPKCS1PrivateKey(priv), 0o600)
}

// WriteCertificatePEM writes a certificate to the given path in PEM format.
func WriteCertificatePEM(t *testing.T, fs afero.Fs,
	path string, cert *x509.Certificate) {
	writePEM(t, fs, path, "CERTIFICATE", cert.Raw, 0o644)
}

type CertificateBundleTestSuite struct {
	suite.Suite
	fs              afero.Fs
	dataPathFactory func(string) string
}

func (s *CertificateBundleTestSuite) SetupTest() {
	s.fs = afero.NewMemMapFs()
	s.dataPathFactory = func(string) string { return "certificates" }
}

func TestCertificateBundleTestSuite(t *testing.T) {
	suite.Run(t, new(CertificateBundleTestSuite))
}

func (s *CertificateBundleTestSuite) TestLoadCertBundle() {
	keyFile := filepath.Join("certificates", "client.key")
	certFile := filepath.Join("certificates", "client.pem")

	key, cert := GenerateTestKeyPair(s.T())
	WritePrivateKeyPEM(s.T(), s.fs, keyFile, key)
	WriteCertificatePEM(s.T(), s.fs, certFile, cert)

	bundle, err := certutil.LoadCertBundle(
		certutil.WithFS(s.fs),
		certutil.WithDataPathFactory(s.dataPathFactory),
	)

	require.NoError(s.T(), err)

	assert.Equal(s.T(), key, bundle.PrivateKey)
	assert.Equal(s.T(), cert, bundle.Certificate)
}

func (s *CertificateBundleTestSuite) TestNewCertBundle() {
	bundle, err := certutil.NewCertBundle(
		certutil.WithFS(s.fs),
		certutil.WithDataPathFactory(s.dataPathFactory),
		certutil.WithRSAKeySize(1024),
	)

	require.NoError(s.T(), err)

	keyFile := filepath.Join("certificates", "client.key")

	info, err := s.fs.Stat(keyFile)
	assert.NoError(s.T(), err)
	assert.Equal(s.T(), os.FileMode(0o600), info.Mode().Perm())

	assert.NotNil(s.T(), bundle.PrivateKey)
	assert.Nil(s.T(), bundle.Certificate)
}

func (s *CertificateBundleTestSuite) TestGenerateCSR() {
	bundle, err := certutil.NewCertBundle(
		certutil.WithFS(s.fs),
		certutil.WithDataPathFactory(s.dataPathFactory),
		certutil.WithRSAKeySize(1024),
	)
	require.NoError(s.T(), err)

	csrPEM, err := bundle.GenerateCSRPEM(s.T().Name())
	require.NoError(s.T(), err)

	block, _ := pem.Decode(csrPEM)
	if block == nil || block.Type != "CERTIFICATE REQUEST" {
		s.T().Fatal("invalid PEM block type")
	}

	csr, err := x509.ParseCertificateRequest(block.Bytes)
	assert.NoError(s.T(), err)

	assert.Equal(s.T(), s.T().Name(), csr.Subject.CommonName)
}

func (s *CertificateBundleTestSuite) TestSetCertificateFromPem() {
	bundle, err := certutil.NewCertBundle(
		certutil.WithFS(s.fs),
		certutil.WithDataPathFactory(s.dataPathFactory),
		certutil.WithRSAKeySize(1024),
	)
	require.NoError(s.T(), err)

	require.NotNil(s.T(), bundle.PrivateKey)
	require.Nil(s.T(), bundle.Certificate)

	cert := GenerateTestCertificate(s.T(), bundle.PrivateKey)
	require.NotNil(s.T(), cert)

	pemData := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: cert.Raw})

	assert.NoError(s.T(), bundle.SetCertificateFromPEM(s.fs, pemData))
	assert.NotNil(s.T(), bundle.Certificate)
}
