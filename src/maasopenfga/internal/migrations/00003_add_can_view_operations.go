package migrations

import (
	"context"
	"database/sql"
	"fmt"

	sq "github.com/Masterminds/squirrel"
	"github.com/oklog/ulid/v2"
	parser "github.com/openfga/language/pkg/go/transformer"
	"github.com/pressly/goose/v3"
	"google.golang.org/protobuf/proto"
)

func init() {
	goose.AddMigrationContext(Up00003, Down00003)
}

func updateAuthorizationModel(ctx context.Context, tx *sql.Tx) error {
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

    define can_view_dnsrecords: [group#member]

    define can_edit_operations: [group#member]
    define can_view_operations: [group#member] or can_edit_operations

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

	model.Id = storeID

	pbdata, err := proto.Marshal(model)
	if err != nil {
		return err
	}

	builder := sq.StatementBuilder.PlaceholderFormat(sq.Dollar)

	deleteStmt, deleteArgs, err := builder.
		Delete("openfga.authorization_model").
		Where(sq.Eq{"store": storeID}).
		ToSql()
	if err != nil {
		return err
	}

	if _, err := tx.ExecContext(ctx, deleteStmt, deleteArgs...); err != nil {
		return err
	}

	insertStmt, insertArgs, err := builder.
		Insert("openfga.authorization_model").
		Columns("store", "authorization_model_id", "schema_version", "type", "type_definition", "serialized_protobuf").
		Values(storeID, model.GetId(), model.GetSchemaVersion(), "", nil, pbdata).
		ToSql()
	if err != nil {
		return err
	}

	_, err = tx.ExecContext(ctx, insertStmt, insertArgs...)
	return err
}

func addAdminOperationsTuples(ctx context.Context, tx *sql.Tx) error {
	groupID, err := getGroupID(ctx, tx, administratorGroupName)
	if err != nil {
		return fmt.Errorf("failed to get administrator group id: %w", err)
	}

	builder := sq.StatementBuilder.PlaceholderFormat(sq.Dollar)
	relations := []string{"can_edit_operations", "can_view_operations"}

	for _, relation := range relations {
		insertStmt, insertArgs, err := builder.
			Insert("openfga.tuple").
			Columns("store", "_user", "user_type", "relation", "object_type", "object_id", "ulid", "inserted_at").
			Values(
				storeID,
				fmt.Sprintf("group:%d#member", groupID),
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

		if _, err := tx.ExecContext(ctx, insertStmt, insertArgs...); err != nil {
			return fmt.Errorf("failed to insert %s tuple: %w", relation, err)
		}
	}

	return nil
}

func Up00003(ctx context.Context, tx *sql.Tx) error {
	if err := updateAuthorizationModel(ctx, tx); err != nil {
		return fmt.Errorf("failed to update authorization model: %w", err)
	}

	if err := addAdminOperationsTuples(ctx, tx); err != nil {
		return err
	}

	return nil
}

func Down00003(ctx context.Context, tx *sql.Tx) error {
	return fmt.Errorf("downgrade not supported")
}
