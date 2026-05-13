# Quickstart: Testing Power Driver Extraction

## Prerequisites

- MAAS development environment running
- A test driver snap built (see external driver repositories)

## Manual Testing

### 1. Verify builtin drivers

```bash
# Start rackd, check that manual and webhook are available
curl -s http://localhost:5240/MAAS/rackcontrollers/1.0/rackcontrollers/describe_power_types/ | python3 -m json.tool
```

Expected: `manual` and `webhook` appear in the power types list.

### 2. Install and connect a test driver snap

```bash
# Build the driver snap
cd maas-power-driver-ipmi
snapcraft --output test-ipmi.snap

# Install
sudo snap install --dangerous --devmode test-ipmi.snap

# Connect to MAAS
sudo snap connect maas:power-drivers maas-power-driver-ipmi:power-drivers

# Verify service is running
sudo snap services maas-power-driver-ipmi
```

### 3. Verify discovery

```bash
# Check that rackd discovered the driver
# The ipmi driver should now appear in the power types list
curl -s http://localhost:5240/MAAS/rackcontrollers/1.0/rackcontrollers/describe_power_types/ | python3 -m json.tool
```

Expected: `ipmi` appears in the power types list.

### 4. Verify region notification

```bash
# Check that the region received the driver registration
# (query the v3 internal API or check the database)
psql -d maas -c "SELECT * FROM rack_power_drivers;"
```

Expected: An entry for the ipmi driver associated with the rack's system_id.

### 5. Test power action

```bash
# Use the driver snap's CLI tool (not maas-power)
maas-power-driver-ipmi query --system-id ABC123 --context '{"power_address": "10.0.0.1", "power_user": "admin", "power_pass": "secret"}'
```

### 6. Disconnect and verify removal

```bash
sudo snap disconnect maas:power-drivers maas-power-driver-ipmi:power-drivers
sudo snap remove maas-power-driver-ipmi

# Verify ipmi is no longer in the power types list
curl -s http://localhost:5240/MAAS/rackcontrollers/1.0/rackcontrollers/describe_power_types/ | python3 -m json.tool
```

Expected: `ipmi` no longer appears.

## Running Tests

```bash
# MAAS monorepo tests
bin/test.rack -k power
bin/test.region -k power

# Driver repo tests
cd maas-power-driver-ipmi
make test
```
