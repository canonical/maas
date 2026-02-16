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
	"fmt"
	"os"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"

	"github.com/openfga/openfga/pkg/logger"
	"github.com/openfga/openfga/pkg/storage/migrate"
)

// Tested in the integration tests of the dbupgrade django command.
func main() {
	if len(os.Args) != 2 {
		fmt.Fprintf(os.Stderr, "usage: %s <datastore-uri>\n", os.Args[0])
		os.Exit(1)
	}

	uri := os.Args[1]

	log := logger.MustNewLogger("text", "info", "Unix")

	cfg := migrate.MigrationConfig{
		Engine:        "postgres",
		URI:           uri,
		TargetVersion: 0, // migrate to latest
		Timeout:       time.Second * 30,
		Verbose:       true,
		Logger:        log,
	}

	if err := migrate.RunMigrations(cfg); err != nil {
		panic(err)
	}
}
