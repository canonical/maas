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

package cluster

import (
	"context"
	"database/sql"

	"github.com/canonical/lxd/lxd/db/schema"
)

const (
	dropPreviousDHCPSchema = `
DROP TABLE IF EXISTS vlan;
DROP TABLE IF EXISTS subnet;
DROP TABLE IF EXISTS ip_range;
DROP TABLE IF EXISTS host_reservation;
DROP TABLE IF EXISTS lease;
DROP TABLE IF EXISTS expiration;
DROP TABLE IF EXISTS dhcp_option;
`
	vlanTable = `
CREATE TABLE vlan (
	id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	vid INTEGER NOT NULL,
	relay_vlan_id INTEGER,
	FOREIGN KEY(relay_vlan_id) REFERENCES vlan(id)
);
`
	// interfaceTable does not mirror the interface table found in postgres,
	// instead this is metadata around the agent's interface(s) to determine the
	// exact associated VLAN. It uses the system's interface index and hostname of the agent to associate
	// with the actual host's interface
	interfaceTable = `
CREATE TABLE interface (
	id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	hostname TEXT NOT NULL,
	idx INTEGER NOT NULL,
	vlan_id INTEGER NOT NULL,
	FOREIGN KEY(vlan_id) REFERENCES vlan(id),
	UNIQUE(hostname, idx)
);
`

	subnetTable = `
CREATE TABLE subnet (
	id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	cidr TEXT NOT NULL,
	address_family INTEGER NOT NULL,
	vlan_id INTEGER NOT NULL,
	FOREIGN KEY(vlan_id) REFERENCES vlan(id),
	UNIQUE(cidr)
);
`
	ipRangeTable = `
CREATE TABLE ip_range (
	id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	start_ip TEXT NOT NULL,
	end_ip TEXT NOT NULL,
	size INTEGER NOT NULL,
	fully_allocated BOOL NOT NULL,
	dynamic BOOL NOT NULL,
	subnet_id INTEGER NOT NULL,
	FOREIGN KEY(subnet_id) REFERENCES subnet(id),
	UNIQUE(start_ip),
	UNIQUE(end_ip)
);
`
	hostReservationTable = `
CREATE TABLE host_reservation (
	id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	ip_address TEXT NOT NULL,
	mac_address TEXT,
	range_id INTEGER NOT NULL,
	FOREIGN KEY(range_id) REFERENCES ip_range(id),
	UNIQUE(ip_address)
);
`
	leaseTable = `
CREATE TABLE lease (
	id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	ip TEXT NOT NULL,
	mac_address TEXT,
	duid TEXT,
	created_at INTEGER NOT NULL,
	updated_at INTEGER NOT NULL,
	lifetime INTEGER NOT NULL, -- in milliseconds for easy computation with unix epochs
	state INTEGER NOT NULL, -- offered or acked / advertised or replied
	needs_sync BOOL NOT NULL, -- true when the lease has yet to be sent to the region
	range_id INTEGER NOT NULL,
	FOREIGN KEY(range_id) REFERENCES ip_range(id),
	UNIQUE(ip)
);
`
	expirationTable = `
CREATE TABLE expiration (
	id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	ip TEXT NOT NULL,
	mac_address TEXT,
	duid TEXT,
	created_at INTEGER NOT NULL,
	UNIQUE(ip, mac_address)
);
`
	dhcpOptionTable = `
CREATE TABLE dhcp_option (
	id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
	label TEXT,
	number INTEGER NOT NULL,
	value TEXT NOT NULL,
	vlan_id INTEGER,
	subnet_id INTEGER,
	range_id INTEGER,
	host_reservation_id INTEGER,
	FOREIGN KEY(vlan_id) REFERENCES vlan(id),
	FOREIGN KEY(subnet_id) REFERENCES subnet(id),
	FOREIGN KEY(range_id) REFERENCES ip_range(id),
	FOREIGN KEY(host_reservation_id) REFERENCES host_reservation(id)
);
`
)

var (
	orderedDHCPStmts = []string{
		dropPreviousDHCPSchema,
		vlanTable,
		interfaceTable,
		subnetTable,
		ipRangeTable,
		hostReservationTable,
		leaseTable,
		expirationTable,
		dhcpOptionTable,
	}

	schemaExtensions = []schema.Update{
		SchemaAppendDHCP,
	}
)

func SchemaAppendDHCP(ctx context.Context, tx *sql.Tx) error {
	for _, stmt := range orderedDHCPStmts {
		_, err := tx.ExecContext(ctx, stmt)
		if err != nil {
			return err
		}
	}

	return nil
}
