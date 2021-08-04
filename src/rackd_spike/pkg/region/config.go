package region

import (
	"context"

	"github.com/rs/zerolog"

	"rackd/internal/config"
	httpInternal "rackd/internal/http"
	"rackd/internal/service"
	"rackd/internal/transport"
	"rackd/pkg/http"
	"rackd/pkg/ntp"
	"rackd/pkg/tftp"
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

	tftpIface, err := rpcMgr.GetClient("tftp")
	if err != nil {
		return err
	}

	revProxyIface, err := sup.Get("http_reverse_proxy")
	if err != nil {
		return err
	}

	if n, ok := ntpIface.(ntp.Client); ok {
		log.Info().Msg("configuring NTP")
		err = n.GetTimeConfiguration(ctx, config.Config.SystemID)
		if err != nil {
			log.Err(err).Msg("error fetching ntp config")
			return err
		}
	}
	if proxy, ok := proxyIface.(http.Client); ok {
		log.Info().Msg("configuring proxy")
		err = proxy.GetProxyConfiguration(ctx, config.Config.SystemID)
		if err != nil {
			log.Err(err).Msg("error fetching http proxy config")
			return err
		}
	}
	if revProxy, ok := revProxyIface.(httpInternal.RevProxyService); ok {
		log.Info().Msg("configuring HTTP reverse proxy")
		err = revProxy.Configure(ctx, rpcMgr.ConnsToString())
		if err != nil {
			log.Err(err).Msg("error configuring reverse proxy")
			return err
		}
	}
	if tftpClient, ok := tftpIface.(tftp.Client); ok {
		log.Info().Msg("configuring TFTP service")
		err = tftpClient.GetTFTPServers(ctx, config.Config.SystemID)
		if err != nil {
			log.Err(err).Msg("error fetching tftp config")
			return err
		}
	}

	return nil
	// TODO add other services that fetch config from region controller
}
