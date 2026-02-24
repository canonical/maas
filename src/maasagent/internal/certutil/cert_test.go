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
	"crypto/x509"
	"encoding/pem"
	"os"
	"testing"

	"github.com/spf13/afero"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
	certtest "maas.io/core/src/maasagent/internal/testing/cert"
)

func TestWriteCertificatePEM(t *testing.T) {
	cert := certtest.GenerateTestCertificate(t)
	certPEMBlock := &pem.Block{Type: "CERTIFICATE", Bytes: cert.Certificate[0]}
	certBytes := pem.EncodeToMemory(certPEMBlock)

	notCertPEMBlock := &pem.Block{Type: "BADCERTIFICATE", Bytes: []byte{}}
	notCertBytes := pem.EncodeToMemory(notCertPEMBlock)

	badCertPEMBlock := &pem.Block{Type: "CERTIFICATE", Bytes: []byte{}}
	badCertBytes := pem.EncodeToMemory(badCertPEMBlock)

	testcases := map[string]struct {
		in  []byte
		out []byte
		err string
	}{
		"valid": {
			in:  certBytes,
			out: certBytes,
		},
		"missing CERTIFICATE block": {
			in:  notCertBytes,
			err: "unexpected PEM block type: BADCERTIFICATE",
		},
		"bad certificate": {
			in:  badCertBytes,
			err: "invalid certificate",
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			fs := afero.NewMemMapFs()

			err := WriteCertificatePEM(fs, "/cert.pem", tc.in)
			if tc.err != "" {
				require.ErrorContains(t, err, tc.err)

				_, err := afero.ReadFile(fs, "/cert.pem")
				require.ErrorIs(t, err, os.ErrNotExist)
			} else {
				require.NoError(t, err)

				got, err := afero.ReadFile(fs, "/cert.pem")
				require.NoError(t, err)

				require.Equal(t, tc.out, got)
			}
		})
	}
}

func TestWriteCACertificatePEM(t *testing.T) {
	ca1 := certtest.GenerateTestCA(t)
	ca1PEM := ca1.Certificate[0]
	ca1PEMBlock := &pem.Block{Type: "CERTIFICATE", Bytes: ca1PEM}
	ca1Bytes := pem.EncodeToMemory(ca1PEMBlock)

	ca2 := certtest.GenerateTestCA(t)
	ca2PEM := ca2.Certificate[0]
	ca2PEMBlock := &pem.Block{Type: "CERTIFICATE", Bytes: ca2PEM}
	ca2Bytes := pem.EncodeToMemory(ca2PEMBlock)

	caNotCertPEMBlock := &pem.Block{Type: "BADCERTIFICATE", Bytes: []byte{}}
	caNotCertBytes := pem.EncodeToMemory(caNotCertPEMBlock)

	caBadPEMBlock := &pem.Block{Type: "CERTIFICATE", Bytes: []byte{}}
	caBadBytes := pem.EncodeToMemory(caBadPEMBlock)

	testcases := map[string]struct {
		in  []byte
		out []byte
		err string
	}{
		"all valid": {
			in:  append(append([]byte(nil), ca1Bytes...), ca2Bytes...),
			out: append(append([]byte(nil), ca1Bytes...), ca2Bytes...),
		},
		"first valid, second non-cert": {
			in:  append(append([]byte(nil), ca1Bytes...), caNotCertBytes...),
			err: "unexpected PEM block type",
		},
		"first valid, second bad": {
			in:  append(append([]byte(nil), ca1Bytes...), caBadBytes...),
			err: "invalid certificate in CA",
		},
		"first non-cert, second valid": {
			in:  append(append([]byte(nil), caNotCertBytes...), ca2Bytes...),
			err: "unexpected PEM block type",
		},
		"first bad, second valid": {
			in:  append(append([]byte(nil), caBadBytes...), ca2Bytes...),
			err: "invalid certificate in CA",
		},
		"first non-cert, second bad": {
			in:  append(append([]byte(nil), caNotCertBytes...), caBadBytes...),
			err: "unexpected PEM block type",
		},
		"single valid": {
			in:  append([]byte(nil), ca1Bytes...),
			out: append([]byte(nil), ca1Bytes...),
		},
		"single non-cert": {
			in:  append([]byte(nil), caNotCertBytes...),
			err: "unexpected PEM block type",
		},
		"single bad": {
			in:  append([]byte(nil), caBadBytes...),
			err: "invalid certificate in CA",
		},
		"empty": {
			in:  []byte{},
			err: "did not find any CERTIFICATE blocks",
		},
	}

	for name, tc := range testcases {
		t.Run(name, func(t *testing.T) {
			t.Parallel()

			fs := afero.NewMemMapFs()

			err := WriteCertificatePEM(fs, "/ca.pem", tc.in)
			if tc.err != "" {
				require.ErrorContains(t, err, tc.err)

				_, err := afero.ReadFile(fs, "/ca.pem")
				require.ErrorIs(t, err, os.ErrNotExist)
			} else {
				require.NoError(t, err)

				got, err := afero.ReadFile(fs, "/ca.pem")
				require.NoError(t, err)

				require.Equal(t, tc.out, got)
			}
		})
	}
}

func TestWritePrivateKey(t *testing.T) {
	cert := certtest.GenerateTestCertificate(t)

	fs := afero.NewMemMapFs()
	err := WritePrivateKey(fs, "tls.key", cert.PrivateKey)

	require.NoError(t, err)

	data, err := afero.ReadFile(fs, "tls.key")
	require.NoError(t, err)

	block, _ := pem.Decode(data)
	require.Equal(t, "PRIVATE KEY", block.Type)
	key, err := x509.ParsePKCS8PrivateKey(block.Bytes)
	require.NoError(t, err)

	want, err := x509.MarshalPKCS8PrivateKey(cert.PrivateKey)
	require.NoError(t, err)

	got, err := x509.MarshalPKCS8PrivateKey(key)
	require.NoError(t, err)

	assert.Equal(t, want, got)
}

func TestCreateCSR(t *testing.T) {
	cert := certtest.GenerateTestCertificate(t)

	csrPEM, err := CreateCSR(t.Name(), cert.PrivateKey)
	require.NoError(t, err)

	block, _ := pem.Decode(csrPEM)
	require.Equal(t, "CERTIFICATE REQUEST", block.Type)

	csr, err := x509.ParseCertificateRequest(block.Bytes)
	require.NoError(t, err)

	assert.Equal(t, t.Name(), csr.Subject.CommonName)
}

func TestWriteCertificate(t *testing.T) {
	expected := certtest.GenerateTestCertificate(t)
	certFile := "cert.pem"

	fs := afero.NewMemMapFs()

	require.NoError(t, WriteCertificate(fs, certFile, expected))

	data, err := afero.ReadFile(fs, certFile)
	require.NoError(t, err)

	block, _ := pem.Decode(data)
	require.NotNil(t, block, "failed to decode PEM")

	got, err := x509.ParseCertificate(block.Bytes)
	require.NoError(t, err)
	require.Equal(t, expected.Leaf, got)
}

func TestLoadX509KeyPair(t *testing.T) {
	expected := certtest.GenerateTestCertificate(t)
	certFile := "cert.pem"
	keyFile := "cert.key"

	fs := afero.NewMemMapFs()

	require.NoError(t, WriteCertificate(fs, certFile, expected))
	require.NoError(t, WritePrivateKey(fs, keyFile, expected.PrivateKey))

	got, err := LoadX509KeyPair(fs, certFile, keyFile)
	require.NoError(t, err)

	require.NoError(t, err)
	require.Equal(t, expected, got)
}

func TestLoadCAPool(t *testing.T) {
	ca := certtest.GenerateTestCA(t)
	caFile := "ca.pem"

	fs := afero.NewMemMapFs()

	require.NoError(t, WriteCertificate(fs, caFile, ca))

	leaf, err := x509.ParseCertificate(ca.Certificate[0])
	require.NoError(t, err)

	expected, err := x509.SystemCertPool()
	require.NoError(t, err)
	expected.AddCert(leaf)

	require.NoError(t, err)

	got, err := LoadCAPool(fs, caFile)
	require.NoError(t, err)
	require.True(t, expected.Equal(got))
}
