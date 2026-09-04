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

package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestReadOpenFGAConfig(t *testing.T) {
	tests := []struct {
		name    string
		content string
		want    openfgaConfig
		wantErr bool
	}{
		{
			name: "valid config",
			content: `
database_uri: postgres://maas:secret@/maasdb?host=%2Fvar%2Frun%2Fpostgresql&search_path=openfga
openfga_max_open_conns: 7
openfga_max_idle_conns: 2
`,
			want: openfgaConfig{
				DatabaseURI:         "postgres://maas:secret@/maasdb?host=%2Fvar%2Frun%2Fpostgresql&search_path=openfga",
				OpenFGAMaxOpenConns: 7,
				OpenFGAMaxIdleConns: 2,
			},
		},
		{
			name: "default connection limits",
			content: `
database_uri: postgres://maas@localhost:5432/maasdb?search_path=openfga
`,
			want: openfgaConfig{
				DatabaseURI:         "postgres://maas@localhost:5432/maasdb?search_path=openfga",
				OpenFGAMaxOpenConns: defaultMaxOpenConns,
				OpenFGAMaxIdleConns: defaultMaxIdleConns,
			},
		},
		{
			name:    "missing database_uri",
			content: "openfga_max_open_conns: 3\n",
			wantErr: true,
		},
		{
			name:    "invalid yaml",
			content: ": bad yaml\n",
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			configPath := filepath.Join(t.TempDir(), "openfga.yaml")
			if err := os.WriteFile(configPath, []byte(tt.content), 0o600); err != nil {
				t.Fatalf("failed to write test config: %v", err)
			}

			t.Setenv("MAAS_OPENFGA_CONFIG", configPath)

			got, err := readOpenFGAConfig()

			if (err != nil) != tt.wantErr {
				t.Fatalf("readOpenFGAConfig() error = %v, wantErr %v", err, tt.wantErr)
			}

			if err != nil {
				return
			}

			if got != tt.want {
				t.Errorf("readOpenFGAConfig() = %+v, want %+v", got, tt.want)
			}
		})
	}
}

func TestReadOpenFGAConfigMissingEnv(t *testing.T) {
	t.Setenv("MAAS_OPENFGA_CONFIG", "")

	if _, err := readOpenFGAConfig(); err == nil {
		t.Fatal("expected error when MAAS_OPENFGA_CONFIG is not set")
	}
}
