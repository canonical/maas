# MAAS Power Driver: Cisco UCSM

HTTP service for managing Cisco UCSM-compatible BMCs as a MAAS power driver.

## Overview

This driver runs as a long-running HTTP service over a UNIX domain socket,
providing power management operations for systems with Cisco UCSM-compatible
baseboard management controllers.

## Prerequisites

None — uses standard library only

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
ucsm-driver start --socket-path /tmp/ucsm.sock

# Check status
ucsm-driver status --socket-path /tmp/ucsm.sock
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
