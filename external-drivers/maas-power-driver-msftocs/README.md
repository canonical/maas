# MAAS Power Driver: Microsoft OCS

HTTP service for managing Microsoft OCS-compatible BMCs as a MAAS power driver.

## Overview

This driver runs as a long-running HTTP service over a UNIX domain socket,
providing power management operations for systems with Microsoft OCS-compatible
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
msftocs-driver start --socket-path /tmp/msftocs.sock

# Check status
msftocs-driver status --socket-path /tmp/msftocs.sock
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
