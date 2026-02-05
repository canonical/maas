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

// Package dhcp implements a DHCP server as defined in RFC2131.
//
// The package provides tools for managing the full DHCP lifecycle, including
// IP address allocation, lease persistence, and support for custom options.
package dhcp

import (
	"bytes"
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/insomniacslk/dhcp/dhcpv4"
	"github.com/rs/zerolog/log"
)

const (
	getHostReservationForMACStmt = `
SELECT hr.* FROM vlan AS v
	JOIN subnet AS s ON s.vlan_id = v.id
	JOIN ip_range AS ir ON ir.subnet_id = s.id
	JOIN host_reservation AS hr ON hr.range_id = ir.id
	WHERE v.id = $1 AND hr.mac_address = $3;
`
	getIPRangeForAllocationStmt = `
SELECT ir.* FROM vlan AS v 
	JOIN subnet AS s ON s.vlan_id = v.id
	JOIN ip_range as ir ON ir.subnet_id = s.id
	WHERE v.id = $1 AND ir.dynamic = $2 AND ir.fully_allocated = false
	ORDER BY RANDOM() LIMIT 1;
`
	getLeaseInVLANStmt = `
SELECT l.* FROM lease AS l
	JOIN ip_range AS iprange ON iprange.id = l.range_id
	JOIN subnet AS s ON s.id = iprange.subnet_id
	JOIN vlan AS v ON v.id = s.vlan_id
	WHERE v.id = $1 AND l.mac_address = $2;
`
	getLeaseForIPStmt           = "SELECT id FROM lease WHERE ip = $1;"
	getPreviousLeaseInRangeStmt = `
SELECT l.* FROM ip_range AS ir
	JOIN lease AS l ON l.range_id = ir.id
	WHERE ir.id = $1 ORDER BY l.id DESC LIMIT 1;
`
	getLeaseForIPAndMACStmt    = "SELECT * FROM lease WHERE ip = $1 AND mac_address = $2;"
	getVLANForInterfaceIdxStmt = `
SELECT v.* FROM interface AS i
	JOIN vlan AS v ON v.id = i.vlan_id
	WHERE i.hostname = $1 AND i.idx = $2;
`
	updateIPRangeAsFullStmt = "UPDATE ip_range SET fully_allocated = true WHERE id = $1;"
	createOfferedLeaseStmt  = `
INSERT INTO lease(ip, mac_address, state, created_at, updated_at, lifetime, needs_sync, range_id) 
	VALUES ($1, $2, $3, $4, $5, $6, true, $7);
`
	updateLeaseStateByIDStmt    = "UPDATE lease SET state = $1, updated_at = $2 WHERE id = $3;"
	createExpirationStmt        = "INSERT INTO expiration VALUES (NULL, $1, $2, $3, $4);"
	deleteLeaseForIPAndMACStmt  = "DELETE FROM lease WHERE ip = $1 AND mac_address = $2;"
	deleteLeaseForMACInVLANStmt = `
DELETE FROM lease AS l
WHERE EXISTS (
	SELECT 1 FROM ip_range AS ir
	JOIN subnet AS s ON s.id = ir.subnet_id
	JOIN vlan AS v ON v.id = s.vlan_id
	WHERE ir.id = l.range_id AND v.id = $1 AND l.mac_address = $2
);
`
	createLeaseForConflict = `
INSERT INTO lease (
	ip, state, created_at, updated_at, lifetime, needs_sync, range_id
) VALUES ($1, 1, $2, $3, 30, false, 0);
`
)

var (
	ErrInvalidDHCP4State = errors.New("received a message type invalid to current DORA state")
	ErrRangeFull         = errors.New("the selected IP range is fully allocated")
	ErrNoMatchingVLAN    = errors.New("no suitable VLAN found")
	ErrNoAvailableIP     = errors.New("no free IP available")
	ErrMissingDHCPOption = errors.New("the proposed lease is missing a required DHCP option")
)

type Offer struct {
	Options map[uint16]string
	IP      net.IP
}

type Allocator4 interface {
	GetOfferFromDiscover(context.Context, *sql.Tx, *dhcpv4.DHCPv4, int, net.HardwareAddr) (*Offer, error)
	GetOfferForAllocation(context.Context, *sql.Tx, int, net.HardwareAddr) (*Offer, error)
	ACKLease(context.Context, *sql.Tx, net.IP, net.HardwareAddr) (*Lease, error)
	NACKLease(context.Context, *sql.Tx, net.IP, net.HardwareAddr) error
	UpdateForRenewal(context.Context, *sql.Tx, net.IP, net.HardwareAddr) error
	Release(context.Context, *sql.Tx, int, net.HardwareAddr) error
	MarkConflicted(context.Context, *sql.Tx, net.IP) error
}

type dqliteAllocator4 struct {
	hostname string // attached to the allocator to avoid calling os.Hostname() on every DISCOVER
}

func newDQLiteAllocator4() (*dqliteAllocator4, error) {
	hn, err := os.Hostname()
	if err != nil {
		return nil, err
	}

	return &dqliteAllocator4{
		hostname: hn,
	}, nil
}

func (d *dqliteAllocator4) GetOfferFromDiscover(ctx context.Context, tx *sql.Tx, discover *dhcpv4.DHCPv4, ifaceIdx int, mac net.HardwareAddr) (*Offer, error) {
	if discover.MessageType() != dhcpv4.MessageTypeDiscover {
		return nil, fmt.Errorf("did not receive a DISCOVER: %w", ErrInvalidDHCP4State)
	}

	// check for different MAC than one read off the wire, i.e if relayed
	if !bytes.Equal(discover.ClientHWAddr, mac) {
		mac = discover.ClientHWAddr
	}

	relayOptions := discover.RelayAgentInfo()
	if relayOptions != nil { //nolint:staticcheck // ignore TODO's
		// TODO fetch relay info
	}

	vlan, err := d.getVLANForAllocation(ctx, tx, ifaceIdx)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrNoMatchingVLAN
		}

		return nil, err
	}

	lease, err := d.getLeaseIfExists(ctx, tx, vlan.ID, mac)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, err
	}

	if lease != nil {
		err = lease.LoadOptions(ctx, tx)
		if err != nil {
			return nil, err
		}

		return &Offer{
			IP:      lease.IP.To4(),
			Options: lease.Options,
		}, nil
	}

	hostRes, err := d.getHostReservationIfExists(ctx, tx, vlan.ID, mac)
	if err != nil && !errors.Is(err, sql.ErrNoRows) {
		return nil, err
	}

	if hostRes != nil {
		err = hostRes.LoadOptions(ctx, tx)
		if err != nil {
			return nil, err
		}

		offer := &Offer{
			IP:      hostRes.IPAddress.To4(),
			Options: hostRes.Options,
		}

		_, err = d.createOfferedLease(ctx, tx, offer, mac, hostRes.RangeID)
		if err != nil {
			return nil, err
		}

		return offer, nil
	}

	iprange, err := d.getIPRangeForAllocation(ctx, tx, vlan.ID, true)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return nil, ErrNoAvailableIP
		}

		return nil, err
	}

	ip, err := d.getIPForAllocation(ctx, tx, iprange)
	if err != nil {
		return nil, err
	}

	offer := &Offer{
		IP: ip,
	}

	lease, err = d.createOfferedLease(ctx, tx, offer, mac, iprange.ID)
	if err != nil {
		return nil, err
	}

	offer.Options = lease.Options

	return offer, nil
}

func (d *dqliteAllocator4) GetOfferForAllocation(ctx context.Context, tx *sql.Tx, subnetID int, mac net.HardwareAddr) (*Offer, error) {
	// TODO to be called from temporal activity to allocate for AUTO assignment
	return nil, nil //nolint:nilnil // ignore TODO's
}

func (d *dqliteAllocator4) getVLANForAllocation(ctx context.Context, tx *sql.Tx, ifaceIdx int) (*Vlan, error) {
	row := tx.QueryRowContext(ctx, getVLANForInterfaceIdxStmt, d.hostname, ifaceIdx)
	vlan := &Vlan{}
	err := vlan.ScanRow(row)

	return vlan, err
}

func (d *dqliteAllocator4) getLeaseIfExists(ctx context.Context, tx *sql.Tx, vlanID int, mac net.HardwareAddr) (*Lease, error) {
	row := tx.QueryRowContext(ctx, getLeaseInVLANStmt, vlanID, strings.ToLower(mac.String()))
	lease := &Lease{}

	err := lease.ScanRow(row)
	if err != nil {
		return nil, err
	}

	return lease, nil
}

func (d *dqliteAllocator4) getHostReservationIfExists(ctx context.Context, tx *sql.Tx, vlanID int, mac net.HardwareAddr) (*HostReservation, error) {
	row := tx.QueryRowContext(ctx, getHostReservationForMACStmt, vlanID, strings.ToLower(mac.String()))
	hr := &HostReservation{}

	err := hr.ScanRow(row)
	if err != nil {
		return nil, err
	}

	return hr, nil
}

func (d *dqliteAllocator4) getIPRangeForAllocation(ctx context.Context, tx *sql.Tx, vlanID int, dynamic bool) (*IPRange, error) {
	rows, err := tx.QueryContext(ctx, getIPRangeForAllocationStmt, vlanID, dynamic)
	if err != nil {
		return nil, fmt.Errorf("error querying for iprange: %w", err)
	}

	defer func() {
		cErr := rows.Close()
		if cErr != nil {
			log.Err(err).Send()
		}
	}()

	iprange := &IPRange{}

	if rows.Next() {
		var startIPStr, endIPStr string

		err = rows.Scan(
			&iprange.ID,
			&startIPStr,
			&endIPStr,
			&iprange.Size,
			&iprange.FullyAllocated,
			&iprange.Dynamic,
			&iprange.SubnetID,
		)
		if err != nil {
			return nil, fmt.Errorf("error reading iprange: %w", err)
		}

		iprange.StartIP = net.ParseIP(startIPStr)
		iprange.EndIP = net.ParseIP(endIPStr)

		// use first available if there are more than one
		return iprange, nil
	} else if err = rows.Err(); err != nil {
		return nil, fmt.Errorf("error scanning iprange: %w", err)
	}

	return nil, ErrNoAvailableIP
}

func (d *dqliteAllocator4) getIPForAllocation(ctx context.Context, tx *sql.Tx, iprange *IPRange) (net.IP, error) {
	previousLeaseInRangeRow := tx.QueryRowContext(ctx, getPreviousLeaseInRangeStmt, iprange.ID)
	previousLease := &Lease{}

	err := previousLease.ScanRow(previousLeaseInRangeRow)
	if err != nil {
		if errors.Is(err, sql.ErrNoRows) {
			return iprange.StartIP.To4(), nil
		}

		return nil, fmt.Errorf("error finding previous allocated IP in range: %w", err)
	}

	nextIP := make(net.IP, 4)
	copy(nextIP, previousLease.IP.To4())
	nextIP = incrementIP4(nextIP)

	var row *sql.Rows

	for bytes.Compare(nextIP, iprange.EndIP.To4()) < 0 {
		row, err = tx.QueryContext(ctx, getLeaseForIPStmt, nextIP.String())
		if err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				return nextIP, nil
			}

			return nil, fmt.Errorf("error querying for free IP: %w", err)
		}

		if !row.Next() {
			return nextIP, nil
		}

		nextIP = incrementIP4(nextIP)
	}

	copy(nextIP, iprange.StartIP.To4())

	for bytes.Compare(nextIP, iprange.EndIP.To4()) < 0 {
		row, err = tx.QueryContext(ctx, getLeaseForIPStmt, nextIP.String())
		if err != nil {
			if errors.Is(err, sql.ErrNoRows) {
				return nextIP, nil
			}

			return nil, fmt.Errorf("error scanning range for free IP: %w", err)
		}

		if !row.Next() {
			return nextIP, nil
		}

		nextIP = incrementIP4(nextIP)
	}

	err = d.setIPRangeFull(ctx, tx, iprange.ID)
	if err != nil {
		return nil, fmt.Errorf("error marking iprange fully allocated: %w", err)
	}

	return nil, ErrRangeFull
}

func incrementIP4(ip net.IP) net.IP {
	ip = ip.To4()
	if ip == nil {
		return nil
	}

	for i := 3; i >= 0; i-- {
		if int(ip[i])+1 > 255 {
			ip[i] = 0
			continue
		}

		ip[i]++

		break
	}

	return ip
}

func (d *dqliteAllocator4) setIPRangeFull(ctx context.Context, tx *sql.Tx, iprangeID int) error {
	_, err := tx.ExecContext(ctx, updateIPRangeAsFullStmt, iprangeID)

	return err
}

func (d *dqliteAllocator4) createOfferedLease(ctx context.Context, tx *sql.Tx, offer *Offer, mac net.HardwareAddr, iprangeID int) (*Lease, error) {
	nowEpoch := int(time.Now().Unix())
	lease := &Lease{
		IP:         offer.IP,
		MACAddress: mac,
		State:      LeaseStateOffered,
		CreatedAt:  nowEpoch,
		UpdatedAt:  nowEpoch,
		RangeID:    iprangeID,
		Options:    offer.Options,
	}

	err := lease.LoadOptions(ctx, tx)
	if err != nil {
		return nil, err
	}

	lifetimeStr, ok := lease.Options[uint16(dhcpv4.OptionIPAddressLeaseTime)]
	if !ok {
		return nil, fmt.Errorf("%w: lease lifetime", ErrMissingDHCPOption)
	}

	lifetime, err := strconv.Atoi(lifetimeStr)
	if err != nil {
		return nil, err
	}

	lease.Lifetime = lifetime * 1000 // convert the option (in seconds) to milliseconds

	result, err := tx.ExecContext(
		ctx,
		createOfferedLeaseStmt,
		lease.IP.String(),
		strings.ToLower(lease.MACAddress.String()),
		lease.State,
		lease.CreatedAt,
		lease.UpdatedAt,
		lease.Lifetime,
		lease.RangeID,
	)
	if err != nil {
		return nil, err
	}

	id, err := result.LastInsertId()
	if err != nil {
		return nil, err
	}

	lease.ID = int(id)

	return lease, nil
}

func (d *dqliteAllocator4) ACKLease(ctx context.Context, tx *sql.Tx, ip net.IP, mac net.HardwareAddr) (*Lease, error) {
	row := tx.QueryRowContext(ctx, getLeaseForIPAndMACStmt, ip.String(), mac.String())
	lease := &Lease{}

	err := lease.ScanRow(row)
	if err != nil {
		return nil, err
	}

	now := time.Now().Unix()

	_, err = tx.ExecContext(ctx, updateLeaseStateByIDStmt, LeaseStateAcked, now, lease.ID)
	if err != nil {
		return nil, err
	}

	lease.UpdatedAt = int(now)

	return lease, lease.LoadOptions(ctx, tx)
}

func (d *dqliteAllocator4) NACKLease(ctx context.Context, tx *sql.Tx, ip net.IP, mac net.HardwareAddr) error {
	_, err := tx.ExecContext(ctx, deleteLeaseForIPAndMACStmt, ip.String(), mac.String())

	return err
}

func (d *dqliteAllocator4) UpdateForRenewal(ctx context.Context, tx *sql.Tx, ip net.IP, mac net.HardwareAddr) error {
	now := time.Now().Unix()

	result, err := tx.ExecContext(
		ctx,
		"UPDATE lease SET updated_at = $1 WHERE ip = $2 AND mac_address = $3;",
		now,
		ip.String(),
		mac.String(),
	)
	if err != nil {
		return err
	}

	rowsAffected, err := result.RowsAffected()
	if err != nil {
		return err
	}

	if rowsAffected == 0 {
		return sql.ErrNoRows
	}

	return nil
}

func (d *dqliteAllocator4) Release(ctx context.Context, tx *sql.Tx, ifaceIdx int, mac net.HardwareAddr) error {
	row := tx.QueryRowContext(ctx, getVLANForInterfaceIdxStmt, d.hostname, ifaceIdx)
	vlan := &Vlan{}

	err := vlan.ScanRow(row)
	if err != nil {
		return err
	}

	row = tx.QueryRowContext(ctx, getLeaseInVLANStmt, vlan.ID, mac.String())
	lease := &Lease{}

	err = lease.ScanRow(row)
	if err != nil {
		return err
	}

	now := time.Now().Unix()

	if lease.State == LeaseStateAcked {
		_, err = tx.ExecContext(ctx, createExpirationStmt, lease.IP.String(), lease.MACAddress.String(), nil, now)
		if err != nil {
			return err
		}
	}

	_, err = tx.ExecContext(ctx, deleteLeaseForMACInVLANStmt, vlan.ID, mac.String())

	return err
}

// MarkConflicted creates a lease for a conflicting IP from a client's decline message. This temporarily
// marks the IP in use by an unknown entity, disallowing it to be allocated for a lease, for some time.
// This lease does not get reported back to the region and only serves to be used in allocation.
func (d *dqliteAllocator4) MarkConflicted(ctx context.Context, tx *sql.Tx, ip net.IP) error {
	now := time.Now().Unix()
	_, err := tx.ExecContext(ctx, createLeaseForConflict, ip.String(), now, now)

	return err
}
