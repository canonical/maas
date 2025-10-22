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

package certutil

import (
	"bytes"
	"crypto/rand"
	"crypto/rsa"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/afero"
	"maas.io/core/src/maasagent/internal/pathutil"
)

// TODO: MAAS controller is using RSA 4096, this default is here to match it.
// We should consider moving to ECDSA instead.
const (
	defaultRSAKeySize = 4096
)

type dataPathFactory func(string) string

// CertBundle holds a private key along with a certificate.
// It is expected that certificate can be nil. In that case the caller should
// generate CSR and then save the signed certificate to update the bundle.
type CertBundle struct {
	fs              afero.Fs
	PrivateKey      *rsa.PrivateKey
	Certificate     *x509.Certificate
	dataPathFactory dataPathFactory
	keySize         int
}

type CertBundleOption func(*CertBundle)

// WithDataPathFactory used for testing.
func WithDataPathFactory(factory dataPathFactory) CertBundleOption {
	return func(cb *CertBundle) {
		cb.dataPathFactory = factory
	}
}

// WithFS sets a custom filesystem for testing purposes.
func WithFS(fs afero.Fs) CertBundleOption {
	return func(cb *CertBundle) {
		cb.fs = fs
	}
}

// WithRSAKeySize sets a custom key size to speed up testing.
func WithRSAKeySize(n int) CertBundleOption {
	return func(cb *CertBundle) {
		cb.keySize = n
	}
}

// NewCertBundle creates a new CertBundle with only a private key field being
// initialized with a newly generated key.
func NewCertBundle(opts ...CertBundleOption) (*CertBundle, error) {
	cb := &CertBundle{
		keySize:         defaultRSAKeySize,
		dataPathFactory: pathutil.GetDataPath,
		fs:              afero.NewOsFs(),
	}

	for _, opt := range opts {
		opt(cb)
	}

	certsDir := cb.dataPathFactory("certificates")

	keyFile := filepath.Join(filepath.Clean(certsDir), "client.key")

	key, err := rsa.GenerateKey(rand.Reader, cb.keySize)
	if err != nil {
		return nil, err
	}

	f, err := cb.fs.OpenFile(keyFile, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o600)
	if err != nil {
		return nil, fmt.Errorf("failed to open file for writing: %w", err)
	}
	defer f.Close() //nolint:errcheck // we could log this, but we decided not to.

	if err := pem.Encode(
		f,
		&pem.Block{
			Bytes: x509.MarshalPKCS1PrivateKey(key),
			Type:  "RSA PRIVATE KEY",
		},
	); err != nil {
		return nil, fmt.Errorf("failed to encode private key to PEM: %w", err)
	}

	cb.PrivateKey = key

	return cb, nil
}

// LoadCertBundle returns a new CertBundle using an existing private key and
// certificate from disk.
func LoadCertBundle(opts ...CertBundleOption) (*CertBundle, error) {
	cb := &CertBundle{
		dataPathFactory: pathutil.GetDataPath,
		fs:              afero.NewOsFs(),
	}

	for _, opt := range opts {
		opt(cb)
	}

	certsDir := cb.dataPathFactory("certificates")

	keyFile := filepath.Join(filepath.Clean(certsDir), "client.key")
	certFile := filepath.Join(filepath.Clean(certsDir), "client.pem")

	key, err := loadPrivateKey(cb.fs, keyFile)
	if err != nil {
		return nil, err
	}

	cb.PrivateKey = key

	cert, err := loadCertificate(cb.fs, certFile)
	if err != nil {
		return nil, err
	}

	cb.Certificate = cert

	return cb, nil
}

// SetCertificateFromPEM writes a certificate as PEM to disk, and updates the
// bundle.
func (cb *CertBundle) SetCertificateFromPEM(fs afero.Fs, pemData []byte) error {
	block, _ := pem.Decode(pemData)
	if block == nil {
		return fmt.Errorf("failed to decode PEM block")
	}

	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return fmt.Errorf("failed to parse certificate: %w", err)
	}

	certsDir := cb.dataPathFactory("certificates")
	certFile := filepath.Join(certsDir, "client.pem")

	if err := afero.WriteFile(fs, certFile, pemData, 0o644); err != nil {
		return fmt.Errorf("failed to write certificate to file: %w", err)
	}

	cb.Certificate = cert

	return nil
}

// GenerateCSRPEM generates a PEM encoded CSR for a given Common Name and using
// a private key from the bundle to sign it.
func (cb *CertBundle) GenerateCSRPEM(cn string) ([]byte, error) {
	derBytes, err := x509.CreateCertificateRequest(rand.Reader,
		&x509.CertificateRequest{Subject: pkix.Name{CommonName: cn}}, cb.PrivateKey)
	if err != nil {
		return nil, fmt.Errorf("error creating CSR: %w", err)
	}

	pemBytes := bytes.NewBuffer([]byte{})

	err = pem.Encode(pemBytes, &pem.Block{Type: "CERTIFICATE REQUEST",
		Bytes: derBytes})
	if err != nil {
		return nil, fmt.Errorf("error encoding certificate PEM: %w", err)
	}

	return pemBytes.Bytes(), err
}

// loadPrivateKey would try to load PEM-encoded key from file.
func loadPrivateKey(fs afero.Fs, path string) (*rsa.PrivateKey, error) {
	b, err := afero.ReadFile(fs, path)
	if err != nil {
		return nil, err
	}

	block, _ := pem.Decode(b)
	if block == nil {
		return nil, fmt.Errorf("failed to decode PEM block")
	}

	return x509.ParsePKCS1PrivateKey(block.Bytes)
}

// loadCertificate loads a PEM-encoded certificate from the given file.
func loadCertificate(fs afero.Fs, path string) (*x509.Certificate, error) {
	data, err := afero.ReadFile(fs, path)
	if err != nil {
		return nil, fmt.Errorf("failed to read certificate file: %w", err)
	}

	block, _ := pem.Decode(data)
	if block == nil {
		return nil, fmt.Errorf("failed to decode PEM block")
	}

	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("failed to parse certificate: %w", err)
	}

	return cert, nil
}
