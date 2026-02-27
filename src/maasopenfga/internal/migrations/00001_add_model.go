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

	sq "github.com/Masterminds/squirrel"
	parser "github.com/openfga/language/pkg/go/transformer"
	"github.com/pressly/goose/v3"
	"google.golang.org/protobuf/proto"
)

const (
	storeID = "00000000000000000000000000"
)

func init() {
	goose.AddMigrationContext(Up00001, Down00001)
}

func createStore(ctx context.Context, tx *sql.Tx) error {
	stmt, args, err := sq.StatementBuilder.PlaceholderFormat(sq.Dollar).
		Insert("openfga.store").
		Columns("id", "name", "created_at", "updated_at").
		Values(storeID, "MAAS", sq.Expr("NOW()"), sq.Expr("NOW()")).
		Suffix("returning id, name, created_at, updated_at").ToSql()
	if err != nil {
		return err
	}

	_, err = tx.ExecContext(
		ctx,
		stmt,
		args...,
	)

	return err
}

func createAuthorizationModel(ctx context.Context, tx *sql.Tx) error {
	modelDSL := `
model 
  schema 1.1

type user

type group
  relations
    define member: [user]

type maas
  relations
    define can_edit_machines: [group#member]
    define can_deploy_machines: [group#member] or can_edit_machines
    define can_view_machines: [group#member] or can_edit_machines
    define can_view_available_machines: [group#member] or can_edit_machines or can_view_machines
    
    define can_edit_global_entities: [group#member] 
    define can_view_global_entities: [group#member] or can_edit_global_entities
    
    define can_edit_controllers: [group#member]
    define can_view_controllers: [group#member] or can_edit_controllers

    define can_edit_identities: [group#member]
    define can_view_identities: [group#member] or can_edit_identities

    define can_edit_configurations: [group#member]
    define can_view_configurations: [group#member] or can_edit_configurations

    define can_edit_notifications: [group#member]
    define can_view_notifications: [group#member] or can_edit_notifications

    define can_edit_boot_entities: [group#member]
    define can_view_boot_entities: [group#member] or can_edit_boot_entities

    define can_edit_license_keys: [group#member]
    define can_view_license_keys: [group#member] or can_edit_license_keys

    define can_view_devices: [group#member]

    define can_view_ipaddresses: [group#member]

type pool
  relations
    define parent: [maas]

    define can_edit_machines: [group#member] or can_edit_machines from parent
    define can_deploy_machines: [group#member] or can_edit_machines or can_deploy_machines from parent
    define can_view_machines: [group#member] or can_edit_machines or can_view_machines from parent
    define can_view_available_machines: [group#member] or can_edit_machines or can_view_machines or can_view_available_machines from parent
`

	model, err := parser.TransformDSLToProto(modelDSL)
	if err != nil {
		return err
	}

	// The ID in the protobuf and in the database must be set and match, otherwise openfga will not work properly with this model.
	model.Id = storeID

	pbdata, err := proto.Marshal(model)
	if err != nil {
		return err
	}

	stmt, args, err := sq.StatementBuilder.PlaceholderFormat(sq.Dollar).
		Insert("openfga.authorization_model").
		Columns("store", "authorization_model_id", "schema_version", "type", "type_definition", "serialized_protobuf").
		Values(storeID, model.GetId(), model.GetSchemaVersion(), "", nil, pbdata).
		ToSql()
	if err != nil {
		return err
	}

	_, err = tx.ExecContext(
		ctx,
		stmt,
		args...,
	)

	return err
}

func Up00001(ctx context.Context, tx *sql.Tx) error {
	if err := createStore(ctx, tx); err != nil {
		return fmt.Errorf("failed to create store: %w", err)
	}

	if err := createAuthorizationModel(ctx, tx); err != nil {
		return fmt.Errorf("failed to create authorization model: %w", err)
	}

	return nil
}

func Down00001(ctx context.Context, tx *sql.Tx) error {
	return fmt.Errorf("downgrade not supported")
}
