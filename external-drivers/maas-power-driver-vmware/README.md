# MAAS Power Driver: VMware

HTTP service for managing VMware-compatible BMCs as a MAAS power driver.

## Overview

This driver runs as a long-running HTTP service over a UNIX domain socket,
providing power management operations for systems with VMware-compatible
baseboard management controllers.

## Prerequisites

- `python3-pyvmomi`

## Development

```bash
# Install in development mode
pip install -e .

# Run tests
make test

# Build package
make build
```

## Usage

```bash
# Start the service
vmware-driver start --socket-path /tmp/vmware.sock

# Check status
vmware-driver status --socket-path /tmp/vmware.sock
```

## API Endpoints

| Method | Path             | Description            |
|--------|------------------|------------------------|
| GET    | `/metadata`      | Driver capabilities    |
| POST   | `/query`         | Query power state      |
| POST   | `/on`            | Power on               |
| POST   | `/off`           | Power off              |
| POST   | `/cycle`         | Power cycle            |
| POST   | `/reset`         | Hard reset             |
| POST   | `/set-boot-order`| Set boot order         |

## License

AGPL-3.0-only
