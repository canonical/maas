# Security Logging

MAAS implements comprehensive security event logging following the [OWASP Application Logging Vocabulary](https://github.com/OWASP/CheatSheetSeries/blob/master/cheatsheets/Logging_Vocabulary_Cheat_Sheet.md) standard, an industry-recognized framework for security event logging.

## Overview

Security logging in MAAS captures critical security events including authentication, authorization, user management, and token lifecycle events. All security logs are identified with `type=security` and use structured JSON formatting, making them easy to parse, filter, and analyze with security monitoring tools.

Every security log can be correlated with its originating request using the `trace_id` field. See [Contextual Logging](contextual-logging.md) for more details on request correlation.

## Security Event Categories

MAAS logs security events in four main categories:

- **Authentication Events (AUTHN)**: User authentication and login processes
- **Authorization Events (AUTHZ)**: Access control and permission checks
- **User Management Events (USER)**: User account creation, modification, and deletion
- **Token Management Events (AUTHN_TOKEN)**: Token lifecycle, including creation, deletion, revocation, and reuse attempts

## Log Format

All security logs follow a consistent JSON structure:

```json
{
  "message": "AUTHN_login_successful",
  "timestamp": "2025-11-26T21:02:55.704463Z",
  "level": "INFO",
  "type": "security",
  "userID": "admin",
  "role": "Admin",
  "trace_id": "cc6b8a1da517409c9cfc9871d6784f7b",
  "request_method": "POST",
  "request_path": "/MAAS/a/v3/auth/login",
  "request_remote_ip": "10.10.0.1",
  "useragent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
}
```

### Key Fields

- **message**: The security event type and optional additional information
- **timestamp**: ISO 8601 formatted timestamp in UTC
- **type**: Always set to `security` for security events
- **trace_id**: Unique identifier correlating all logs for a single request
- **userID**: Username of the authenticated user (when applicable)
- **role**: User's role such as Admin or User (when applicable)
- **token_hash**: SHA-256 hash of tokens for secure identification (when applicable)

## Security Event Types

### Authentication Events

Events related to user authentication, login processes, and credential management.

#### AUTHN_login_successful

Logged when a user successfully logs in to MAAS.

**Example**:

```json
{
  "message": "AUTHN_login_successful",
  "type": "security",
  "userID": "admin",
  "role": "Admin"
}
```

#### AUTHN_login_unsuccessful

Logged when a login attempt fails due to invalid credentials.

**Example**:

```json
{
  "message": "AUTHN_login_unsuccessful",
  "type": "security"
}
```

**Note**: Usernames are not logged in failed login attempts to prevent information disclosure.

#### AUTHN_authentication_successful

Logged when a request is successfully authenticated using tokens, macaroons, or other methods.

**Example**:

```json
{
  "message": "AUTHN_authentication_successful",
  "type": "security",
  "userID": "operator1",
  "role": "User"
}
```

#### AUTHN_authentication_failed

Logged when authentication fails for a request (invalid token, expired credentials, etc.).

**Example**:

```json
{
  "message": "AUTHN_authentication_failed",
  "type": "security"
}
```

#### AUTHN_password_changed

Logged when a user's password is changed.

**Format**: `AUTHN_password_changed:<username>`

**Example**:

```json
{
  "message": "AUTHN_password_changed:jdoe",
  "type": "security"
}
```

**Note**: The username in the message refers to the account whose password was changed. The `userID` field shows who made the change.

### Authorization Events

Events related to access control, permission checks, and administrative actions.

#### AUTHZ_fail

Logged when a user attempts to access a resource or perform an action they are not authorized to perform.

**Example**:

```json
{
  "message": "AUTHZ_fail",
  "type": "security",
  "userID": "user1",
  "role": "User"
}
```

#### AUTHZ_administrative

Logged when an administrative action is performed on system resources.

**Format**: `AUTHZ_administrative:<resource>:<action>:<resource_id>`

**Example**:

```json
{
  "message": "AUTHZ_administrative:user:created:jdoe",
  "type": "security",
  "userID": "admin",
  "role": "Admin"
}
```

```json
{
  "message": "AUTHZ_administrative:subnet:updated:10.0.0.0/24",
  "type": "security",
  "userID": "admin",
  "role": "Admin"
}
```

```json
{
  "message": "AUTHZ_administrative:machine:deleted:ace-swan",
  "type": "security",
  "userID": "admin",
  "role": "Admin"
}
```

### User Management Events

Events related to user account lifecycle including creation, modification, and deletion.

#### USER_created

Logged when a new user account is created.

**Format**: `USER_created:<username>:<role>`

**Example**:

```json
{
  "message": "USER_created:jdoe:User",
  "type": "security"
}
```

```json
{
  "message": "USER_created:admin2:Admin",
  "type": "security"
}
```

#### USER_deleted

Logged when a user account is deleted.

**Format**: `USER_deleted:<username>`

**Example**:

```json
{
  "message": "USER_deleted:jdoe",
  "type": "security"
}
```

#### USER_updated

Logged when a user's privileges are modified (e.g., promoted to admin or demoted).

**Format**: `USER_updated:<username>:<new_role>`

**Example**:

```json
{
  "message": "USER_updated:jdoe:Admin",
  "type": "security"
}
```

**Note**: Regular profile updates (email, name, etc.) without privilege changes do not generate this event.

### Token Management Events

#### AUTHN_token_created

Logged when a new authentication token is created.

**Format**: `AUTHN_token_created:<token_type>[:<identifier>]`

**Token Types**:

- `JWT`: JSON Web Token for API authentication
- `bootstraptoken`: Token for agent enrollment
- `OIDC:access_token`: OAuth2/OIDC access token
- `OIDC:refresh_token`: OAuth2/OIDC refresh token

**Examples**:

```json
{
  "message": "AUTHN_token_created:JWT",
  "type": "security",
  "token_hash": "a3c45f7b2e9d1a6c8b4e5f7a9c2d3e4f5b6c7a8d9e0f1a2b3c4d5e6f7a8b9c0d"
}
```

```json
{
  "message": "AUTHN_token_created:bootstraptoken",
  "type": "security",
  "token_hash": "7f3e6a9b4c1d8e5f2a0c7b4d9e6a1f3c8b5d2e9f6a3c0d7b4e1f8a5c2d9e6b3"
}
```

#### AUTHN_token_deleted

Logged when an authentication token is explicitly deleted from the system.

**Example**:

```json
{
  "message": "AUTHN_token_deleted:bootstraptoken",
  "type": "security",
  "token_hash": "7f3e6a9b4c1d8e5f2a0c7b4d9e6a1f3c8b5d2e9f6a3c0d7b4e1f8a5c2d9e6b3"
}
```

**Note**: The `token_hash` matches the hash from the corresponding `AUTHN_token_created` event, allowing correlation.

#### AUTHN_token_revoked

Logged when an authentication token is revoked (invalidated but still exists in the database).

**Examples**:

```json
{
  "message": "AUTHN_token_revoked:certificate:550e8400-e29b-41d4-a716-446655440000",
  "type": "security"
}
```

```json
{
  "message": "AUTHN_token_revoked:OIDC:refresh_token",
  "type": "security",
  "token_hash": "c4d5e6f7a8b9c0d1a2b3c4d5e6f7a8b9c0d1a2b3c4d5e6f7a8b9c0d1a2b3c4d"
}
```

#### AUTHN_token_reused

Logged when an attempt is made to use an invalid, expired, or non-existent token.

**What This Catches**:

- Expired tokens
- Invalid or malformed tokens
- Deleted or revoked tokens
- Non-existent tokens
- Tampered tokens

**Examples**:

```json
{
  "message": "AUTHN_token_reused:JWT",
  "type": "security",
  "token_hash": "a3c45f7b2e9d1a6c8b4e5f7a9c2d3e4f5b6c7a8d9e0f1a2b3c4d5e6f7a8b9c0d"
}
```

```json
{
  "message": "AUTHN_token_reused:bootstraptoken",
  "type": "security",
  "token_hash": "7f3e6a9b4c1d8e5f2a0c7b4d9e6a1f3c8b5d2e9f6a3c0d7b4e1f8a5c2d9e6b3"
}
```

**Security Note**: A high frequency of `AUTHN_token_reused` events may indicate:

- Attempted token replay attacks
- Client-side bugs causing token reuse
- Token theft attempts

## Token Hashing

To protect sensitive token values while still allowing correlation in logs, MAAS hashes tokens before logging them using SHA-256.

### Why Hashing?

1. **Security**: Prevents token values from being exposed in logs
2. **Correlation**: The same token always produces the same hash, enabling tracking
3. **Non-reversibility**: Hash cannot be reversed to obtain the original token
4. **Auditability**: Enables security investigations without exposing credentials

### Tracking Token Lifecycle

You can track a token from creation through deletion and attempted reuse by matching `token_hash` values:

```json
{
  "message": "AUTHN_token_created:bootstraptoken",
  "token_hash": "abc123...",
  "timestamp": "2025-11-26T10:00:00Z"
}

{
  "message": "AUTHN_token_deleted:bootstraptoken",
  "token_hash": "abc123...",
  "timestamp": "2025-11-26T10:05:00Z"
}

{
  "message": "AUTHN_token_reused:bootstraptoken",
  "token_hash": "abc123...",
  "timestamp": "2025-11-26T10:10:00Z"
}
```

The matching `token_hash` shows this is the same token throughout its lifecycle.

## Querying Security Logs

### Filter All Security Logs

To view all security events:

```bash
journalctl -u snap.maas.pebble.service | jq 'select(.MESSAGE | contains("\"type\":\"security\""))'
```

### Filter by Event Type

To view specific event types (e.g., all authentication failures):

```bash
journalctl -u snap.maas.pebble.service | \
  jq 'select(.MESSAGE | contains("AUTHN_authentication_failed"))'
```

### Filter by User

To view all security events for a specific user:

```bash
journalctl -u snap.maas.pebble.service | \
  jq 'select(.MESSAGE | fromjson | .userID == "admin")'
```

### Filter by Token Hash

To track a specific token across its lifecycle:

```bash
journalctl -u snap.maas.pebble.service | \
  jq 'select(.MESSAGE | fromjson | .token_hash == "abc123...")'
```

### Filter by Trace ID

To see all security events for a specific request:

```bash
journalctl -u snap.maas.pebble.service | \
  jq 'select(.MESSAGE | fromjson | .trace_id == "cc6b8a1da517409c9cfc9871d6784f7b")'
```

## Security Monitoring Best Practices

### What to Monitor

1. **Failed authentication attempts**: High frequency may indicate brute force attacks
2. **Authorization failures**: Repeated failures for the same user may indicate privilege escalation attempts
3. **Token reuse**: May indicate token theft or replay attacks
4. **Administrative actions**: Track all privileged operations for audit purposes
5. **Account changes**: Monitor user creation, deletion, and privilege escalation

### Alert Recommendations

Consider setting up alerts for:

- Multiple `AUTHN_login_unsuccessful` or `AUTHN_authentication_failed` events from the same IP
- `AUTHZ_fail` events for the same user/resource combination
- Multiple `AUTHN_token_reused` events with the same token hash
- `USER_updated` events that grant admin privileges
- `AUTHZ_administrative` events outside of expected maintenance windows

### Integration with Security Tools

MAAS security logs are compatible with Security Information and Event Management (SIEM) systems such as:

- Splunk
- Elastic Stack (ELK)
- Graylog
- LogRhythm

The structured JSON format and OWASP-compliant field names ensure seamless integration.

## Related Documentation

- [Contextual Logging](contextual-logging.md) - Understanding trace IDs and request correlation
- [Use Logging](../how-to-guides/use-logging.md) - General MAAS logging guide
