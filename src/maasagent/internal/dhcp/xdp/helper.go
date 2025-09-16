// Copyright (c) 2025 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

package xdp

import (
	"github.com/cilium/ebpf"
	"github.com/cilium/ebpf/rlimit"
	"github.com/rs/zerolog/log"
)

//go:generate go run github.com/cilium/ebpf/cmd/bpf2go -makebase "$MAKEDIR" -tags linux bpf xdp.c -- -I../../ebpf/include

type BpfDHCPData struct {
	bpfDhcpData
}

type Program struct {
	objs bpfObjects
}

func New() *Program {
	return &Program{
		objs: bpfObjects{},
	}
}

func (p *Program) Load() error {
	err := rlimit.RemoveMemlock()
	if err != nil {
		log.Warn().Err(err).Msg("unable to set rlimit, continuing with default")
	}

	return loadBpfObjects(&p.objs, nil)
}

func (p *Program) Func() *ebpf.Program {
	return p.objs.XdpProgFunc
}

func (p *Program) Queue() *ebpf.Map {
	return p.objs.DhcpQueue
}

func (p *Program) Close() error {
	return p.objs.Close()
}
