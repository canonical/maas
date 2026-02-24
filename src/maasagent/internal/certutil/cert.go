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

package certutil

import (
	"bytes"
	"crypto"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"fmt"

	"github.com/spf13/afero"
	"maas.io/core/src/maasagent/internal/atomicfile"
)

// WriteCertificate encodes the entire certificate chain from a tls.Certificate
// into PEM format and writes it to the specified path. The certificates are
// written in order, starting with the leaf. It uses an atomic write to
// prevent file corruption.
func WriteCertificate(fs afero.Fs, path string, cert tls.Certificate) error {
	if len(cert.Certificate) == 0 {
		return fmt.Errorf("certificate contains no data")
	}

	var buf bytes.Buffer

	for i, der := range cert.Certificate {
		block := &pem.Block{
			Type:  "CERTIFICATE",
			Bytes: der,
		}

		if err := pem.Encode(&buf, block); err != nil {
			return fmt.Errorf("failed to encode certificate at index %d: %w", i, err)
		}
	}

	if err := atomicfile.WriteFileWithFs(fs, path, buf.Bytes(), 0o644); err != nil {
		return fmt.Errorf("failed to write certificate chain to %s: %w", path, err)
	}

	return nil
}

// WritePrivateKey marshals the given crypto.PrivateKey into PKCS#8 PEM format
// and writes it to the specified path. It uses an atomic write to prevent
// file corruption.
func WritePrivateKey(fs afero.Fs, path string, key crypto.PrivateKey) error {
	der, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		return fmt.Errorf("failed to marshal private key: %v", err)
	}

	var buf bytes.Buffer

	block := &pem.Block{
		Type:  "PRIVATE KEY",
		Bytes: der,
	}

	if err := pem.Encode(&buf, block); err != nil {
		return fmt.Errorf("failed to encode key: %w", err)
	}

	if err := atomicfile.WriteFileWithFs(fs, path, buf.Bytes(), 0o600); err != nil {
		return fmt.Errorf("failed to write key to %s: %w", path, err)
	}

	return nil
}

// CreateCSR generates a PEM-encoded certificate signing request (CSR) using
// the provided private key and common name (CN).
// The CSR is created in PKCS#10 format.
func CreateCSR(cn string, key crypto.PrivateKey) ([]byte, error) {
	derBytes, err := x509.CreateCertificateRequest(rand.Reader,
		&x509.CertificateRequest{Subject: pkix.Name{CommonName: cn}}, key)
	if err != nil {
		return nil, fmt.Errorf("error creating CSR: %w", err)
	}

	pemBytes := bytes.NewBuffer([]byte{})

	err = pem.Encode(pemBytes, &pem.Block{Type: "CERTIFICATE REQUEST",
		Bytes: derBytes})
	if err != nil {
		return nil, fmt.Errorf("error encoding CSR into PEM: %w", err)
	}

	return pemBytes.Bytes(), nil
}

// WriteCertificatePEM validates that the provided certPEM contains at least
// one valid PEM-encoded X.509 certificate (scanning all CERTIFICATE blocks),
// and writes the PEM data to a file.
//
// Returns an error if no valid CERTIFICATE blocks are found in certPEM, if any
// block cannot be parsed as an X.509 certificate, or if writing the file fails.
func WriteCertificatePEM(fs afero.Fs, path string, certPEM []byte) error {
	tail := certPEM
	found := false

	for {
		block, next := pem.Decode(tail)
		if block == nil {
			break
		}

		if block.Type != "CERTIFICATE" {
			return fmt.Errorf("unexpected PEM block type: %s", block.Type)
		}

		if _, err := x509.ParseCertificate(block.Bytes); err != nil {
			return fmt.Errorf("invalid certificate in CA: %w", err)
		}

		found = true
		tail = next
	}

	if !found {
		return fmt.Errorf("did not find any CERTIFICATE blocks")
	}

	if err := atomicfile.WriteFileWithFs(fs, path, certPEM, 0o644); err != nil {
		return fmt.Errorf("failed to write CA PEM to file: %w", err)
	}

	return nil
}

// LoadX509KeyPair works like tls.LoadX509KeyPair but allows using afero.Fs
func LoadX509KeyPair(fs afero.Fs, certFile string,
	keyFile string) (tls.Certificate, error) {
	keyPEM, err := afero.ReadFile(fs, keyFile)
	if err != nil {
		return tls.Certificate{}, fmt.Errorf("failed to read private key: %w", err)
	}

	certPEM, err := afero.ReadFile(fs, certFile)
	if err != nil {
		return tls.Certificate{}, fmt.Errorf("failed to read certificate: %w", err)
	}

	return tls.X509KeyPair(certPEM, keyPEM)
}

// LoadCAPool returns x509.SystemCertPool with added PEM data read from afero.Fs
func LoadCAPool(fs afero.Fs, caFile string) (*x509.CertPool, error) {
	caPEM, err := afero.ReadFile(fs, caFile)
	if err != nil {
		return nil, fmt.Errorf("read CA file: %w", err)
	}

	pool, err := x509.SystemCertPool()
	if err != nil {
		return nil, fmt.Errorf("system cert pool: %w", err)
	}

	if ok := pool.AppendCertsFromPEM(caPEM); !ok {
		return nil, fmt.Errorf("no certificates found in %s", caFile)
	}

	return pool, nil
}
