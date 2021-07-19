#!/bin/sh

go vet ./... 2>&1 | grep -v \
    -e '^#' \
    -e 'internal/dhcp/service.go:46' \
    -e 'internal/dhcp/service.go:74' \
    -e 'internal/dhcp/service.go:102' \
    -e 'internal/dhcp/service.go:130'

# invert grep result
[ "$?" -ne "0" ]