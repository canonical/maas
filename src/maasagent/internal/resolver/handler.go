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
	"net"
	"net/netip"
	"os"
	"slices"
	"strings"
	"time"

	"github.com/miekg/dns"
	"github.com/rs/zerolog/log"
	"maas.io/core/src/maasagent/internal/connpool"
)

const (
	exchangeTimeout     = 20 * time.Second
	defaultConnPoolSize = 12
)

var (
	ErrInvalidResolvConf = errors.New("invalid resolv.conf")
	ErrNoAnswer          = errors.New("no answer received")
)

type client interface {
	Dial(string) (*dns.Conn, error)
	Exchange(*dns.Msg, string) (*dns.Msg, time.Duration, error)
	ExchangeContext(context.Context, *dns.Msg, string) (*dns.Msg, time.Duration, error)
	ExchangeWithConn(*dns.Msg, *dns.Conn) (*dns.Msg, time.Duration, error)
	ExchangeWithConnContext(context.Context, *dns.Msg, *dns.Conn) (*dns.Msg, time.Duration, error)
}

type systemConfig struct {
	Nameservers   []netip.Addr
	SearchDomains []string
	EDNS0Enabled  bool
	Rotate        bool
	UseTCP        bool
	TrustAD       bool
}

type RecursiveHandlerOption func(*RecursiveHandler)

type RecursiveHandler struct {
	recordCache          Cache
	client               client
	conns                conns
	authoritativeServers []netip.Addr
	systemConfig         systemConfig
	sessions             sessions
	stats                handlerStats
	connPoolSize         int
}

// NewRecursiveHandler provides a constructor for a new handler for recursive queries
func NewRecursiveHandler(cache Cache, options ...RecursiveHandlerOption) *RecursiveHandler {
	r := &RecursiveHandler{
		client:       &dns.Client{Timeout: exchangeTimeout},
		systemConfig: systemConfig{},
		sessions: sessions{
			m: make(map[string]*session),
		},
		conns: conns{
			m: make(map[netip.Addr]connpool.Pool),
		},
		stats:        handlerStats{},
		connPoolSize: defaultConnPoolSize,
		recordCache:  cache,
	}

	for _, option := range options {
		option(r)
	}

	return r
}

// SetUpstreams sets upstream connections for both authoritative and non-authoritative servers
func (h *RecursiveHandler) SetUpstreams(systemConfig systemConfig, authServers []netip.Addr) error {
	h.systemConfig = systemConfig
	h.authoritativeServers = authServers

	network := "udp"
	if h.systemConfig.UseTCP {
		network = "tcp"

		client, ok := h.client.(*dns.Client)
		if ok {
			client.Net = "tcp"
		}
	}

	for _, server := range slices.Concat(h.systemConfig.Nameservers, authServers) {
		// check for overlap with MAAS authoritative servers
		if _, ok := h.conns.Get(server); ok {
			continue
		}

		factory := func() (net.Conn, error) {
			return net.Dial(network, net.JoinHostPort(server.String(), "53"))
		}

		pool, err := connpool.NewChannelPool(h.connPoolSize, factory)
		if err != nil {
			return err
		}

		h.conns.Set(server, pool)
	}

	return nil
}

// ClearExpiredSessions removes all expired sessions
func (h *RecursiveHandler) ClearExpiredSessions() {
	h.sessions.ClearExpired()
}

// Close closes all connections in the handler's connection pool
func (h *RecursiveHandler) Close() {
	h.conns.Close()
}

// ServeDNS implements dns.Handler for the RecursiveHandler.
// It is the main entrypoint into all query handling.
func (h *RecursiveHandler) ServeDNS(w dns.ResponseWriter, r *dns.Msg) {
	h.stats.queries.Add(1)

	ok := h.validateQuery(w, r)
	if !ok {
		h.stats.invalid.Add(1)

		return
	}

	remoteAddr := w.RemoteAddr()
	sessionKey := sessionKeyFromRemoteAddr(remoteAddr)
	remoteSession := h.getOrCreateSession(sessionKey, remoteAddr)

	defer func() {
		if remoteSession.expired(time.Now()) {
			h.sessions.Delete(sessionKey)
		}
	}()

	r.Response = true
	r.RecursionAvailable = true

	// Only a single entry in AUTHORITY and ADDITIONAL sections should be returned
	uniqueNs := make(map[string]struct{})
	uniqueExtra := make(map[string]struct{})

	for _, q := range r.Question {
		q.Name = dns.Fqdn(q.Name)

		rr, ok := h.getCachedRecordForQuestion(q)
		if ok {
			r.Answer = append(r.Answer, rr)

			h.stats.fromCache.Add(1)

			continue
		}

		var msg *dns.Msg

		qstate := newQueryState(q.Name)

		nameserver, err := h.findRecursiveNS(qstate)
		if err != nil && !errors.Is(err, ErrNoAnswer) {
			log.Error().Err(err).Msg("Failed to find recursive NS")

			h.srvFailResponse(w, r)

			return
		}

		if nameserver != nil {
			msg, err = h.handleAuthoritative(q, remoteSession, nameserver)
			if err != nil {
				log.Error().Err(err).Msg("Failed to handle authoritative query")

				h.srvFailResponse(w, r)

				return
			}

			if msg.Rcode != dns.RcodeSuccess && msg.Rcode != dns.RcodeNameError {
				r.Rcode = msg.Rcode

				err = w.WriteMsg(r)
				if err != nil {
					log.Error().Err(err).Msg("Failed to send reply")
				}

				return
			}

			// non-auth queries can still come back without an answer, but no error,
			// in this case often with an authority section, if this is the case,
			// we should check if there is an answer, and assume it's non-authoritative
			// if not
			if msg.Rcode == dns.RcodeSuccess && len(msg.Answer) > 0 {
				r.Answer = append(r.Answer, msg.Answer...)

				appendUniqueRR(uniqueNs, &r.Ns, msg.Ns)
				appendUniqueRR(uniqueExtra, &r.Extra, msg.Extra)

				h.stats.authoritative.Add(1)

				continue
			}
		}

		if qstate.UseSearch() {
			msg, err = h.handleSearch(q)
			if err != nil {
				log.Error().Err(err).Msg("Failed querying search domain")

				h.srvFailResponse(w, r)

				return
			}

			if msg != nil {
				r.Rcode = msg.Rcode
				r.Answer = append(r.Answer, msg.Answer...)

				appendUniqueRR(uniqueNs, &r.Ns, msg.Ns)
				appendUniqueRR(uniqueExtra, &r.Extra, msg.Extra)

				h.stats.nonauthoritative.Add(1)
			}

			continue
		}

		msg, err = h.handleNonAuthoritative(q)
		if err != nil {
			log.Error().Err(err).Msg("Failed non-authoritative querying")

			h.srvFailResponse(w, r)

			return
		}

		if msg.Rcode != dns.RcodeSuccess {
			r.Rcode = msg.Rcode

			err = w.WriteMsg(r)
			if err != nil {
				log.Error().Err(err).Msg("Failed to send reply")
			}

			return
		}

		r.Answer = append(r.Answer, msg.Answer...)

		appendUniqueRR(uniqueNs, &r.Ns, msg.Ns)
		appendUniqueRR(uniqueExtra, &r.Extra, msg.Extra)

		h.stats.nonauthoritative.Add(1)
	}

	err := w.WriteMsg(r)
	if err != nil {
		log.Error().Err(err).Msg("Failed to send reply")
	}
}

// appendUniqueRR is used to append RR to the result only if it was not met before.
// Tracking of previous occurrences happens via map[string]struct{}
func appendUniqueRR(seen map[string]struct{}, result *[]dns.RR, rrs []dns.RR) {
	for _, rr := range rrs {
		s := rr.String()
		if _, ok := seen[s]; ok {
			continue
		}

		*result = append(*result, rr)
		seen[s] = struct{}{}
	}
}

// handleNonAuthoritative handles subqueries for a non-authoritative query
func (h *RecursiveHandler) handleNonAuthoritative(q dns.Question) (*dns.Msg, error) {
	m := &dns.Msg{}
	m.Question = []dns.Question{q}

	return h.nonAuthoritativeQuery(m)
}

// handleSearch handles querying a search domain list for a non-authoritative query
func (h *RecursiveHandler) handleSearch(q dns.Question) (*dns.Msg, error) {
	singleMsg := &dns.Msg{}
	singleMsg.Question = []dns.Question{q}

	msg, err := h.nonAuthoritativeQuery(singleMsg)

	if err != nil {
		return nil, err
	}

	if msg != nil && msg.Rcode == dns.RcodeSuccess {
		return msg, nil
	}

	for _, s := range h.systemConfig.SearchDomains {
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
			return nil, err
		}

		if msg.Rcode == dns.RcodeSuccess {
			break
		}
	}

	return msg, nil
}

// handleAuthoritative handles authoritative queries
func (h *RecursiveHandler) handleAuthoritative(q dns.Question, remoteSession *session, nameserver *dns.NS) (*dns.Msg, error) {
	query := &dns.Msg{Question: []dns.Question{q}}

	if q.Qtype == dns.TypeCNAME || q.Qtype == dns.TypeDNAME {
		return h.queryAliasType(query, nameserver, remoteSession)
	}

	// we're not querying a CNAME / DNAME, so if there was a chain, it finished
	remoteSession.reset()

	return h.authoritativeQuery(query, nameserver)
}

// getOrCreateSessions fetches a session for a remote address if one exists and creates one
// if not
func (h *RecursiveHandler) getOrCreateSession(key string, remoteAddr net.Addr) *session {
	remoteSession := h.sessions.Load(key)
	if remoteSession == nil {
		remoteSession = newSession(remoteAddr)

		h.sessions.Store(key, remoteSession)
	}

	return remoteSession
}

// findRecursiveNS recursively finds the authoritative nameserver for a given name
func (h *RecursiveHandler) findRecursiveNS(qstate *queryState) (*dns.NS, error) {
	var (
		authServerIdx int
		label         string
	)

	ok := true

	for ok {
		label, ok = qstate.NextLabel()
		label = dns.Fqdn(label)
		nameserver := qstate.Nameserver()

		var (
			nsAddr netip.Addr
			err    error
		)

		if nameserver != nil {
			nsAddr, err = h.resolveAuthoritativeArbitraryName(nameserver.Ns)
		}

		if err != nil || nameserver == nil { // if failed to find NS record's address or we haven't found one yet
			if err != nil {
				log.Debug().Err(err).Msgf("Retryable error")
			}

			if authServerIdx == len(h.authoritativeServers) {
				return nil, ErrNoAnswer
			}

			nsAddr = h.authoritativeServers[authServerIdx]
			authServerIdx++
		}

		ns, err := h.getNS(label, nsAddr)
		if err != nil {
			log.Debug().Err(err).Msgf("Retryable error")

			continue
		}

		qstate.SetLastResponse(ns)

		if ns == nil && nameserver != nil { // found most specific NS
			break
		}
	}

	return qstate.Nameserver(), nil
}

// getNS fetches the NS record for a given name
func (h *RecursiveHandler) getNS(name string, nameserver netip.Addr) (*dns.NS, error) {
	query := func(addr netip.Addr) (*dns.NS, error) {
		id, err := generateTransactionID()
		if err != nil {
			return nil, err
		}

		q := prepareQueryMessage(id, name, dns.TypeNS)

		resp, err := h.authoritativeExchange(addr, q)
		if err != nil {
			return nil, err
		}

		for _, answer := range resp.Answer {
			if ns, ok := answer.(*dns.NS); ok {
				return ns, nil
			}
		}

		return nil, ErrNoAnswer
	}

	if nameserver.IsValid() {
		resp, err := query(nameserver)
		if err != nil && !errors.Is(err, ErrNoAnswer) {
			return nil, err
		}

		if resp != nil {
			return resp, nil
		}
	}

	// fallback to local servers in the event nameserver was possibly a forwarded external record
	// and NXDOMAIN's or there was no namserver provided
	for _, server := range h.authoritativeServers {
		msg, err := query(server)
		if err != nil {
			log.Debug().Err(err).Msgf("Retryable error")

			continue
		}

		return msg, nil
	}

	return nil, ErrNoAnswer
}

// queryAliasType handles the special logic for resolving CNAME and DNAME queries
func (h *RecursiveHandler) queryAliasType(query *dns.Msg, nameserver *dns.NS, remoteSession *session) (*dns.Msg, error) {
	for _, q := range query.Question {
		if q.Qtype == dns.TypeCNAME || q.Qtype == dns.TypeDNAME {
			name, err := remoteSession.format(q.Name)
			if err != nil {
				return nil, err
			}

			alreadyQueried := remoteSession.contains(name)

			if alreadyQueried {
				log.Warn().Msgf("Detected a looping querying from %s", remoteSession.String())

				query.Response = true
				query.Rcode = dns.RcodeRefused

				return query, nil
			}

			remoteSession.add(name)
		}
	}

	return h.authoritativeQuery(query, nameserver)
}

// authoritativeQuery exchanges authoritative sub-queries
func (h *RecursiveHandler) authoritativeQuery(msg *dns.Msg, ns *dns.NS) (*dns.Msg, error) {
	nsAddr, err := h.resolveAuthoritativeArbitraryName(ns.Ns)
	if err != nil {
		return nil, err
	}

	return h.authoritativeExchange(nsAddr, msg)
}

// resolveAuthoritativeArbitraryName resolves a given name where we do not know if it is a CNAME, A or AAAA
func (h *RecursiveHandler) resolveAuthoritativeArbitraryName(addrStr string) (netip.Addr, error) {
	qstate := newQueryState(addrStr)

	// create session for self, addr just needs to be something we wont see real traffic from
	sess := newSession(&net.UDPAddr{IP: net.ParseIP("0.0.0.0"), Port: 0})

outerLoop:
	for {
		addr, err := netip.ParseAddr(addrStr) // attempt to parse name if it is an IP already
		if err == nil {
			return addr, nil
		}

		if addrStr != "." {
			name, err := sess.format(addrStr)
			if err != nil {
				return netip.Addr{}, err
			}

			seen := sess.contains(name)
			if seen {
				return netip.Addr{}, ErrCNAMELoop
			}

			sess.add(name)
		}

		// not all should come back, but we should check
		// for each when only given a name
		msgs := []*dns.Msg{
			prepareQueryMessage(0, addrStr, dns.TypeA),
			prepareQueryMessage(0, addrStr, dns.TypeAAAA),
			prepareQueryMessage(0, addrStr, dns.TypeCNAME), // id will be set at exchange
		}

		for _, msg := range msgs {
			for _, server := range h.authoritativeServers {
				resp, err := h.authoritativeExchange(server, msg)
				if err != nil {
					log.Err(err).Send()

					continue
				}

				if resp.Rcode != dns.RcodeSuccess {
					continue
				}

				// combine answer and extra as some servers (the root server in particular)
				// will return A / AAAA in the extra section for its servers
				for i, answer := range append(resp.Answer, resp.Extra...) {
					if answer.Header().Name != addrStr {
						continue
					}

					switch a := answer.(type) {
					case *dns.CNAME:
						if i < len(resp.Answer)-1 {
							continue
						}

						addrStr = a.Target

						qstate.SetLastResponse(a)

						continue outerLoop
					case *dns.A:
						return netip.AddrFrom4([4]byte(a.A.To4())), nil
					case *dns.AAAA:
						return netip.AddrFrom16([16]byte(a.AAAA)), nil
					}
				}
			}
		}

		return netip.Addr{}, ErrNoAnswer
	}
}

// authoritativeExchange sets the header values for authoritative subqueries and exchanges the subquery for a response
func (h *RecursiveHandler) authoritativeExchange(server netip.Addr, r *dns.Msg) (*dns.Msg, error) {
	if r.Id == 0 {
		id, err := generateTransactionID()
		if err != nil {
			return nil, err
		}

		r.Id = id
	}

	return h.fetchAnswer(server, r)
}

// validateQuery ensures we only process valid queries
func (h *RecursiveHandler) validateQuery(w dns.ResponseWriter, r *dns.Msg) bool {
	remoteAddr := w.RemoteAddr().String()

	if r.Response || (r.Opcode != dns.OpcodeQuery && r.Opcode != dns.OpcodeIQuery) {
		log.Warn().Msgf("Received a non-query from: %s", remoteAddr)

		r.Response = true
		r.Rcode = dns.RcodeRefused

		err := w.WriteMsg(r)
		if err != nil {
			log.Err(err).Send()
		}

		return false
	}

	// we don't want to answer the following types of queries for either security
	// or functionality reasons
	for _, q := range r.Question {
		if q.Qclass == dns.ClassCHAOS || q.Qclass == dns.ClassNONE || q.Qclass == dns.ClassANY {
			log.Warn().Msgf("Received a %s class query from: %s", dns.ClassToString[q.Qclass], remoteAddr)

			r.Response = true
			r.Rcode = dns.RcodeRefused

			continue
		}

		if q.Qtype == dns.TypeAXFR || q.Qtype == dns.TypeIXFR {
			log.Warn().Msgf("Received a %s from: %s", dns.TypeToString[q.Qtype], remoteAddr)

			r.Response = true
			r.Rcode = dns.RcodeRefused

			continue
		}

		if q.Qtype == dns.TypeANY {
			log.Warn().Msgf("Received a %s from: %s", dns.TypeToString[q.Qtype], remoteAddr)

			r.Response = true
			// not implemented instead of refused,
			// as this is what most public resolvers use
			r.Rcode = dns.RcodeNotImplemented
		}
	}

	if r.Response { // only set true if there's a response to be written
		err := w.WriteMsg(r)
		if err != nil {
			log.Err(err).Send()
		}

		return false
	}

	return true
}

// srvFailResponse sends a servfail to the client in the event of an error
func (h *RecursiveHandler) srvFailResponse(w dns.ResponseWriter, r *dns.Msg) {
	h.stats.srvFail.Add(1)

	r.Response = true
	r.Rcode = dns.RcodeServerFailure

	err := w.WriteMsg(r)
	if err != nil {
		log.Err(err).Send()
	}
}

// nonAuhtoritativeExchange exchanges subqueries with the nameserver(s) configured in resolv.conf
func (h *RecursiveHandler) nonAuthoritativeExchange(resolver netip.Addr, r *dns.Msg) (*dns.Msg, error) {
	var err error

	if h.systemConfig.EDNS0Enabled && !slices.ContainsFunc(r.Extra, checkForEDNS0Cookie) {
		var cookie string

		cookie, err = generateEDNS0Cookie()
		if err != nil {
			return nil, err
		}

		r.Extra = append(
			r.Extra,
			&dns.OPT{
				Hdr: dns.RR_Header{
					Name:     ".",
					Rrtype:   dns.TypeOPT,
					Class:    dns.ClassINET,
					Ttl:      30,
					Rdlength: 8,
				},
				Option: []dns.EDNS0{
					&dns.EDNS0_COOKIE{
						Code:   dns.EDNS0COOKIE,
						Cookie: cookie,
					},
				},
			},
		)
	}

	r.AuthenticatedData = h.systemConfig.TrustAD

	if r.Id == 0 {
		r.Id, err = generateTransactionID()
		if err != nil {
			return nil, err
		}
	}

	r.RecursionDesired = true

	return h.fetchAnswer(resolver, r)
}

// fetchAnswer provides the logic necessary to fetch an answer from the given server at the netip.Addr
func (h *RecursiveHandler) fetchAnswer(server netip.Addr, r *dns.Msg) (*dns.Msg, error) {
	var cachedAnswers []dns.RR

	cachedMsg := r.Copy()

	for i, q := range cachedMsg.Question {
		rr, ok := h.getCachedRecordForQuestion(q)
		if !ok {
			continue
		}

		log.Debug().Msgf("Using cached answer for %q %q", q.Name, dns.TypeToString[q.Qtype])

		cachedAnswers = append(cachedAnswers, rr)

		if len(cachedMsg.Question) == 1 {
			cachedMsg.Question = nil
			break
		}

		if i+1 < len(cachedMsg.Question) {
			cachedMsg.Question = slices.Delete(cachedMsg.Question, i, i+1)
		} else {
			cachedMsg.Question = cachedMsg.Question[:i]
		}
	}

	var (
		err   error
		conn  net.Conn
		wconn *connpool.Conn
	)

	if len(cachedMsg.Question) > 0 {
		// authoritative or resolvconf resolver
		if pool, ok := h.conns.Get(server); ok {
			conn, err = pool.Get()
			if err != nil {
				return nil, err
			}

			if wconn, ok = conn.(*connpool.Conn); !ok {
				return nil, fmt.Errorf("the type should be \"*connpool.Conn\"")
			}

			// When using ExchangeWithConn, the provided net.Conn will be asserted to
			// ensure it is a net.PacketConn (for UDP). Since out net.Conn connection
			// is wrapped with connpool.Conn the mentioned type assertion will fail and
			// UDP  will be incorrectly identified. To solve this issue we pass the
			// underlying embedded net.Conn, but calling a Close() on a wrapper.
			// information is being lost
			r, _, err = h.client.ExchangeWithConn(cachedMsg, &dns.Conn{Conn: wconn.Conn})
			if err != nil {
				log.Debug().Msgf("Connection %s removed from pool", server.String())
				wconn.MarkUnusable()
			}

			if err := conn.Close(); err != nil { //nolint:govet // false positive shadow
				log.Warn().Err(err).Msgf("Cannot return connection back to the pool")
			}
		} else { // MAAS authoritative server returned a NS for a non-authoritative zone
			r, _, err = h.client.Exchange(cachedMsg, net.JoinHostPort(server.String(), "53"))
		}

		if err != nil {
			return nil, err
		}

		h.cacheResponse(r)
	}

	r.Answer = append(r.Answer, cachedAnswers...)

	return r, nil
}

// cacheResponse caches records returned in a response
func (h *RecursiveHandler) cacheResponse(msg *dns.Msg) {
	for _, answer := range msg.Answer {
		h.recordCache.Set(answer)
	}

	for _, ns := range msg.Ns {
		h.recordCache.Set(ns)
	}

	for _, extra := range msg.Extra {
		h.recordCache.Set(extra)
	}
}

// getCachedRecordForQuestion checks the cache for a record corresponding to the given question
func (h *RecursiveHandler) getCachedRecordForQuestion(q dns.Question) (dns.RR, bool) {
	return h.recordCache.Get(q.Name, q.Qtype)
}

// preparseQueryMessage creates a full *dns.Msg for a given name and type
func prepareQueryMessage(id uint16, name string, qtype uint16) *dns.Msg {
	return &dns.Msg{
		MsgHdr: dns.MsgHdr{
			Id:     id,
			Opcode: dns.OpcodeQuery,
		},
		Question: []dns.Question{
			{
				Name:   name,
				Qtype:  qtype,
				Qclass: dns.ClassINET,
			},
		},
	}
}

// generateTransactionID generates an ID for a *dns.Msg
func generateTransactionID() (uint16, error) {
	var b [2]byte

	//nolint:errcheck,gosec // rand.Read() never returns an error
	rand.Read(b[:])

	return uint16(b[0])<<8 | uint16(b[1]), nil
}

// generateEDNS0Cookie creates a cookie to be used in non-authoritative
// queries when EDNS is enabled.
func generateEDNS0Cookie() (string, error) {
	clientBytes := make([]byte, 8)

	//nolint:errcheck,gosec // rand.Read() never returns an error
	rand.Read(clientBytes)

	return hex.EncodeToString(clientBytes)[:16], nil
}

// checkForEDNS0Cookie checks if a given record is a EDNS cookie
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

// nonAuthoritativeQuery queries the nameserver(s) configured in resolv.conf for a given query
func (h *RecursiveHandler) nonAuthoritativeQuery(r *dns.Msg) (*dns.Msg, error) {
	for _, resolver := range h.systemConfig.Nameservers {
		msg, err := h.nonAuthoritativeExchange(resolver, r)
		if err != nil {
			log.Err(err).Send()
		} else {
			return msg, nil
		}
	}

	return nil, ErrNoAnswer
}

// parseResolvConf parses and returns configuration for a resolv.conf at the
// give path
func parseResolvConf(resolvConf string) (systemConfig, error) {
	cfg := systemConfig{}

	//nolint:gosec // flags any file being opened via a variable
	f, err := os.Open(resolvConf)
	if err != nil {
		return cfg, err
	}

	//nolint:errcheck // ok to skip error check here
	defer f.Close()

	scanner := bufio.NewScanner(f)

	for scanner.Scan() {
		line := scanner.Text()

		// remove comments
		line, _, _ = strings.Cut(line, "#")
		line = strings.TrimSpace(line)

		if nameserver, ok := strings.CutPrefix(line, "nameserver"); ok {
			ns := strings.TrimSpace(nameserver)
			if len(ns) == len(nameserver) {
				return cfg, fmt.Errorf(
					"%w: no space between \"nameserver\" and addresses",
					ErrInvalidResolvConf,
				)
			}

			ip, err := netip.ParseAddr(ns)
			if err != nil {
				return cfg, fmt.Errorf("error parsing nameserver address: %w", err)
			}

			cfg.Nameservers = append(cfg.Nameservers, ip)

			continue // no need to check this line for search domains
		}

		if search, ok := strings.CutPrefix(line, "search"); ok {
			domains := strings.TrimSpace(search)
			if len(domains) == len(search) {
				return cfg, fmt.Errorf(
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
				return cfg, fmt.Errorf(
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
