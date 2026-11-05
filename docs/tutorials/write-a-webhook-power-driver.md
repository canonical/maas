<!-- Copyright 2026 Canonical Ltd.  This software is licensed under the
GNU Affero General Public License version 3 (see the file LICENSE). -->

# Replace a power driver with a webhook

MAAS's Webhook power driver lets you supply the hardware-specific power-control
code outside MAAS. Use it to replace a removed driver or integrate hardware that
MAAS does not support natively.

In this tutorial, you will write and run a small web service for an **Eaton PDU**,
then configure MAAS to call it. The service controls the outlet supplying a
server, not the entire PDU. You do not install a new driver inside MAAS.

MAAS no longer includes the native `eaton` driver. This example uses its SNMP
commands and default power-on sequence.

```text
MAAS rack controller --HTTP--> your webhook service --SNMP--> Eaton PDU outlet
                                                                   |
                                                                 server
```

:::{warning}
This tutorial uses plain HTTP and SNMPv1 on an isolated, trusted management
network. Neither encrypts credentials or traffic. Restrict access to the webhook
and PDU to the management hosts; do not expose them to the Internet. This is a
learning example, not a hardened deployment.

Use a test server: switching its outlet off cuts power immediately. The power-on
operation also cycles the outlet if it is already on, matching the retired
driver.
:::

## 1. Understand the webhook interface

MAAS needs three URLs:

| MAAS action | Request | Example response |
| --- | --- | --- |
| Query power | `GET /outlets/3/status` | `{"status": "running"}` or `{"status": "stopped"}` |
| Power on | `POST /outlets/3/on` | `{"result": "accepted"}` |
| Power off | `POST /outlets/3/off` | `{"result": "accepted"}` |

MAAS sends the POST requests without a body. It reads the query response using
configurable regular expressions; the example responses match its defaults.
A successful POST acknowledges the command, not the final hardware state.
An unsuccessful hardware operation must return an HTTP error, not a success
response or a made-up power state.

For simple access control, this example requires a token. Configure it in MAAS's
**Power token** field; MAAS sends it as `Authorization: Bearer <token>`.

## 2. Prepare a test server and PDU

You need an existing MAAS machine, an always-on Ubuntu host for the webhook, and
an Eaton PDU supporting the outlet MIB used by the retired driver. Not every
Eaton model uses the same MIB: confirm these OIDs against your model before
proceeding.

This walkthrough uses the following example addresses; replace them with yours:

| Item | Example |
| --- | --- |
| Webhook host's management IP | `192.0.2.10` |
| Eaton PDU IP | `192.0.2.20` |
| Outlet supplying the test server | `3` |

Allow the managing MAAS rack controllers to reach TCP port 8000 on the webhook
host, and the webhook host to reach UDP port 161 on the PDU. Enable SNMPv1 on the
PDU with a read-write community and restrict access to the webhook host.

Configure the server's firmware to **power on when AC power is restored**.
Otherwise, enabling its outlet may leave the server off. An outlet state reports
AC supply, not whether the OS is running. A server with redundant power supplies
needs all its feeds handled together; this example controls only one outlet.

Do not host the webhook on the server or outlet it controls. Before upgrading
from a removed driver, retain the PDU address, outlet number and any settings you
need: MAAS does not automatically convert the old configuration to Webhook.

## 3. Write the hardware-specific service

On the webhook host, install the runtime dependencies:

```bash
sudo apt-get install python3-flask gunicorn snmp
mkdir -p ~/eaton-webhook
cd ~/eaton-webhook
```

Save the following code as `eaton_webhook_example.py`, or download
{download}`the example file <../../utilities/webhook-power-driver/eaton_webhook_example.py>`.
In a MAAS source checkout, it is also under `utilities/webhook-power-driver/`.

```{literalinclude} ../../utilities/webhook-power-driver/eaton_webhook_example.py
:language: python
```

Most of the hardware-specific work is in `query_power()` and `set_power()`.
The `snmp()` helper builds the same outlet OIDs as the retired driver:

| Purpose | OID for outlet 3 | Operation |
| --- | --- | --- |
| Read outlet state | `1.3.6.1.4.1.534.6.6.7.6.6.1.2.0.3` | `snmpget`: `0` = off, `1` = on |
| Switch outlet off | `1.3.6.1.4.1.534.6.6.7.6.6.1.3.0.3` | `snmpset`: integer `0` |
| Switch outlet on | `1.3.6.1.4.1.534.6.6.7.6.6.1.4.0.3` | `snmpset`: integer `0` |

For on/off, the value `0` means **act without a delay**, not "set the power state
to off." `-Oqve` makes `snmpget` return just the numeric value, without labels.
The final OID component is the outlet number, validated against the retired
driver's range of 1-24.

These objects are defined in
[EATON-EPDU-MIB](https://github.com/librenms/librenms/blob/master/mibs/eaton/EATON-EPDU-MIB)
as `outletControlStatus`, `outletControlOffCmd` and `outletControlOnCmd`.

The `power_on()` handler switches off an already-powered outlet, waits five
seconds, and switches it on. This matches the old driver's default behavior.
If you used a different `power_on_delay`, adjust `time.sleep(5)` accordingly.

## 4. Run the webhook

In the same directory, configure the PDU address, its read-write SNMP community,
and a new token for callers of the webhook:

```bash
export PDU_ADDRESS=192.0.2.20
read -r -s -p 'PDU read-write SNMP community: ' SNMP_COMMUNITY
printf '\n'
export SNMP_COMMUNITY
export WEBHOOK_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
printf 'Save this token for MAAS: %s\n' "$WEBHOOK_TOKEN"
```

The SNMP community authenticates to the **PDU**; the token authenticates to the
**webhook**. They are different credentials. Keep both private. SNMP's `-c`
argument can also be visible to other local processes, so use a dedicated,
trusted webhook host.

Start the service as your normal, unprivileged user:

```bash
gunicorn --bind 192.0.2.10:8000 --workers 1 --threads 1 --timeout 60 \
  'eaton_webhook_example:create_app()'
```

Replace the bind address with the webhook host's actual management IP. Keep this
terminal running for the tutorial; Ctrl-C stops the service. The single worker
serializes requests so that outlet power sequences do not overlap. No changes
to the MAAS installation are needed. For an unattended installation, run this
same command under your service manager with the same environment variables.

From a rack controller, open another terminal and test the query endpoint. Enter
the token saved above:

```bash
read -r -s -p 'Webhook token: ' WEBHOOK_TOKEN
printf '\n'
curl --fail-with-body \
  -H "Authorization: Bearer $WEBHOOK_TOKEN" \
  http://192.0.2.10:8000/outlets/3/status
```

Expect `{"status":"running"}` or `{"status":"stopped"}`. HTTP 401 means the token
is wrong; 502 means the SNMP command failed or returned an unexpected state; 504
means it timed out. Check the PDU's SNMP access, community and supported OIDs
before continuing. Query after a timeout before retrying a power operation.

## 5. Point MAAS at the webhook

Open the test machine's power configuration in MAAS and change its power type to
**Webhook**. Enter:

| Field | Value |
| --- | --- |
| URI to power on the node | `http://192.0.2.10:8000/outlets/3/on` |
| URI to power off the node | `http://192.0.2.10:8000/outlets/3/off` |
| URI to query the node's power status | `http://192.0.2.10:8000/outlets/3/status` |
| Regex to confirm the node is on | `status.*\:.*running` |
| Regex to confirm the node is off | `status.*\:.*stopped` |
| Power token | The generated `WEBHOOK_TOKEN` |

Leave **Power user** and **Power password** empty. SSL verification has no effect
on these plain HTTP URLs; no certificate configuration is involved.
The URI address is the **webhook host**, not the PDU. Do not use `localhost`
unless the service runs on every rack controller that may manage the machine.

Alternatively, use an authenticated MAAS CLI profile. Replace `admin` and
`abc123` with your profile and machine system ID, and ensure `WEBHOOK_TOKEN`
contains the token from the previous step:

```bash
PROFILE=admin
SYSTEM_ID=abc123

maas "$PROFILE" machine update "$SYSTEM_ID" \
  power_type=webhook \
  power_parameters_power_on_uri=http://192.0.2.10:8000/outlets/3/on \
  power_parameters_power_off_uri=http://192.0.2.10:8000/outlets/3/off \
  power_parameters_power_query_uri=http://192.0.2.10:8000/outlets/3/status \
  power_parameters_power_on_regex='status.*\:.*running' \
  power_parameters_power_off_regex='status.*\:.*stopped' \
  power_parameters_power_user= \
  power_parameters_power_pass= \
  power_parameters_power_token="$WEBHOOK_TOKEN" \
  power_parameters_power_verify_ssl=y
```

For another server on the same PDU, use its outlet number in all three URLs.
The MAAS system ID and PDU outlet number are unrelated. This service does not
depend on MAAS's `System_Id` header; the URL identifies the outlet.

## 6. Power the test server through MAAS

These commands operate real hardware. Shut down any running OS safely before
cutting power, then exercise the integration:

```bash
maas "$PROFILE" machine query-power-state "$SYSTEM_ID"
maas "$PROFILE" machine power-off "$SYSTEM_ID"
# Wait for the action to finish, then query again: expect "off".
maas "$PROFILE" machine query-power-state "$SYSTEM_ID"
maas "$PROFILE" machine power-on "$SYSTEM_ID"
# Wait for the action to finish, then query again: expect "on".
maas "$PROFILE" machine query-power-state "$SYSTEM_ID"
```

MAAS now sends HTTP requests to your service instead of using its removed Eaton
driver. Your service translates those requests into SNMP operations on the PDU.
The same integration works with the UI's power actions.

## Adapt the example for another power driver

Keep the three HTTP endpoints and replace the hardware-specific functions:

- `query_power()`: read the real hardware state and return `running` or
  `stopped`. Treat an unreachable device or an unknown state as an error.
- `set_power()`: call your hardware's API, SDK or command-line tool. Use
  argument lists and timeouts for external commands, not shell interpolation.
- `power_on()`: use your hardware's normal power-on behavior. The off/wait/on
  sequence here is Eaton-specific, not a requirement of the Webhook driver.

For a non-PDU device, replace the outlet URL parameter with an appropriate
machine identifier and map it to configured devices in the service. Keep
hardware addresses and credentials on the service host rather than accepting
arbitrary commands or targets in HTTP requests.

The Webhook driver does not configure PXE boot order or discover chassis.
Configure network boot separately if required for commissioning and deployment.
