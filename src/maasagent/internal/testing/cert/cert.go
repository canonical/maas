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

package cert

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"fmt"
	"math/big"
	"testing"
	"time"
)

type certOptions struct {
	template *x509.Certificate
	parent   *x509.Certificate
	priv     any
}

// CertificateOption defines a function for customizing certificate generation.
type CertificateOption func(*certOptions)

// WithCommonName overrides the certificate's Common Name.
func WithCommonName(cn string) CertificateOption {
	return func(o *certOptions) {
		o.template.Subject.CommonName = cn
	}
}

// WithDNSNames sets the Subject Alternative Names (SANs).
func WithDNSNames(names ...string) CertificateOption {
	return func(o *certOptions) {
		o.template.DNSNames = append(o.template.DNSNames, names...)
	}
}

// WithCA sets CA to sign the certificate. By default it is self-signed
func WithCA(ca tls.Certificate) CertificateOption {
	return func(o *certOptions) {
		parent, err := x509.ParseCertificate(ca.Certificate[0])
		if err != nil {
			panic(fmt.Sprintf("invalid CA certificate: %v", err))
		}

		o.parent = parent
		o.priv = ca.PrivateKey
	}
}

// generateTestCertificate is an internal helper for generating certificate.
func generateTestCertificate(tb testing.TB,
	templateFn func(tb testing.TB) *x509.Certificate,
	opts ...CertificateOption) tls.Certificate {
	tb.Helper()
	//nolint:gosec // 1024 bits is enough for testing
	key, err := rsa.GenerateKey(rand.Reader, 1024)
	if err != nil {
		tb.Fatalf("failed to generate private key: %v", err)
	}

	template := templateFn(tb)

	co := &certOptions{
		template: template,
		parent:   template,
		priv:     key,
	}

	for _, opt := range opts {
		opt(co)
	}

	certDER, err := x509.CreateCertificate(rand.Reader, template, co.parent,
		&key.PublicKey, co.priv)
	if err != nil {
		tb.Fatalf("failed to create certificate: %v", err)
	}

	keyDER, err := x509.MarshalPKCS8PrivateKey(key)
	if err != nil {
		tb.Fatalf("failed to marshal private key: %v", err)
	}

	certPEM := pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: certDER})
	keyPEM := pem.EncodeToMemory(&pem.Block{Type: "PRIVATE KEY", Bytes: keyDER})

	cert, err := tls.X509KeyPair(certPEM, keyPEM)
	if err != nil {
		tb.Fatalf("failed to parse cert/key: %v", err)
	}

	return cert
}

// GenerateTestCA returns a self-signed CA certificate.
func GenerateTestCA(tb testing.TB) tls.Certificate {
	return generateTestCertificate(tb, func(tb testing.TB) *x509.Certificate {
		return &x509.Certificate{
			SerialNumber:          big.NewInt(1),
			Subject:               pkix.Name{CommonName: tb.Name()},
			NotBefore:             time.Now(),
			NotAfter:              time.Now().Add(24 * time.Hour),
			IsCA:                  true,
			KeyUsage:              x509.KeyUsageCertSign | x509.KeyUsageCRLSign,
			BasicConstraintsValid: true,
		}
	})
}

// GenerateTestCertificate returns a key and certificate used for testing.
func GenerateTestCertificate(tb testing.TB,
	opts ...CertificateOption) tls.Certificate {
	return generateTestCertificate(tb, func(tb testing.TB) *x509.Certificate {
		return &x509.Certificate{
			SerialNumber: big.NewInt(1),
			Subject:      pkix.Name{CommonName: tb.Name()},
			NotBefore:    time.Now(),
			NotAfter:     time.Now().Add(24 * time.Hour),
			KeyUsage:     x509.KeyUsageKeyEncipherment | x509.KeyUsageDigitalSignature,
			ExtKeyUsage: []x509.ExtKeyUsage{
				x509.ExtKeyUsageClientAuth,
				x509.ExtKeyUsageServerAuth,
			},
		}
	}, opts...)
}
