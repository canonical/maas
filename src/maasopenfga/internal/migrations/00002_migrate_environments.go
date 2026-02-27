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

package migrations

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"strconv"

	sq "github.com/Masterminds/squirrel"
	"github.com/oklog/ulid/v2"
	"github.com/pressly/goose/v3"
)

const (
	administratorGroupName = "administrators"
	usersGroupName         = "users"
)

func init() {
	goose.AddMigrationContext(Up00002, Down00002)
}

// Create a new maas:0 -> parent -> pool:id for every pool in the database.
func createPools(ctx context.Context, tx *sql.Tx) error {
	builder := sq.StatementBuilder.PlaceholderFormat(sq.Dollar)

	selectStmt, selectArgs, err := builder.
		Select("id").
		From("maasserver_resourcepool").
		ToSql()
	if err != nil {
		return err
	}

	rows, err := tx.QueryContext(ctx, selectStmt, selectArgs...)
	if err != nil {
		return err
	}

	defer func() {
		if err := rows.Close(); err != nil {
			log.Printf("failed to close rows: %v", err)
		}
	}()

	var poolIDs []int64

	for rows.Next() {
		var poolID int64
		if err := rows.Scan(&poolID); err != nil {
			return err
		}

		poolIDs = append(poolIDs, poolID)
	}

	if err := rows.Err(); err != nil {
		return err
	}

	for _, poolID := range poolIDs {
		insertStmt, insertArgs, err := builder.
			Insert("openfga.tuple").
			Columns(
				"store",
				"_user",
				"user_type",
				"relation",
				"object_type",
				"object_id",
				"ulid",
				"inserted_at",
			).
			Values(
				storeID,
				"maas:0",
				"user",
				"parent",
				"pool",
				strconv.FormatInt(poolID, 10),
				ulid.Make().String(),
				sq.Expr("NOW()"),
			).
			ToSql()
		if err != nil {
			return err
		}

		if _, err := tx.ExecContext(ctx, insertStmt, insertArgs...); err != nil {
			return err
		}
	}

	return nil
}

// Create a new group with relations to the maas:0 object.
func createGroup(ctx context.Context, tx *sql.Tx, groupName string, relations *[]string) error {
	builder := sq.StatementBuilder.PlaceholderFormat(sq.Dollar)

	for _, relation := range *relations {
		userGroupStmt, userGroupArgs, err := builder.
			Insert("openfga.tuple").
			Columns(
				"store",
				"_user",
				"user_type",
				"relation",
				"object_type",
				"object_id",
				"ulid",
				"inserted_at",
			).
			Values(
				storeID,
				fmt.Sprintf("group:%s#member", groupName),
				"userset",
				relation,
				"maas",
				"0",
				ulid.Make().String(),
				sq.Expr("NOW()"),
			).
			ToSql()
		if err != nil {
			return err
		}

		if _, err := tx.ExecContext(ctx, userGroupStmt, userGroupArgs...); err != nil {
			return err
		}
	}

	return nil
}

// For every user in auth_users, add them to the users group. if is_superuser is true,
// also add them to the administrators group. If false, add them to the users group.
func addUsersToGroup(ctx context.Context, tx *sql.Tx) error {
	builder := sq.StatementBuilder.PlaceholderFormat(sq.Dollar)

	selectStmt, selectArgs, err := builder.
		Select("id", "is_superuser").
		From("auth_user").
		ToSql()
	if err != nil {
		return err
	}

	rows, err := tx.QueryContext(ctx, selectStmt, selectArgs...)
	if err != nil {
		return err
	}

	defer func() {
		if err := rows.Close(); err != nil {
			log.Printf("failed to close rows: %v", err)
		}
	}()

	type user struct {
		id          int64
		isSuperUser bool
	}

	var users []user

	for rows.Next() {
		var u user
		if err := rows.Scan(&u.id, &u.isSuperUser); err != nil {
			return err
		}

		users = append(users, u)
	}

	if err := rows.Err(); err != nil {
		return err
	}

	for _, u := range users {
		groupName := usersGroupName
		if u.isSuperUser {
			groupName = administratorGroupName
		}

		insertStmt, insertArgs, err := builder.
			Insert("openfga.tuple").
			Columns(
				"store",
				"_user",
				"user_type",
				"relation",
				"object_type",
				"object_id",
				"ulid",
				"inserted_at",
			).
			Values(
				storeID,
				fmt.Sprintf("user:%d", u.id),
				"user",
				"member",
				"group",
				groupName,
				ulid.Make().String(),
				sq.Expr("NOW()"),
			).
			ToSql()
		if err != nil {
			return err
		}

		if _, err := tx.ExecContext(ctx, insertStmt, insertArgs...); err != nil {
			return err
		}
	}

	return nil
}

func Up00002(ctx context.Context, tx *sql.Tx) error {
	if err := createPools(ctx, tx); err != nil {
		return fmt.Errorf("failed to create pools: %w", err)
	}

	relations := []string{"can_edit_machines", "can_edit_global_entities", "can_edit_controllers", "can_edit_identities",
		"can_edit_configurations", "can_edit_notifications", "can_edit_boot_entities", "can_edit_license_keys",
		"can_view_devices",
		"can_view_ipaddresses"}
	if err := createGroup(ctx, tx, administratorGroupName, &relations); err != nil {
		return fmt.Errorf("failed to create administrators group: %w", err)
	}

	relations = []string{"can_deploy_machines", "can_view_deployable_machines", "can_view_global_entities"}
	if err := createGroup(ctx, tx, usersGroupName, &relations); err != nil {
		return fmt.Errorf("failed to create users group: %w", err)
	}

	if err := addUsersToGroup(ctx, tx); err != nil {
		return fmt.Errorf("failed to add users to groups: %w", err)
	}

	return nil
}

func Down00002(ctx context.Context, tx *sql.Tx) error {
	return fmt.Errorf("downgrade not supported")
}
