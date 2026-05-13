# MAAS Power Driver: Intel AMT

HTTP service for managing Intel AMT-compatible BMCs as a MAAS power driver.

## Overview

This driver runs as a long-running HTTP service over a UNIX domain socket,
providing power management operations for systems with Intel AMT-compatible
baseboard management controllers.

## Prerequisites

- `amtterm`
- `wsmancli`

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
amt-driver start --socket-path /tmp/amt.sock

# Check status
amt-driver status --socket-path /tmp/amt.sock
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
