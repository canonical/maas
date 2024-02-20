package httpproxy

import (
	"net"
	"net/http"
	"net/url"
	"os"
	"path"
	"regexp"
	"syscall"
	"time"

	tworkflow "go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/workflow/log/tag"
)

const (
	httpProxyServiceWorkerPoolGroup = "httpproxy-service"
	socketFileName                  = "agent-httpproxy.sock"
)

var (
	rewriteRules = []*RewriteRule{
		NewRewriteRule(regexp.MustCompile(".*/bootaa64.efi"), "boot-resources/bootloaders/uefi/arm64/bootaa64.efi"),
		NewRewriteRule(regexp.MustCompile(".*/grubaa64.efi"), "boot-resources/bootloaders/uefi/arm64/grubaa64.efi"),
		NewRewriteRule(regexp.MustCompile(".*/bootx64.efi"), "boot-resources/bootloaders/uefi/amd64/bootx64.efi"),
		NewRewriteRule(regexp.MustCompile(".*/grubx64.efi"), "boot-resources/bootloaders/uefi/amd64/grubx64.efi"),
		NewRewriteRule(regexp.MustCompile(".*/bootppc64.bin"), "boot-resources/bootloaders/open-firmware/ppc64el/bootppc64.bin"),
		NewRewriteRule(regexp.MustCompile(".*/lpxelinux.0"), "boot-resources/bootloader/pxe/i386/lpxelinux.0"),
		NewRewriteRule(regexp.MustCompile(".*/chain.c32"), "boot-resources/bootloader/pxe/i386/chain.c32"),
		NewRewriteRule(regexp.MustCompile(".*/ifcpu.c32"), "boot-resources/bootloader/pxe/i386/ifcpu.c32"),
		NewRewriteRule(regexp.MustCompile(".*/ifcpu64.c32"), "boot-resources/bootloader/pxe/i386/ifcpu64.c32"),
		NewRewriteRule(regexp.MustCompile(".*/ldlinux.c32"), "boot-resources/bootloader/pxe/i386/ldlinux.c32"),
		NewRewriteRule(regexp.MustCompile(".*/libcom32.c32"), "boot-resources/bootloader/pxe/i386/libcom32.c32"),
		NewRewriteRule(regexp.MustCompile(".*/libutil.c32"), "boot-resources/bootloader/pxe/i386/libutil.c32"),
		NewRewriteRule(regexp.MustCompile(".*/images/(.*)"), "boot-resources/$1"),
	}

	cacheRules = []*CacheRule{
		NewCacheRule(regexp.MustCompile("boot-resources/([[:alnum:]]{64})/"), "$1"),
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

// ConfiguratorName returns a name that will be used to register Configure
// method as Temporal workflow.
func (s *HTTPProxyService) ConfiguratorName() string {
	return "configure-httpproxy-service"
}

type getRegionEndpointsResult struct {
	Endpoints []string `json:"endpoints"`
}

// Configure represents a Temporal workflow that is capable for configuring
// Agent HTTP proxy service.
func (s *HTTPProxyService) Configure(ctx tworkflow.Context, systemID string) error {
	log := tworkflow.GetLogger(ctx)

	// We will close existing listener without graceful shutdown, because it
	// make no sense in case of endpoints reconfiguration.
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

	var endpointsResult getRegionEndpointsResult

	err := tworkflow.ExecuteActivity(
		tworkflow.WithActivityOptions(ctx,
			tworkflow.ActivityOptions{
				TaskQueue:              "region",
				ScheduleToCloseTimeout: 60 * time.Second,
			}),
		"get-region-controller-endpoints").
		Get(ctx, &endpointsResult)
	if err != nil {
		return err
	}

	var u *url.URL

	targets := make([]*url.URL, len(endpointsResult.Endpoints))
	for i := 0; i < len(targets); i++ {
		u, err = url.Parse(endpointsResult.Endpoints[i])
		if err != nil {
			return err
		}

		targets[i] = u
	}

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

	// XXX: While httpproxy-service service is consumed through socket via NGINX
	// there is nothing bad about not setting the timeout on the listener/server/

	//nolint:gosec // this is okay in the current situation
	go func() { s.fatal <- http.Serve(s.listener, s.proxy) }()

	log.Info("Starting httpproxy-service", tag.Builder().KV("targets", targets).KeyVals...)
	// We consider this workflow to be successful without checking if the service
	// is up & running after a call to http.Serve().
	// If there will be any error, it should be captured via HTTPProxyService.Error()
	return nil
}

func (s *HTTPProxyService) Error() chan error {
	return s.fatal
}
