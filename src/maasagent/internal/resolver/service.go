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
	"context"
	"errors"
	"net"
	"time"

	"github.com/miekg/dns"
	tworkflow "go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/workflow"
)

const (
	defaultResolvConfPath = "/etc/resolv.conf"
)

var (
	ErrInvalidBindIP = errors.New("provided bind value is not a valid IP")
)

var (
	RackBindActive = true // public to be able to overriden by the compiler for testing
)

type Handler interface {
	dns.Handler
	SetUpstreams(string, []string) error
	ClearExpiredSessions()
	Close() error
}

type ResolverService struct {
	handler              Handler
	sessionTicker        *time.Ticker
	fatal                chan error
	resolvConfPath       string
	authoritativeServers []string
	bindIPs              []string
	// in order to not conflict with systemd-resolved, we need
	// to listen on all other IPs in subnets with DNS enabled,
	// so for each IP the resolver is bound to we create a
	// TCP listener or UDP connection
	frontendServers []*dns.Server
}

type ResolverServiceOption func(*ResolverService)

type GetResolverConfigParam struct {
	SystemID string `json:"system_id"`
	UseBind  bool   `json:"use_bind"`
}

type GetResolverConfigResult struct {
	AuthoritativeIPs []string `json:"authoritative_ips"`
	BindIPs          []string `json:"bind_ips"`
	Enabled          bool     `json:"enabled"`
}

func NewResolverService(handler Handler, options ...ResolverServiceOption) *ResolverService {
	s := &ResolverService{
		handler:        handler,
		fatal:          make(chan error),
		resolvConfPath: defaultResolvConfPath,
		sessionTicker:  time.NewTicker(sessionTTL),
	}

	for _, opt := range options {
		opt(s)
	}

	return s
}

func WithResolvConf(path string) ResolverServiceOption {
	return func(s *ResolverService) {
		s.resolvConfPath = path
	}
}

func (s *ResolverService) ConfigurationWorkflows() map[string]any {
	return map[string]any{"configure-resolver-service": s.configure}
}

func (s *ResolverService) ConfigurationActivities() map[string]any {
	return map[string]any{}
}

func (s *ResolverService) configure(ctx tworkflow.Context, systemID string) error {
	var resolverConfigResult GetResolverConfigResult

	log := tworkflow.GetLogger(ctx)
	log.Info("Configuring resolver-service")

	if err := tworkflow.ExecuteActivity(
		tworkflow.WithActivityOptions(
			ctx,
			tworkflow.ActivityOptions{
				TaskQueue:              "region",
				ScheduleToCloseTimeout: 60 * time.Second,
			},
		),
		"get-resolver-config",
		GetResolverConfigParam{SystemID: systemID, UseBind: RackBindActive},
	).Get(ctx, &resolverConfigResult); err != nil {
		return err
	}

	if !resolverConfigResult.Enabled {
		log.Info("resolver-service is not enabled")

		if len(s.frontendServers) > 0 {
			return workflow.RunAsLocalActivity(ctx, func(ctx context.Context) error {
				return s.stop(ctx)
			})
		}

		return nil
	}

	s.authoritativeServers = resolverConfigResult.AuthoritativeIPs
	s.bindIPs = resolverConfigResult.BindIPs

	if err := workflow.RunAsLocalActivity(ctx, func(ctx context.Context) error {
		if err := s.handler.SetUpstreams(
			s.resolvConfPath,
			s.authoritativeServers,
		); err != nil {
			return err
		}

		if len(s.frontendServers) > 0 {
			if err := s.stop(ctx); err != nil {
				return err
			}
		}

		for _, ipStr := range s.bindIPs {
			var (
				tcpNet string
				udpNet string
			)

			ip := net.ParseIP(ipStr)

			if ip == nil {
				return ErrInvalidBindIP
			}

			if ip4 := ip.To4(); ip4 != nil {
				ip = ip4
				tcpNet = "tcp4"
				udpNet = "udp4"
			} else {
				tcpNet = "tcp6"
				udpNet = "udp6"
			}

			tcpServer := &dns.Server{
				Addr:    net.JoinHostPort(ip.String(), "53"),
				Net:     tcpNet,
				Handler: s.handler,
			}

			udpServer := &dns.Server{
				Addr:    net.JoinHostPort(ip.String(), "53"),
				Net:     udpNet,
				Handler: s.handler,
			}

			s.frontendServers = append(s.frontendServers, tcpServer, udpServer)

			go func() { s.fatal <- tcpServer.ListenAndServe() }()
			go func() { s.fatal <- udpServer.ListenAndServe() }()
			go s.sessionGC()
		}

		return nil
	}); err != nil {
		return err
	}

	log.Info("Started resolver-server")

	return nil
}

func (s *ResolverService) stop(ctx context.Context) error {
	for _, server := range s.frontendServers {
		if err := server.ShutdownContext(ctx); err != nil {
			return err
		}
	}

	s.frontendServers = []*dns.Server{}

	s.sessionTicker.Stop()

	return s.handler.Close()
}

func (s *ResolverService) Error() error {
	return <-s.fatal
}

func (s *ResolverService) sessionGC() {
	for range s.sessionTicker.C {
		s.handler.ClearExpiredSessions()
	}
}
