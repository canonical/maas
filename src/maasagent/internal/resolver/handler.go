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
	"sync"
	"time"

	"github.com/miekg/dns"
	"github.com/rs/zerolog/log"
)

const (
	attemptTimeout  = 5 * time.Second
	exchangeTimeout = 20 * time.Second

	defaultConnPoolSize = 12
)

var (
	ErrInvalidResolvConf = errors.New("invalid resolv.conf")
	ErrNoAnswer          = errors.New("no answer received")
)

type resolverClient interface {
	Dial(string) (*dns.Conn, error)
	ExchangeContext(context.Context, *dns.Msg, string) (*dns.Msg, time.Duration, error)
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

type sessionMap struct {
	sessions map[string]*session
	lock     sync.RWMutex
}

// Load loads an existing session
func (s *sessionMap) Load(key string) *session {
	s.lock.RLock()
	defer s.lock.RUnlock()

	return s.sessions[key]
}

// Store stores a session
func (s *sessionMap) Store(key string, sess *session) {
	s.lock.Lock()
	defer s.lock.Unlock()

	s.sessions[key] = sess
}

// Delete deletes a session
func (s *sessionMap) Delete(key string) {
	s.lock.Lock()
	defer s.lock.Unlock()

	delete(s.sessions, key)
}

// ClearExpired removes all expired sessions
func (s *sessionMap) ClearExpired() {
	now := time.Now()

	s.lock.Lock()
	defer s.lock.Unlock()

	for k, v := range s.sessions {
		if v.Expired(now) {
			delete(s.sessions, k)
		}
	}
}

type exclusiveConn struct {
	conn *dns.Conn
	lock sync.Mutex
}

// Use acquires a lock on a connection for use with ExchangeConnWithContext()
func (e *exclusiveConn) Use(fn func(*dns.Conn)) {
	e.lock.Lock()
	defer e.lock.Unlock()

	fn(e.conn)
}

type connMap struct {
	conns map[netip.Addr][]*exclusiveConn
	lock  sync.Mutex
}

// Get fetches a connection for the given netip.Addr
func (c *connMap) Get(addr netip.Addr) (*exclusiveConn, bool) {
	c.lock.Lock()
	defer c.lock.Unlock()

	var conn *exclusiveConn

	conns, ok := c.conns[addr]
	if ok {
		if len(conns) == 0 {
			return nil, false
		}

		conn = conns[0]

		if len(conns) > 1 {
			c.conns[addr] = append(conns[1:], conn)
		}
	}

	return conn, ok
}

// Set sets a connection to the pool for a given netip.Addr
func (c *connMap) Set(addr netip.Addr, conn *dns.Conn) {
	c.lock.Lock()
	defer c.lock.Unlock()

	c.conns[addr] = append(c.conns[addr], &exclusiveConn{
		conn: conn,
	})
}

// Close closes all connections in the connection pool
func (c *connMap) Close() error {
	c.lock.Lock()
	defer c.lock.Unlock()

	for addr, cns := range c.conns {
		var err error

		for _, cn := range cns {
			cn.Use(func(conn *dns.Conn) {
				err = conn.Close()
			})

			if err != nil {
				return err
			}
		}

		delete(c.conns, addr)
	}

	return nil
}

type RecursiveHandlerOption func(*RecursiveHandler)

type RecursiveHandler struct {
	systemResolvers      *systemConfig
	sessionMap           *sessionMap
	conns                *connMap
	stats                *handlerStats
	recordCache          Cache
	client               resolverClient
	authoritativeServers []netip.Addr
	connPoolSize         int
}

// NewRecursiveHandler provides a constructor for a new handler for recursive queries
func NewRecursiveHandler(cache Cache, options ...RecursiveHandlerOption) *RecursiveHandler {
	r := &RecursiveHandler{
		sessionMap: &sessionMap{
			sessions: make(map[string]*session),
		},
		conns: &connMap{
			conns: make(map[netip.Addr][]*exclusiveConn),
		},
		stats:        &handlerStats{},
		connPoolSize: defaultConnPoolSize,
		recordCache:  cache,
		client:       &dns.Client{},
	}

	for _, option := range options {
		option(r)
	}

	return r
}

// SetUpstreams sets upstream connections for both authoritative and non-authoritative servers
func (h *RecursiveHandler) SetUpstreams(cfg *systemConfig, authServers []string) error {
	var err error

	h.systemResolvers = cfg

	if h.systemResolvers.UseTCP {
		client, ok := h.client.(*dns.Client)
		if ok {
			client.Net = "tcp"
		}
	}

	authAddrs := make([]netip.Addr, len(authServers))
	for i, server := range authServers {
		authAddrs[i], err = netip.ParseAddr(server)
		if err != nil {
			return err
		}

		for j := 0; j < h.connPoolSize; j++ {
			conn, err := h.client.Dial(net.JoinHostPort(server, "53"))
			if err != nil {
				return err
			}

			h.conns.Set(authAddrs[i], conn)

			h.stats.connPoolSize.Add(1)
		}
	}

	h.authoritativeServers = authAddrs

	for _, ns := range h.systemResolvers.Nameservers {
		if _, ok := h.conns.Get(ns); ok { // check for overlap with MAAS authoritative servers
			continue
		}

		for i := 0; i < h.connPoolSize; i++ {
			conn, err := h.client.Dial(net.JoinHostPort(ns.String(), "53"))
			if err != nil {
				return err
			}

			h.conns.Set(ns, conn)

			h.stats.connPoolSize.Add(1)
		}
	}

	return nil
}

// ClearExpiredSessions removes all expired sessions
func (h *RecursiveHandler) ClearExpiredSessions() {
	h.sessionMap.ClearExpired()
}

// Close closes all connections in the handler's connection pool
func (h *RecursiveHandler) Close() error {
	return h.conns.Close()
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
		if remoteSession.Expired(time.Now()) {
			h.sessionMap.Delete(sessionKey)
		}
	}()

	r.Response = true
	r.RecursionAvailable = true

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
			log.Err(err).Send()

			h.srvFailResponse(w, r)

			return
		}

		if nameserver != nil {
			msg, err = h.handleAuthoritative(q, remoteSession, nameserver)
			if err != nil {
				log.Err(err).Send()

				h.srvFailResponse(w, r)

				return
			}

			if msg.Rcode != dns.RcodeSuccess {
				r.Rcode = msg.Rcode

				err = w.WriteMsg(r)
				if err != nil {
					log.Err(err).Send()
				}

				return
			}

			// non-auth queries can still come back without an answer, but no error,
			// in this case often with an authority section, if this is the case,
			// we should check if there is an answer, and assume it's non-authoritative
			// if not
			if msg.Rcode == dns.RcodeSuccess && len(msg.Answer) > 0 {
				r.Answer = append(r.Answer, msg.Answer...)
				r.Ns = append(r.Ns, msg.Ns...)
				r.Extra = append(r.Extra, msg.Extra...)

				h.stats.authoritative.Add(1)

				continue
			}
		}

		if qstate.UseSearch() {
			msg, err = h.handleSearch(q)
			if err != nil {
				log.Err(err).Send()

				h.srvFailResponse(w, r)

				return
			}

			if msg != nil {
				r.Rcode = msg.Rcode
				r.Answer = append(r.Answer, msg.Answer...)
				r.Ns = append(r.Ns, msg.Ns...)
				r.Extra = append(r.Extra, msg.Extra...)

				h.stats.nonauthoritative.Add(1)
			}

			continue
		}

		msg, err = h.handleNonAuthoritative(q)
		if err != nil {
			log.Err(err).Send()

			h.srvFailResponse(w, r)

			return
		}

		if msg.Rcode != dns.RcodeSuccess {
			r.Rcode = msg.Rcode

			err = w.WriteMsg(r)
			if err != nil {
				log.Err(err).Send()
			}

			return
		}

		r.Answer = append(r.Answer, msg.Answer...)
		r.Ns = append(r.Ns, msg.Ns...)
		r.Extra = append(r.Extra, msg.Extra...)

		h.stats.nonauthoritative.Add(1)
	}

	err := w.WriteMsg(r)
	if err != nil {
		log.Err(err).Send()
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
	remoteSession.Reset()

	return h.authoritativeQuery(query, nameserver)
}

// getOrCreateSessions fetches a session for a remote address if one exists and creates one
// if not
func (h *RecursiveHandler) getOrCreateSession(key string, remoteAddr net.Addr) *session {
	remoteSession := h.sessionMap.Load(key)
	if remoteSession == nil {
		remoteSession = newSession(remoteAddr)

		h.sessionMap.Store(key, remoteSession)
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
			nsAddr, err = h.resolveAuthoritativeArbitraryName(
				context.Background(),
				nameserver.Ns,
			)
		}

		if err != nil || nameserver == nil { // if failed to find NS record's address or we haven't found one yet
			if err != nil {
				log.Debug().Msgf("retryable error: %s", err)
			}

			if authServerIdx == len(h.authoritativeServers) {
				return nil, ErrNoAnswer
			}

			nsAddr = h.authoritativeServers[authServerIdx]
			authServerIdx++
		}

		ns, err := h.getNS(label, nsAddr)
		if err != nil {
			log.Debug().Msgf("retryable err: %s", err)

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
	ctx, cancel := context.WithTimeout(context.Background(), exchangeTimeout)

	defer cancel()

	query := func(addr netip.Addr) (*dns.NS, error) {
		id, err := generateTransactionID()
		if err != nil {
			return nil, err
		}

		q := prepareQueryMessage(id, name, dns.TypeNS)

		resp, err := h.authoritativeExchange(ctx, addr, q)
		if err != nil {
			return nil, err
		}

		for _, answer := range resp.Answer {
			if ns, ok := answer.(*dns.NS); ok {
				return ns, nil
			}
		}

		// TODO cache Ns and Additional sections

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
			log.Debug().Msgf("retryable err: %s", err)

			continue
		}

		// TODO cache potential As/AAAAs returned in the Extras section
		return msg, nil
	}

	return nil, ErrNoAnswer
}

// queryAliasType handles the special logic for resolving CNAME and DNAME queries
func (h *RecursiveHandler) queryAliasType(query *dns.Msg, nameserver *dns.NS, remoteSession *session) (*dns.Msg, error) {
	for _, q := range query.Question {
		if q.Qtype == dns.TypeCNAME || q.Qtype == dns.TypeDNAME {
			alreadyQueried, err := remoteSession.NameAlreadyQueried(q.Name)
			if err != nil {
				return nil, err
			}

			if alreadyQueried {
				log.Warn().Msgf("detected a looping querying from %s", remoteSession.String())

				query.Response = true
				query.Rcode = dns.RcodeRefused

				return query, nil
			}

			err = remoteSession.StoreName(q.Name)
			if err != nil {
				return nil, err
			}
		}
	}

	return h.authoritativeQuery(query, nameserver)
}

// authoritativeQuery exchanges authoritative sub-queries
func (h *RecursiveHandler) authoritativeQuery(msg *dns.Msg, ns *dns.NS) (*dns.Msg, error) {
	ctx, cancel := context.WithTimeout(context.Background(), exchangeTimeout)
	defer cancel()

	nsAddr, err := h.resolveAuthoritativeArbitraryName(ctx, ns.Ns)
	if err != nil {
		return nil, err
	}

	return h.authoritativeExchange(ctx, nsAddr, msg)
}

// resolveAuthoritativeArbitraryName resolves a given name where we do not know if it is a CNAME, A or AAAA
func (h *RecursiveHandler) resolveAuthoritativeArbitraryName(ctx context.Context, addrStr string) (netip.Addr, error) {
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
			seen, err := sess.NameAlreadyQueried(addrStr)
			if err != nil {
				return netip.Addr{}, err
			} else if seen {
				return netip.Addr{}, ErrCNAMELoop
			}

			err = sess.StoreName(addrStr)
			if err != nil {
				return netip.Addr{}, err
			}
		}

		// not all should come back, but we should check
		// for each when only given a name
		msgs := []*dns.Msg{
			prepareQueryMessage(0, addrStr, dns.TypeCNAME), // id will be set at exchange
			prepareQueryMessage(0, addrStr, dns.TypeA),
			prepareQueryMessage(0, addrStr, dns.TypeAAAA),
		}

		for _, msg := range msgs {
			for _, server := range h.authoritativeServers {
				resp, err := h.authoritativeExchange(ctx, server, msg)
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
func (h *RecursiveHandler) authoritativeExchange(ctx context.Context, server netip.Addr, r *dns.Msg) (*dns.Msg, error) {
	ctx, cancel := context.WithTimeout(ctx, attemptTimeout)

	defer cancel()

	if r.Id == 0 {
		id, err := generateTransactionID()
		if err != nil {
			return nil, err
		}

		r.Id = id
	}

	return h.fetchAnswer(ctx, server, r)
}

// validateQuery ensures we only process valid queries
func (h *RecursiveHandler) validateQuery(w dns.ResponseWriter, r *dns.Msg) bool {
	remoteAddr := w.RemoteAddr().String()

	if r.Response || (r.Opcode != dns.OpcodeQuery && r.Opcode != dns.OpcodeIQuery) {
		log.Warn().Msgf("received a non-query from: %s", remoteAddr)

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
			log.Warn().Msgf("received a %s class query from: %s", dns.ClassToString[q.Qclass], remoteAddr)

			r.Response = true
			r.Rcode = dns.RcodeRefused

			continue
		}

		if q.Qtype == dns.TypeAXFR || q.Qtype == dns.TypeIXFR {
			log.Warn().Msgf("received a %s from: %s", dns.TypeToString[q.Qtype], remoteAddr)

			r.Response = true
			r.Rcode = dns.RcodeRefused

			continue
		}

		if q.Qtype == dns.TypeANY {
			log.Warn().Msgf("received a %s from: %s", dns.TypeToString[q.Qtype], remoteAddr)

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
func (h *RecursiveHandler) nonAuthoritativeExchange(ctx context.Context, resolver netip.Addr, r *dns.Msg) (*dns.Msg, error) {
	var err error

	ctx, cancel := context.WithTimeout(ctx, attemptTimeout)
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

	r.AuthenticatedData = h.systemResolvers.TrustAD

	if r.Id == 0 {
		r.Id, err = generateTransactionID()
		if err != nil {
			return nil, err
		}
	}

	r.RecursionDesired = true

	return h.fetchAnswer(ctx, resolver, r)
}

// fetchAnswer provides the logic necessary to fetch an answer from the given server at the netip.Addr
func (h *RecursiveHandler) fetchAnswer(ctx context.Context, server netip.Addr, r *dns.Msg) (*dns.Msg, error) {
	var cachedAnswers []dns.RR

	cachedMsg := r.Copy()

	for i, q := range cachedMsg.Question {
		rr, ok := h.getCachedRecordForQuestion(q)
		if !ok {
			continue
		}

		log.Debug().Msgf("using cached answer for %s %s", q.Name, dns.TypeToString[q.Qtype])

		cachedAnswers = append(cachedAnswers, rr)

		if len(cachedMsg.Question) == 1 {
			cachedMsg.Question = nil
			break
		}

		if i+1 < len(cachedMsg.Question) {
			cachedMsg.Question = append(cachedMsg.Question[:i], cachedMsg.Question[i+1:]...)
		} else {
			cachedMsg.Question = cachedMsg.Question[:i]
		}
	}

	var (
		msg *dns.Msg
		err error
	)

	if len(cachedMsg.Question) > 0 {
		if conn, ok := h.conns.Get(server); ok { // authoritative or resolvconf resolver
			conn.Use(func(c *dns.Conn) {
				msg, _, err = h.client.ExchangeWithConnContext(ctx, cachedMsg, c)
			})
		} else { // MAAS authoritative server returned a NS for a non-authoritative zone
			msg, _, err = h.client.ExchangeContext(ctx, cachedMsg, net.JoinHostPort(server.String(), "53"))
		}

		if err != nil {
			return nil, err
		}

		h.cacheResponse(msg)
	} else {
		msg = r.Copy()
	}

	msg.Answer = append(msg.Answer, cachedAnswers...)

	return msg, nil
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

// parseResolvConf parses and returns configuration for a resolv.conf at the
// give path
func parseResolvConf(resolvConf string) (*systemConfig, error) {
	cfg := &systemConfig{}

	//nolint:gosec // flags any file being opened via a variable
	f, err := os.Open(resolvConf)
	if err != nil {
		return nil, err
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
