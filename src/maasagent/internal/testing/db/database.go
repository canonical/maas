// Copyright (c) 2025 Canonical Ltd
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

package db

import (
	"context"
	"database/sql"
	"os"
	"testing"

	"maas.io/core/src/maasagent/internal/cluster"
)

func SetupSchema(ctx context.Context, tx *sql.Tx) error {
	return cluster.SchemaAppendDHCP(ctx, tx)
}

func WithTestDatabase(t testing.TB) (*sql.DB, error) {
	f, err := os.CreateTemp(t.TempDir(), t.Name()+".db")
	if err != nil {
		return nil, err
	}

	if err = f.Close(); err != nil {
		return nil, err
	}

	db, err := sql.Open("sqlite3", f.Name())
	if err != nil {
		return nil, err
	}

	return db, nil
}
