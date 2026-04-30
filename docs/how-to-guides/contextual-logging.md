# Contextual Logging

MAAS uses contextual logging, where individual log statements contain only a subset of information about a request, but all statements share the same `trace_id`. This approach:

- Reduces redundancy in logs
- Allows for more focused log messages
- Enables correlation of related events
- Supports efficient log storage and transmission

Using a trace ID enables the correlation of log statements across different components and services for a single request. This enables operators to track the complete flow of a request through the system, even when logs from multiple concurrent requests are interleaved.

## Overview

A trace ID is a unique identifier that follows a request throughout its lifecycle in MAAS. A request received by MAAS may either have a trace id set already, or if it is missing MAAS will generate a new one. This trace ID is then included in every log statement related to that request, making it possible to filter and view all logs for a specific operation.

## How Trace IDs Work

### Trace ID Format

Trace IDs are 32-character hexadecimal strings. For example:

```
cc6b8a1da517409c9cfc9871d6784f7b
```

### Trace ID Propagation

#### Client-Provided Trace IDs

Clients can provide their own trace ID by including the `MAAS-trace-id` header in API requests:

```bash
curl -H "MAAS-trace-id: my-custom-trace-id" https://maas.example.com/MAAS/api/2.0/...
```

This allows clients to correlate their own logs with MAAS logs for end-to-end tracing.

#### Automatic Generation

If no trace ID is provided in the request headers, MAAS automatically generates one when the request enters the system.

#### Response Headers

MAAS includes the trace ID in the response headers, allowing clients to retrieve and use it for debugging:

```
MAAS-trace-id: cc6b8a1da517409c9cfc9871d6784f7b
```

## Example Log Output

Here's an example showing multiple log statements for a single request, all sharing the same trace ID:

```json
{
  "message": "Start processing request",
  "request_method": "PUT",
  "request_path": "/MAAS/a/v3/users/8",
  "request_remote_ip": "10.10.0.1",
  "useragent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
  "trace_id": "cc6b8a1da517409c9cfc9871d6784f7b",
  "timestamp": "2025-11-26T21:02:55.704463Z",
  "level": "INFO"
}
{
  "message": "AUTHN_authentication_successful",
  "type": "security",
  "userID": "maas",
  "role": "Admin",
  "trace_id": "cc6b8a1da517409c9cfc9871d6784f7b",
  "timestamp": "2025-11-26T21:02:55.709633Z",
  "level": "INFO"
}
{
  "message": "AUTHN_password_changed:testuser",
  "type": "security",
  "trace_id": "cc6b8a1da517409c9cfc9871d6784f7b",
  "timestamp": "2025-11-26T21:02:55.806602Z",
  "level": "INFO"
}
{
  "message": "End processing request",
  "status_code": 200,
  "elapsed_time_seconds": 0.105,
  "trace_id": "cc6b8a1da517409c9cfc9871d6784f7b",
  "timestamp": "2025-11-26T21:02:55.809642Z",
  "level": "INFO"
}
```

In this example, the trace ID `cc6b8a1da517409c9cfc9871d6784f7b` ties together:

1. The initial request metadata
2. Authentication success
3. A password change operation
4. The final response status

## Filtering Logs by Trace ID

### Using journalctl

To view all logs for a specific trace ID using `journalctl`:

```bash
journalctl -u snap.maas.pebble.service | grep "cc6b8a1da517409c9cfc9871d6784f7b"
```

### Using jq for JSON Processing

For more sophisticated filtering and formatting of JSON logs:

```bash
journalctl -u snap.maas.pebble.service -o json | \
  jq 'select(.MESSAGE | fromjson | .trace_id == "cc6b8a1da517409c9cfc9871d6784f7b") | .MESSAGE | fromjson'
```

This command:
1. Outputs journalctl logs in JSON format
2. Filters for messages with the specified trace ID
3. Extracts and formats the structured log messages

## Use Cases

### Debugging Failed Requests

When a user reports an error, they can provide the trace ID from the response headers. Operators can then use this trace ID to find all related log entries and diagnose the issue.

### Performance Analysis

By filtering logs by trace ID, you can measure the time spent in each component of the system for a particular request, helping identify performance bottlenecks.

### Distributed Tracing

When MAAS interacts with external services, the trace ID can be forwarded to those services, enabling end-to-end distributed tracing across multiple systems.

### Audit Trails

For security and compliance purposes, trace IDs make it possible to reconstruct the complete sequence of operations for any given request.

## Related Documentation

- [Security Logging](security-logging.md) - Learn about security-specific logging with trace IDs
- [Use Logging](use-logging.md) - General MAAS logging guide
- [OWASP Logging Vocabulary](https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/Logging_Vocabulary_Cheat_Sheet.md) - Industry standards for log fields
