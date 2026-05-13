# MAAS Power Driver: HP Power Distribution Unit Wedge

HTTP service for managing HP Power Distribution Unit Wedge-compatible BMCs as a MAAS power driver.

## Overview

This driver runs as a long-running HTTP service over a UNIX domain socket,
providing power management operations for systems with HP Power Distribution Unit Wedge-compatible
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
wedge-driver start --socket-path /tmp/wedge.sock

# Check status
wedge-driver status --socket-path /tmp/wedge.sock
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
