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

package daemon

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/tls"
	"errors"
	"fmt"
	"os"

	"github.com/google/uuid"
	"github.com/spf13/afero"
	"maas.io/core/src/maasagent/internal/certutil"
)

const defaultKeySize = 4096

type generateIdentityConfig struct {
	keySize int
}

type generateIdentityOption func(*generateIdentityConfig)

func withKeySize(size int) generateIdentityOption {
	return func(c *generateIdentityConfig) {
		c.keySize = size
	}
}

// identity represents the raw components before enrollment.
type identity struct {
	ID          string
	Certificate tls.Certificate
	CSR         []byte
}

// generateIdentity creates a new identity.
// If a private key and cert already exist on disk, it loads and validates them,
// extracts the Common Name, and returns the existing identity.
// If the keypair doesn't exist, it generates a new private key and a CSR with
// a UUIDv6 subject, writes the key and CSR to disk, and returns a new identity.
func generateIdentity(fs afero.Fs, certFile, keyFile string,
	opts ...generateIdentityOption) (*identity, error) {
	cfg := generateIdentityConfig{keySize: defaultKeySize}
	for _, o := range opts {
		o(&cfg)
	}

	certExists, err := fileExists(fs, certFile)
	if err != nil {
		return nil, fmt.Errorf("stat cert file: %w", err)
	}

	keyExists, err := fileExists(fs, keyFile)
	if err != nil {
		return nil, fmt.Errorf("stat key file: %w", err)
	}

	if keyExists && certExists {
		cert, err := certutil.LoadX509KeyPair(fs, certFile, keyFile)
		if err != nil {
			return nil, fmt.Errorf("load certificate: %w", err)
		}

		return &identity{
			ID:          cert.Leaf.Subject.CommonName,
			Certificate: cert,
		}, nil
	}

	id, err := uuid.NewV6()
	if err != nil {
		return nil, fmt.Errorf("failed to generate uuid: %w", err)
	}

	key, err := rsa.GenerateKey(rand.Reader, cfg.keySize)
	if err != nil {
		return nil, fmt.Errorf("failed to generate private key: %w", err)
	}

	csr, err := certutil.CreateCSR(id.String(), key)
	if err != nil {
		return nil, fmt.Errorf("create CSR: %w", err)
	}

	if err := certutil.WritePrivateKey(fs, keyFile, key); err != nil {
		return nil, fmt.Errorf("write private key: %w", err)
	}

	return &identity{
		ID:          id.String(),
		Certificate: tls.Certificate{PrivateKey: key},
		CSR:         csr,
	}, nil
}

func fileExists(fs afero.Fs, path string) (bool, error) {
	_, err := fs.Stat(path)
	if err == nil {
		return true, nil
	}

	if errors.Is(err, os.ErrNotExist) {
		return false, nil
	}

	return false, err
}
