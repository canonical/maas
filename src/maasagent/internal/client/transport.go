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

package client

import (
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"
)

// NewTLSConfigWithFingerprintPinning returns a *tls.Config that only accepts
// server certificates matching the given SHA256 fingerprint.
func NewTLSConfigWithFingerprintPinning(fingerprint string) *tls.Config {
	want := strings.ToLower(strings.ReplaceAll(fingerprint, ":", ""))

	return &tls.Config{
		MinVersion:         tls.VersionTLS12,
		InsecureSkipVerify: true, //nolint:gosec // G402: we verify fingerprint manually
		VerifyPeerCertificate: func(rawCerts [][]byte,
			_ [][]*x509.Certificate) error {
			if len(rawCerts) == 0 {
				return errors.New("no server certificate provided")
			}

			// We are interested in a leaf certificate only
			leafCert := rawCerts[0]
			hash := sha256.Sum256(leafCert)

			got := hex.EncodeToString(hash[:])
			if got == want {
				return nil
			}

			return fmt.Errorf("certificate fingerprint mismatch: got %s, want %s", got, want)
		},
	}
}

// NewTLSConfigWithCAValidationOnly returns a *tls.Config that can be used for mTLS
// The TLS configuration validates the certificate against the provided CA pool
// but intentionally skips hostname or SAN verification.
func NewTLSConfigWithCAValidationOnly(cert tls.Certificate, ca *x509.CertPool) *tls.Config {
	// XXX: This is a temporary solution and should be replaced once proper PKI
	// integration is implemented or until MAAS will include IP SANs.
	return &tls.Config{
		MinVersion:         tls.VersionTLS12,
		Certificates:       []tls.Certificate{cert},
		InsecureSkipVerify: true, //nolint:gosec // G402: verify manually using CA
		VerifyPeerCertificate: func(rawCerts [][]byte,
			_ [][]*x509.Certificate) error {
			if len(rawCerts) == 0 {
				return errors.New("no server certificate provided")
			}

			leafCert, err := x509.ParseCertificate(rawCerts[0])
			if err != nil {
				return fmt.Errorf("failed to parse certificate: %w", err)
			}

			// DNSName is intentionally omitted to skip hostname/SAN verification.
			opts := x509.VerifyOptions{
				Roots:         ca,
				Intermediates: x509.NewCertPool(),
			}

			if len(rawCerts) > 1 {
				for _, rawCert := range rawCerts[1:] {
					c, err := x509.ParseCertificate(rawCert)
					if err != nil {
						return fmt.Errorf("failed to parse intermediate certificate: %w", err)
					}
					opts.Intermediates.AddCert(c)
				}
			}

			if _, err := leafCert.Verify(opts); err != nil {
				return fmt.Errorf("certificate verification failed: %w", err)
			}

			return nil
		},
	}
}
