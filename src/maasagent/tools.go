//go:build tools

package main

import (
	_ "github.com/cilium/ebpf/cmd/bpf2go"
	_ "golang.org/x/tools/cmd/stringer"
)
