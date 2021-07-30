package region

import (
	"context"

	"github.com/rs/zerolog"

	"rackd/internal/config"
	httpInternal "rackd/internal/http"
	"rackd/internal/service"
	"rackd/internal/tftp"
	"rackd/internal/transport"
	"rackd/pkg/http"
	"rackd/pkg/ntp"
)

func GetRemoteConfig(ctx context.Context, rpcMgr *transport.RPCManager, sup service.SvcManager) error {
	log := zerolog.Ctx(ctx)

	ntpIface, err := rpcMgr.GetClient("ntp")
	if err != nil {
		return err
	}

	proxyIface, err := rpcMgr.GetClient("http")
	if err != nil {
		return err
	}

	revProxyIface, err := sup.Get("http_reverse_proxy")
	if err != nil {
		return err
	}

	tftpSvcIface, err := sup.Get("tftp")
	if err != nil {
		return err
	}

	if n, ok := ntpIface.(ntp.Client); ok {
		log.Info().Msg("configuring NTP")
		err = n.GetTimeConfiguration(ctx, config.Config.SystemID)
		if err != nil {
			return err
		}
	}
	if proxy, ok := proxyIface.(http.Client); ok {
		log.Info().Msg("configuring proxy")
		err = proxy.GetProxyConfiguration(ctx, config.Config.SystemID)
		if err != nil {
			return err
		}
	}
	if revProxy, ok := revProxyIface.(httpInternal.RevProxyService); ok {
		log.Info().Msg("configuring HTTP reverse proxy")
		revProxy.Configure(ctx, rpcMgr.ConnsToString())
	}
	if tftpSvc, ok := tftpSvcIface.(tftp.TFTPService); ok {
		log.Info().Msg("configuring TFTP service")
		tftpSvc.Configure(ctx, rpcMgr.ConnsToString())
	}

	return nil
	// TODO add other services that fetch config from region controller
}
