// Copyright (c) 2023-2024 Canonical Ltd
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

package httpproxy

import (
	"context"
	"net"
	"net/http"
	"net/url"
	"os"
	"path"
	"regexp"
	"sync"
	"syscall"
	"time"

	tworkflow "go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/workflow"
	"maas.io/core/src/maasagent/internal/workflow/log/tag"
)

const (
	httpProxyServiceWorkerPoolGroup = "httpproxy-service"
	socketFileName                  = "httpproxy.sock"
)

var (
	rewriteRules = []*RewriteRule{
		NewRewriteRule(regexp.MustCompile(".*/bootaa64.efi"), "boot-resources/bootloaders/uefi/arm64/bootaa64.efi"),
		NewRewriteRule(regexp.MustCompile(".*/grubaa64.efi"), "boot-resources/bootloaders/uefi/arm64/grubaa64.efi"),
		NewRewriteRule(regexp.MustCompile(".*/bootx64.efi"), "boot-resources/bootloaders/uefi/amd64/bootx64.efi"),
		NewRewriteRule(regexp.MustCompile(".*/grubx64.efi"), "boot-resources/bootloaders/uefi/amd64/grubx64.efi"),
		NewRewriteRule(regexp.MustCompile(".*/bootppc64.bin"), "boot-resources/bootloaders/open-firmware/ppc64el/bootppc64.bin"),
		NewRewriteRule(regexp.MustCompile(".*/lpxelinux.0"), "boot-resources/bootloaders/pxe/i386/lpxelinux.0"),
		NewRewriteRule(regexp.MustCompile(".*/chain.c32"), "boot-resources/bootloaders/pxe/i386/chain.c32"),
		NewRewriteRule(regexp.MustCompile(".*/ifcpu.c32"), "boot-resources/bootloaders/pxe/i386/ifcpu.c32"),
		NewRewriteRule(regexp.MustCompile(".*/ifcpu64.c32"), "boot-resources/bootloaders/pxe/i386/ifcpu64.c32"),
		NewRewriteRule(regexp.MustCompile(".*/ldlinux.c32"), "boot-resources/bootloaders/pxe/i386/ldlinux.c32"),
		NewRewriteRule(regexp.MustCompile(".*/libcom32.c32"), "boot-resources/bootloaders/pxe/i386/libcom32.c32"),
		NewRewriteRule(regexp.MustCompile(".*/libutil.c32"), "boot-resources/bootloaders/pxe/i386/libutil.c32"),
		NewRewriteRule(regexp.MustCompile(".*/images/(.*)"), "boot-resources/$1"),
	}

	cacheRules = []*CacheRule{
		// Matches the partial sha256 we use to identify images.
		NewCacheRule(regexp.MustCompile("boot-resources/([0-9a-fA-F]+)/"), "$1"),
	}
)

// HTTPProxyService is a service that is used to proxy HTTP requests to the Region.
// Invocation of this service normally should happen via Temporal.
type HTTPProxyService struct {
	listener   net.Listener
	cache      Cache
	proxy      *Proxy
	fatal      chan error
	socketPath string
}

// NewHTTPProxyService returns an instance of HTTPProxyService
// TODO: consider switching to opts pattern
func NewHTTPProxyService(socketDir string, cache Cache) *HTTPProxyService {
	socketPath := path.Join(socketDir, socketFileName)

	return &HTTPProxyService{cache: cache, socketPath: socketPath}
}

type getRegionEndpointsResult struct {
	Endpoints []string `json:"endpoints"`
}

func (s *HTTPProxyService) ConfigurationWorkflows() map[string]interface{} {
	return map[string]interface{}{"configure-httpproxy-service": s.configure}
}

func (s *HTTPProxyService) ConfigurationActivities() map[string]interface{} {
	return map[string]interface{}{}
}

func (s *HTTPProxyService) configure(ctx tworkflow.Context, systemID string) error {
	log := tworkflow.GetLogger(ctx)
	log.Info("Configuring httpproxy-service")

	// We will close existing listener without graceful shutdown, because it
	// make no sense in case of endpoints reconfiguration.
	if err := workflow.RunAsLocalActivity(ctx, func(_ context.Context) error {
		if s.listener != nil {
			if err := s.listener.Close(); err != nil {
				return err
			}
		}

		if err := syscall.Unlink(s.socketPath); err != nil {
			if !os.IsNotExist(err) {
				return err
			}
		}
		return nil
	}); err != nil {
		return err
	}

	var endpointsResult getRegionEndpointsResult

	if err := tworkflow.ExecuteActivity(
		tworkflow.WithActivityOptions(ctx,
			tworkflow.ActivityOptions{
				TaskQueue:              "region",
				ScheduleToCloseTimeout: 60 * time.Second,
			}),
		"get-region-controller-endpoints").
		Get(ctx, &endpointsResult); err != nil {
		return err
	}

	var targets []*url.URL

	if err := workflow.RunAsLocalActivity(ctx, func(_ context.Context) error {
		var wg sync.WaitGroup

		for _, endpoint := range endpointsResult.Endpoints {
			wg.Add(1)

			go func(endpoint string) {
				defer wg.Done()

				u, err := url.Parse(endpoint)
				// Normally this error should not happen, as we should always receive
				// valid endpoint from the Region Controller
				if err != nil {
					log.Warn("Invalid endpoint", tag.Builder().
						KV("endpoint", endpoint).
						KV("error", err))
				}

				// We might receive endpoints that we cannot reach, so before applying
				// proxy settings we need to check which are actually reachable.
				conn, err := net.DialTimeout("tcp", u.Host, 500*time.Millisecond)
				if err != nil {
					return
				}

				targets = append(targets, u)

				if err := conn.Close(); err != nil {
					// We cannot do anything here and this is not critical, but not good.
					// So we just log it as a Warning.
					log.Warn("Failed to close connection", tag.Builder().KV("error", err))
				}
			}(endpoint)
		}

		wg.Wait()

		var err error
		s.proxy, err = NewProxy(targets,
			WithRewriter(NewRewriter(rewriteRules)),
			WithCacher(NewCacher(cacheRules, s.cache)),
		)
		if err != nil {
			return err
		}

		s.listener, err = net.Listen("unix", s.socketPath)
		if err != nil {
			return err
		}

		//nolint:gosec // we know what we are doing here and we need 0660
		if err := os.Chmod(s.socketPath, 0660); err != nil {
			return err
		}

		// XXX: While httpproxy-service service is consumed through socket via NGINX
		// there is nothing bad about not setting the timeout on the listener/server
		//nolint:gosec // this is okay in the current situation
		go func() { s.fatal <- http.Serve(s.listener, s.proxy) }()

		return nil
	}); err != nil {
		return err
	}

	log.Info("Started httpproxy-service", tag.Builder().KV("targets", targets).KeyVals...)
	// We consider this workflow to be successful without checking if the service
	// is up & running after a call to http.Serve().
	// If there will be any error, it should be captured via HTTPProxyService.Error()
	return nil
}

func (s *HTTPProxyService) Error() error {
	return <-s.fatal
}
