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

package resolver

import (
	"bufio"
	"errors"
	"fmt"
	"net/netip"
	"os"
	"strings"

	"github.com/miekg/dns"
)

var (
	ErrInvalidResolvConf = errors.New("invalid resolv.conf")
)

type systemConfig struct {
	Nameservers   []netip.Addr
	SearchDomains []string
}

type RecursiveHandler struct {
	systemResolvers      *systemConfig
	authoritativeServers []string
	// TODO add cache
}

func NewRecursiveHandler() *RecursiveHandler { // TODO pass in cache
	return &RecursiveHandler{}
}

func (h *RecursiveHandler) SetUpstreams(resolvConf string, authServers []string) error {
	sysCfg, err := h.parseResolvConf(resolvConf)
	if err != nil {
		return err
	}

	h.authoritativeServers = authServers
	h.systemResolvers = sysCfg

	return nil
}

func (h *RecursiveHandler) ServeDNS(w dns.ResponseWriter, r *dns.Msg) {
	// TODO handle queries
}

func (h *RecursiveHandler) parseResolvConf(resolvConf string) (*systemConfig, error) {
	var (
		resolvers     []netip.Addr
		searchDomains []string
	)

	//nolint:gosec // flags any file being opened via a variable
	f, err := os.Open(resolvConf)
	if err != nil {
		return nil, err
	}

	scanner := bufio.NewScanner(f)

	for scanner.Scan() {
		line := scanner.Text()

		// remove comments
		line, _, _ = strings.Cut(line, "#")
		line = strings.TrimSpace(line)

		if nameserver, ok := strings.CutPrefix(line, "nameserver"); ok {
			ns := strings.TrimSpace(nameserver)
			if len(ns) == len(nameserver) {
				return nil, fmt.Errorf(
					"%w: no space between \"nameserver\" and addresses",
					ErrInvalidResolvConf,
				)
			}

			ip, err := netip.ParseAddr(ns)
			if err != nil {
				return nil, fmt.Errorf("error parsing nameserver address: %w", err)
			}

			resolvers = append(resolvers, ip)

			continue // no need to check this line for search domains
		}

		if search, ok := strings.CutPrefix(line, "search"); ok {
			domains := strings.TrimSpace(search)
			if len(domains) == len(search) {
				return nil, fmt.Errorf(
					"%w: no space between \"search\" and domains",
					ErrInvalidResolvConf,
				)
			}

			for len(domains) > 0 {
				domain := domains

				idx := strings.IndexAny(domain, "\t")
				if idx == -1 {
					idx = strings.IndexAny(domain, " ")
				}

				if idx != -1 {
					domain = domain[:idx]
					domains = strings.TrimSpace(domains[idx+1:])
				} else {
					domains = ""
				}

				searchDomains = append(searchDomains, dns.Fqdn(domain))
			}
		}
	}

	return &systemConfig{
		Nameservers:   resolvers,
		SearchDomains: searchDomains,
	}, nil
}
