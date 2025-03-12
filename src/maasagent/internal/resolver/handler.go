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
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"math"
	"math/big"
	"net"
	"net/netip"
	"os"
	"slices"
	"strings"
	"time"

	"github.com/miekg/dns"
	"github.com/rs/zerolog/log"
)

const (
	attemptTimeout  = 5 * time.Second
	exchangeTimeout = 20 * time.Second
)

var (
	ErrInvalidResolvConf = errors.New("invalid resolv.conf")
	ErrNoAnswer          = errors.New("no answer received")
)

type ResolverClient interface {
	ExchangeContext(context.Context, *dns.Msg, string) (*dns.Msg, time.Duration, error)
}

type systemConfig struct {
	Nameservers   []netip.Addr
	SearchDomains []string
	EDNS0Enabled  bool
	Rotate        bool
	UseTCP        bool
	TrustAD       bool
}

type RecursiveHandler struct {
	systemResolvers      *systemConfig
	client               ResolverClient
	authoritativeServers []string
	// TODO add cache
}

func NewRecursiveHandler() *RecursiveHandler { // TODO pass in cache
	return &RecursiveHandler{
		client: &dns.Client{}, // TODO provide client config
	}
}

func (h *RecursiveHandler) SetUpstreams(resolvConf string, authServers []string) error {
	sysCfg, err := h.parseResolvConf(resolvConf)
	if err != nil {
		return err
	}

	h.authoritativeServers = authServers
	h.systemResolvers = sysCfg

	if h.systemResolvers.UseTCP {
		client, ok := h.client.(*dns.Client)
		if ok {
			client.Net = "tcp"
		}
	}

	return nil
}

func (h *RecursiveHandler) ServeDNS(w dns.ResponseWriter, r *dns.Msg) {
	ok := h.validateQuery(w, r)
	if !ok {
		return
	}

	resp := &dns.Msg{}

	r.CopyTo(resp)

	resp.Response = true

	for _, q := range r.Question {
		// TODO determine whether query is MAAS-authoritative, i.e the "recursive" part
		nameSplit := strings.Split(q.Name, ".")

		if len(nameSplit) == 1 {
			singleMsg := &dns.Msg{}
			singleMsg.Question = []dns.Question{q}

			msg, err := h.nonAuthoritativeQuery(singleMsg)

			if err != nil {
				log.Err(err).Send()

				h.srvFailResponse(w, r)

				return
			} else if msg != nil && msg.Rcode != dns.RcodeSuccess {
				for _, s := range h.systemResolvers.SearchDomains {
					m := &dns.Msg{}
					m.Question = []dns.Question{
						{
							Name:   dns.Fqdn(dns.Fqdn(q.Name) + s),
							Qtype:  q.Qtype,
							Qclass: q.Qclass,
						},
					}

					msg, err = h.nonAuthoritativeQuery(m)
					if err != nil {
						log.Err(err).Send()

						h.srvFailResponse(w, r)

						return
					}

					if msg.Rcode == dns.RcodeSuccess {
						break
					}
				}
			}

			if msg != nil {
				resp.Rcode = msg.Rcode
				resp.Answer = append(resp.Answer, msg.Answer...)
				resp.Ns = append(resp.Ns, msg.Ns...)
				resp.Extra = append(resp.Extra, msg.Extra...)
			}
		} else {
			m := &dns.Msg{}
			m.Question = []dns.Question{q}

			msg, err := h.nonAuthoritativeQuery(m)
			if err != nil {
				log.Err(err).Send()

				h.srvFailResponse(w, r)

				return
			}

			resp.Rcode = msg.Rcode
			resp.Answer = append(resp.Answer, msg.Answer...)
			resp.Ns = append(resp.Ns, msg.Ns...)
			resp.Extra = append(resp.Extra, msg.Extra...)
		}
	}

	if resp.Rcode == 0 {
		resp.Rcode = dns.RcodeSuccess
	}

	err := w.WriteMsg(resp)
	if err != nil {
		log.Err(err).Send()
	}
}

func (h *RecursiveHandler) validateQuery(w dns.ResponseWriter, r *dns.Msg) bool {
	errResp := &dns.Msg{}
	r.CopyTo(errResp)

	if (r.Opcode != dns.OpcodeQuery && r.Opcode != dns.OpcodeIQuery) || r.Response {
		log.Warn().Msgf("received a non-query from: %s", w.RemoteAddr().String())

		errResp.Response = true
		errResp.Rcode = dns.RcodeRefused

		err := w.WriteMsg(errResp)
		if err != nil {
			log.Err(err).Send()
		}

		return false
	}

	// we don't want to answer the following types of queries for either security
	// or functionality reasons
	for _, q := range r.Question {
		if q.Qclass == dns.ClassCHAOS || q.Qclass == dns.ClassNONE || q.Qclass == dns.ClassANY {
			log.Warn().Msgf("received a %s class query from: %s", dns.ClassToString[q.Qclass], w.RemoteAddr().String())

			errResp.Response = true
			errResp.Rcode = dns.RcodeRefused

			continue
		}

		if q.Qtype == dns.TypeAXFR || q.Qtype == dns.TypeIXFR {
			log.Warn().Msgf("received a %s from: %s", dns.TypeToString[q.Qtype], w.RemoteAddr().String())

			errResp.Response = true
			errResp.Rcode = dns.RcodeRefused

			continue
		}

		if q.Qtype == dns.TypeANY {
			log.Warn().Msgf("received a %s from: %s", dns.TypeToString[q.Qtype], w.RemoteAddr().String())

			errResp.Response = true
			// not implemented instead of refused,
			// as this is what most public resolvers use
			errResp.Rcode = dns.RcodeNotImplemented
		}
	}

	if errResp.Response { // only set true if there's a response to be written
		err := w.WriteMsg(errResp)
		if err != nil {
			log.Err(err).Send()
		}

		return false
	}

	return true
}

func (h *RecursiveHandler) srvFailResponse(w dns.ResponseWriter, r *dns.Msg) {
	errResp := &dns.Msg{}

	r.CopyTo(errResp)

	errResp.Response = true
	errResp.Rcode = dns.RcodeServerFailure

	err := w.WriteMsg(errResp)
	if err != nil {
		log.Err(err).Send()
	}
}

func (h *RecursiveHandler) nonAuthoritativeExchange(ctx context.Context, resolver netip.Addr, r *dns.Msg) (*dns.Msg, error) {
	var (
		cancel context.CancelFunc
		err    error
	)

	ctx, cancel = context.WithTimeout(ctx, attemptTimeout)
	defer cancel()

	if h.systemResolvers.EDNS0Enabled && !slices.ContainsFunc(r.Extra, checkForEDNS0Cookie) {
		var cookie string

		cookie, err = generateEDNS0Cookie()
		if err != nil {
			return nil, err
		}

		r.Extra = append(
			r.Extra,
			&dns.OPT{
				Hdr: dns.RR_Header{},
				Option: []dns.EDNS0{
					&dns.EDNS0_COOKIE{
						Code:   dns.EDNS0COOKIE,
						Cookie: cookie,
					},
				},
			},
		)
	}

	if h.systemResolvers.TrustAD {
		r.AuthenticatedData = true
	}

	if r.Id == 0 {
		max := big.NewInt(int64(math.MaxUint16))

		var id *big.Int

		for id == nil || id.Int64() > math.MaxUint16 {
			id, err = rand.Int(rand.Reader, max)
			if err != nil {
				return nil, err
			}
		}

		r.Id = uint16(id.Int64())
	}

	r.RecursionDesired = true

	msg, _, err := h.client.ExchangeContext(ctx, r, net.JoinHostPort(resolver.String(), "53"))

	return msg, err
}

func generateEDNS0Cookie() (string, error) {
	clientBytes := make([]byte, 8)

	_, err := rand.Read(clientBytes)
	if err != nil {
		return "", err
	}

	return hex.EncodeToString(clientBytes)[:16], nil
}

func checkForEDNS0Cookie(rr dns.RR) bool {
	opt, ok := rr.(*dns.OPT)
	if !ok {
		return false
	}

	for _, option := range opt.Option {
		_, ok := option.(*dns.EDNS0_COOKIE)
		if ok {
			return true
		}
	}

	return false
}

func (h *RecursiveHandler) nonAuthoritativeQuery(r *dns.Msg) (*dns.Msg, error) {
	ctx, cancel := context.WithTimeout(context.Background(), exchangeTimeout)
	defer cancel()

	for _, resolver := range h.systemResolvers.Nameservers {
		msg, err := h.nonAuthoritativeExchange(ctx, resolver, r)
		if err != nil {
			log.Err(err).Send()
		} else {
			return msg, nil
		}
	}

	return nil, ErrNoAnswer
}

func (h *RecursiveHandler) parseResolvConf(resolvConf string) (*systemConfig, error) {
	cfg := &systemConfig{}

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

			cfg.Nameservers = append(cfg.Nameservers, ip)

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

				cfg.SearchDomains = append(cfg.SearchDomains, dns.Fqdn(domain))
			}
		}

		if options, ok := strings.CutPrefix(line, "options"); ok {
			opts := strings.TrimSpace(options)

			if len(opts) == len(options) {
				return nil, fmt.Errorf(
					"%w: no space between \"options\" and set options",
					ErrInvalidResolvConf,
				)
			}

			optsList := strings.Split(opts, " ")

			// we only care about a subset of resolv.conf options,
			// see `man resolv.conf` for full list
			for _, opt := range optsList {
				switch opt {
				case "edns0":
					cfg.EDNS0Enabled = true
				case "use-vc":
					cfg.UseTCP = true
				case "trust-ad":
					cfg.TrustAD = true
				}
			}
		}
	}

	return cfg, nil
}
