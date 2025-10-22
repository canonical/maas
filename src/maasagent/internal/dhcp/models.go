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

package dhcp

import (
	"context"
	"database/sql"
	"errors"
	"net"
)

type LeaseState int

const (
	LeaseStateOffered LeaseState = iota
	LeaseStateAcked
)

const (
	getVlanStmt            = "SELECT * FROM vlan WHERE id = $1;"
	getSubnetStmt          = "SELECT * FROM subnet WHERE id = $1;"
	getIPRangeStmt         = "SELECT * FROM ip_range WHERE id = $1;"
	getHostReservationStmt = "SELECT * FROM host_reservation WHERE id = $1"
	getLeaseStmt           = "SELECT * FROM lease WHERE id = $1;"
	getExpirationStmt      = "SELECT * FROM expiration WHERE id = $1;"

	loadVLANOptionsStmt            = "SELECT number, value FROM dhcp_option WHERE vlan_id = $1;"
	loadSubnetOptionsStmt          = "SELECT number, value FROM dhcp_option WHERE subnet_id = $1;"
	loadIPRangeOptionsStmt         = "SELECT number, value FROM dhcp_option WHERE range_id = $1;"
	loadHostReservationOptionsStmt = "SELECT number, value FROM dhcp_option WHERE host_reservation_id = $1;"

	insertOrReplaceVLANStmt        = "INSERT OR REPLACE INTO vlan (id, vid) VALUES ($1, $2);"
	insertOrReplaceRelayedVLANStmt = "INSERT OR REPLACE INTO vlan (id, vid, relay_vlan_id) VALUES ($1, $2, $3);"
	insertOrReplaceSubnetStmt      = "INSERT OR REPLACE INTO subnet (id, cidr, address_family, vlan_id) VALUES ($1, $2, $3, $4);"
	insertOrReplaceIPRangeStmt     = `
	INSERT OR REPLACE INTO ip_range (
		id, start_ip, end_ip, size, fully_allocated, dynamic, subnet_id
	) VALUES ($1, $2, $3, $4, $5, $6, $7);
	`
	insertOrReplaceHostReservationStmt = `
	INSERT OR REPLACE INTO host_reservation (
		id, ip_address, mac_address, range_id, subnet_id
	) VALUES (NULL, $1, $2, $3, $4);
	`

	insertVLANOptionStmt            = "INSERT OR REPLACE INTO dhcp_option (id, label, number, value, vlan_id) VALUES (NULL, $1, $2, $3, $4);"
	insertSubnetOptionStmt          = "INSERT OR REPLACE INTO dhcp_option (id, label, number, value, subnet_id) VALUES (NULL, $1, $2, $3, $4);"
	insertHostReservationOptionStmt = "INSERT OR REPLACE INTO dhcp_option (id, label, number, value, host_reservation_id) VALUES (NULL, $1, $2, $3, $4);"
)

// loadOptions loads the options for the given sql statement and id.
// Options are not immediately joined in fetching each object because there are more
// scenarios where we need the object without the options, and allowing us to load options
// from an object already fetched from the DB at a later point if all conditions are met
// that do require options.
func loadOptions(ctx context.Context, tx *sql.Tx, stmt string, id int) (map[uint16]string, error) {
	options := make(map[uint16]string)

	results, err := tx.QueryContext(ctx, stmt, id)
	if err != nil {
		return nil, err
	}

	defer results.Close() //nolint:errcheck // ok to ignore this error

	for results.Next() {
		var (
			number uint16
			value  string
		)

		err = results.Scan(&number, &value)
		if err != nil {
			return nil, err
		}

		options[number] = value
	}

	return options, nil
}

type Vlan struct {
	Options       map[uint16]string
	ID            int
	RelayedVlanID int
	VID           int16
}

func (v *Vlan) ScanRow(row *sql.Row) error {
	var relayedVlanID *int

	err := row.Scan(
		&v.ID,
		&v.VID,
		&relayedVlanID,
	)
	if err != nil {
		return err
	}

	if relayedVlanID != nil {
		v.RelayedVlanID = *relayedVlanID
	}

	return nil
}

func (v *Vlan) LoadOptions(ctx context.Context, tx *sql.Tx) error {
	options, err := loadOptions(ctx, tx, loadVLANOptionsStmt, v.ID)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return err
	}

	v.Options = options

	return nil
}

func (v *Vlan) InsertOrReplace(ctx context.Context, tx *sql.Tx) error {
	if v.RelayedVlanID > 0 {
		_, err := tx.ExecContext(ctx, insertOrReplaceRelayedVLANStmt, v.ID, v.VID, v.RelayedVlanID)
		return err
	}

	_, err := tx.ExecContext(ctx, insertOrReplaceVLANStmt, v.ID, v.VID)

	return err
}

func (v *Vlan) InsertOption(ctx context.Context, tx *sql.Tx, label string, number int, value string) error {
	_, err := tx.ExecContext(
		ctx,
		insertVLANOptionStmt,
		label,
		number,
		value,
		v.ID,
	)

	return err
}

type Interface struct {
	Hostname string
	ID       int
	Index    int
	VlanID   int
}

func (i *Interface) ScanRow(row *sql.Row) error {
	return row.Scan(
		&i.ID,
		&i.Hostname,
		&i.Index,
		&i.VlanID,
	)
}

type Subnet struct {
	CIDR          *net.IPNet
	Options       map[uint16]string
	ID            int
	AddressFamily int
	VlanID        int
}

func (s *Subnet) ScanRow(row *sql.Row) error {
	var cidrStr string

	err := row.Scan(
		&s.ID,
		&cidrStr,
		&s.AddressFamily,
		&s.VlanID,
	)
	if err != nil {
		return err
	}

	_, cidr, err := net.ParseCIDR(cidrStr)
	if err != nil {
		return err
	}

	s.CIDR = cidr

	return nil
}

func (s *Subnet) LoadOptions(ctx context.Context, tx *sql.Tx) error {
	options, err := loadOptions(ctx, tx, loadSubnetOptionsStmt, s.ID)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return err
	}

	s.Options = options

	return nil
}

func (s *Subnet) InsertOrReplace(ctx context.Context, tx *sql.Tx) error {
	_, err := tx.ExecContext(ctx, insertOrReplaceSubnetStmt, s.ID, s.CIDR.String(), s.AddressFamily, s.VlanID)
	return err
}

func (s *Subnet) InsertOption(ctx context.Context, tx *sql.Tx, label string, number int, value string) error {
	_, err := tx.ExecContext(ctx, insertSubnetOptionStmt, label, number, value, s.ID)
	return err
}

type IPRange struct {
	Options        map[uint16]string
	StartIP        net.IP
	EndIP          net.IP
	ID             int
	Size           int
	SubnetID       int
	FullyAllocated bool
	Dynamic        bool
}

func (i *IPRange) ScanRow(row *sql.Row) error {
	var startIPStr, endIPStr string

	err := row.Scan(
		&i.ID,
		&startIPStr,
		&endIPStr,
		&i.Size,
		&i.FullyAllocated,
		&i.Dynamic,
		&i.SubnetID,
	)
	if err != nil {
		return err
	}

	i.StartIP = net.ParseIP(startIPStr)
	i.EndIP = net.ParseIP(endIPStr)

	return nil
}

func (i *IPRange) LoadOptions(ctx context.Context, tx *sql.Tx) error {
	options, err := loadOptions(ctx, tx, loadIPRangeOptionsStmt, i.ID)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return err
	}

	i.Options = options

	return nil
}

func (i *IPRange) InsertOrReplace(ctx context.Context, tx *sql.Tx) error {
	_, err := tx.ExecContext(
		ctx,
		insertOrReplaceIPRangeStmt,
		i.ID,
		i.StartIP.String(),
		i.EndIP.String(),
		i.Size,
		i.FullyAllocated,
		i.Dynamic,
		i.SubnetID,
	)

	return err
}

type HostReservation struct {
	Options    map[uint16]string
	DUID       string
	IPAddress  net.IP
	MACAddress net.HardwareAddr
	ID         int
	RangeID    int
	SubnetID   int
}

func (h *HostReservation) ScanRow(row *sql.Row) error {
	var (
		ipStr, macStr string
		duid          *string
		rangeID       *int
	)

	err := row.Scan(
		&h.ID,
		&ipStr,
		&macStr,
		&duid,
		&rangeID,
		&h.SubnetID,
	)
	if err != nil {
		return err
	}

	h.IPAddress = net.ParseIP(ipStr)
	h.MACAddress, err = net.ParseMAC(macStr)

	if duid != nil {
		h.DUID = *duid
	}

	if rangeID != nil {
		h.RangeID = *rangeID
	}

	return err
}

// LoadOptions for HostReservation has a priority of most specific to most broad,
// i.e vlan -> subnet -> iprange -> host reservation, this is handled here, as
// lookup for a HostReservation can be all that is needed for a lease, rather than
// going through the full allocation algorithm, if one exists
func (h *HostReservation) LoadOptions(ctx context.Context, tx *sql.Tx) error {
	hrOptions, err := loadOptions(ctx, tx, loadHostReservationOptionsStmt, h.ID)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return err
	}

	iprange := &IPRange{}
	iprangeRow := tx.QueryRowContext(ctx, getIPRangeStmt, h.RangeID)

	err = iprange.ScanRow(iprangeRow)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return err
	}

	if iprange.ID != 0 {
		err = iprange.LoadOptions(ctx, tx)
		if err != nil && !errors.Is(err, sql.ErrNoRows) {
			return err
		}
	}

	subnet := &Subnet{}
	subnetRow := tx.QueryRowContext(ctx, getSubnetStmt, iprange.SubnetID)

	err = subnet.ScanRow(subnetRow)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return err
	}

	if subnet.ID != 0 {
		err = subnet.LoadOptions(ctx, tx)
		if err != nil {
			return err
		}
	}

	vlan := &Vlan{}
	vlanRow := tx.QueryRowContext(ctx, getVlanStmt, subnet.VlanID)

	err = vlan.ScanRow(vlanRow)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return err
	}

	if vlan.ID != 0 {
		err = vlan.LoadOptions(ctx, tx)
		if err != nil {
			return err
		}
	}

	options := make(map[uint16]string)

	for k, v := range vlan.Options {
		options[k] = v
	}

	for k, v := range subnet.Options {
		options[k] = v
	}

	for k, v := range iprange.Options {
		options[k] = v
	}

	for k, v := range hrOptions {
		options[k] = v
	}

	h.Options = options

	return nil
}

func (h *HostReservation) InsertOrReplace(ctx context.Context, tx *sql.Tx) error {
	var rangeID *int
	if h.RangeID > 0 {
		rangeID = &h.RangeID
	}

	result, err := tx.ExecContext(
		ctx,
		insertOrReplaceHostReservationStmt,
		h.IPAddress.String(),
		h.MACAddress.String(),
		rangeID,
		h.SubnetID,
	)
	if err != nil {
		return err
	}

	id, err := result.LastInsertId()
	if err != nil {
		return err
	}

	h.ID = int(id)

	return nil
}

func (h *HostReservation) InsertOption(ctx context.Context, tx *sql.Tx, label string, number int, value string) error {
	_, err := tx.ExecContext(ctx, insertHostReservationOptionStmt, label, number, value, h.ID)
	return err
}

type Lease struct {
	Options    map[uint16]string
	DUID       string
	IP         net.IP
	MACAddress net.HardwareAddr
	ID         int
	CreatedAt  int
	UpdatedAt  int
	Lifetime   int
	State      LeaseState
	RangeID    int
	NeedsSync  bool
}

func (l *Lease) ScanRow(row *sql.Row) error {
	var (
		ipStr        string
		macStr, duid *string
	)

	err := row.Scan(
		&l.ID,
		&ipStr,
		&macStr,
		&duid,
		&l.CreatedAt,
		&l.UpdatedAt,
		&l.Lifetime,
		&l.State,
		&l.NeedsSync,
		&l.RangeID,
	)
	if err != nil {
		return err
	}

	if macStr != nil {
		l.MACAddress, err = net.ParseMAC(*macStr)
		if err != nil {
			return err
		}
	}

	if duid != nil {
		l.DUID = *duid
	}

	l.IP = net.ParseIP(ipStr)

	return nil
}

// LoadOptions for Lease has a priority of most specific to most broad,
// i.e vlan -> subnet -> iprange, and if a host reservation exists for this lease,
// it already handles this heirarchy and overrides all else.
func (l *Lease) LoadOptions(ctx context.Context, tx *sql.Tx) error {
	hr := &HostReservation{}
	iprange := &IPRange{}
	subnet := &Subnet{}
	vlan := &Vlan{}

	hostReservationRow := tx.QueryRowContext(
		ctx,
		"SELECT * FROM host_reservation WHERE ip_address = $1 AND mac_address = $2;",
		l.IP.String(),
		l.MACAddress.String(),
	)

	err := hr.ScanRow(hostReservationRow)
	if err == nil {
		err = hr.LoadOptions(ctx, tx)
		if err != nil {
			return err
		}

		l.Options = hr.Options

		return nil
	} else if !errors.Is(err, sql.ErrNoRows) {
		return err
	}

	iprangeRow := tx.QueryRowContext(ctx, getIPRangeStmt, l.RangeID)

	err = iprange.ScanRow(iprangeRow)
	if err != nil {
		return err
	}

	err = iprange.LoadOptions(ctx, tx)
	if err != nil {
		return err
	}

	subnetRow := tx.QueryRowContext(ctx, getSubnetStmt, iprange.SubnetID)

	err = subnet.ScanRow(subnetRow)
	if err != nil {
		return err
	}

	err = subnet.LoadOptions(ctx, tx)
	if err != nil {
		return err
	}

	vlanRow := tx.QueryRowContext(ctx, getVlanStmt, subnet.VlanID)

	err = vlan.ScanRow(vlanRow)
	if err != nil {
		return err
	}

	err = vlan.LoadOptions(ctx, tx)
	if err != nil {
		return err
	}

	l.Options = make(map[uint16]string)

	for k, v := range vlan.Options {
		l.Options[k] = v
	}

	for k, v := range subnet.Options {
		l.Options[k] = v
	}

	for k, v := range iprange.Options {
		l.Options[k] = v
	}

	return nil
}

type Expiration struct {
	DUID       string
	IP         net.IP
	MACAddress net.HardwareAddr
	ID         int
	CreatedAt  int
}

func (e *Expiration) ScanRow(row *sql.Row) error {
	var (
		ipStr           string
		macStr, duidStr *string
	)

	err := row.Scan(
		&e.ID,
		&ipStr,
		&macStr,
		&duidStr,
		&e.CreatedAt,
	)
	if err != nil {
		return err
	}

	e.IP = net.ParseIP(ipStr)

	if macStr != nil {
		mac, err := net.ParseMAC(*macStr)
		if err != nil {
			return err
		}

		e.MACAddress = mac
	}

	if duidStr != nil {
		e.DUID = *duidStr
	}

	return nil
}
