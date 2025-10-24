#!/usr/bin/env bash
set -euo pipefail

REAL_CN="Good Agent"
FAKE_CN="Bad Agent"

CA_KEY="ca.key"
CA_CERT="ca.pem"
SERVER_KEY="server.key"
SERVER_CSR="server.csr"
SERVER_CERT="server.pem"
CLIENT_KEY="client.key"
CLIENT_CSR="client.csr"
CLIENT_CERT="client.pem"

FAKE_CA_KEY="fake_ca.key"
FAKE_CA_CERT="fake_ca.pem"
FAKE_CLIENT_KEY="fake_client.key"
FAKE_CLIENT_CSR="fake_client.csr"
FAKE_CLIENT_CERT="fake_client.pem"

# CA private key
openssl genrsa -out "$CA_KEY" 2048

# Self signed certificate
openssl req -x509 -new -nodes \
    -key "$CA_KEY" \
    -sha256 \
    -days 365000 \
    -subj "/CN=Test APP" \
    -out "$CA_CERT"

# Server private key
openssl genrsa -out "$SERVER_KEY" 2048
# Server CSR
openssl req -new -key "$SERVER_KEY" -out "$SERVER_CSR" -subj "/CN=localhost"
# Sign the server CSR with the CA
openssl x509 -req -in "$SERVER_CSR" \
    -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial \
    -out "$SERVER_CERT" -days 365000 -sha256 \
    -extfile <(printf "subjectAltName=DNS:localhost")

# Client private key
openssl genrsa -out "$CLIENT_KEY" 2048
# Client CSR
openssl req -new -key "$CLIENT_KEY" -out "$CLIENT_CSR" -subj "/CN=$REAL_CN"
# Sign the client CSR with the CA
openssl x509 -req -in "$CLIENT_CSR" \
    -CA "$CA_CERT" -CAkey "$CA_KEY" -CAcreateserial \
    -out "$CLIENT_CERT" -days 365000 -sha256

# Malicious CA private key
openssl genrsa -out "$FAKE_CA_KEY" 2048
# Malicious self signed certificate
openssl req -x509 -new -nodes \
    -key "$FAKE_CA_KEY" \
    -sha256 \
    -days 365000 \
    -subj "/CN=Fake Test APP" \
    -out "$FAKE_CA_CERT"

# Malicious client private key
openssl genrsa -out "$FAKE_CLIENT_KEY" 2048
# Malicious client CSR
openssl req -new -key "$FAKE_CLIENT_KEY" -out "$FAKE_CLIENT_CSR" -subj "/CN=$FAKE_CN"
# Sign the malicious client CSR with the malicious CA
openssl x509 -req -in "$FAKE_CLIENT_CSR" \
    -CA "$FAKE_CA_CERT" -CAkey "$FAKE_CA_KEY" -CAcreateserial \
    -out "$FAKE_CLIENT_CERT" -days 365000 -sha256

# Cleanup
rm -f "$SERVER_CSR" "$CLIENT_CSR" "$FAKE_CLIENT_CSR" "$CA_KEY" ca.srl fake_ca.srl
