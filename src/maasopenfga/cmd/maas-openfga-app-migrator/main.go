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
	"context"
	"database/sql"
	"fmt"
	"os"
	"time"

	"github.com/cenkalti/backoff/v4"
	_ "github.com/jackc/pgx/v5/stdlib"
	"github.com/pressly/goose/v3"

	_ "maas.io/core/src/maasopenfga/internal/migrations"
)

const (
	appMigrationsTable = "openfga.goose_app_db_version"
	migrationsPath     = "."
)

// Note that this migrator should manage the openfga schema manually because we might need to access also the MAAS tables in
// the default schema. Do not pass the search_path in the datastore-uri like we do in the maas-openfga-migrator.
// Tested in the integration tests of the dbupgrade django command.
func main() {
	if len(os.Args) != 2 {
		fmt.Fprintf(os.Stderr, "usage: %s <datastore-uri>\n", os.Args[0])
		os.Exit(1)
	}

	uri := os.Args[1]

	goose.SetLogger(goose.NopLogger())
	goose.SetTableName(appMigrationsTable)

	db, err := goose.OpenDBWithDriver("pgx", uri)
	if err != nil {
		panic(fmt.Errorf("failed to open database: %w", err))
	}
	defer func(db *sql.DB) {
		errr := db.Close()
		if errr != nil {
			fmt.Fprintf(os.Stderr, "failed to close database connection: %v\n", err)
		}
	}(db)

	policy := backoff.NewExponentialBackOff()
	policy.MaxElapsedTime = time.Second * 30

	if err := backoff.Retry(func() error {
		return db.PingContext(context.Background())
	}, policy); err != nil {
		panic(fmt.Errorf("failed to initialize database connection: %w", err))
	}

	if err := goose.Up(db, migrationsPath); err != nil {
		panic(fmt.Errorf("failed to run migrations: %w", err))
	}
}
