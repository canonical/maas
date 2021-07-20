package region

import (
	"context"

	"rackd/internal/config"
	"rackd/internal/transport"
	"rackd/pkg/ntp"
)

func GetRemoteConfig(ctx context.Context, rpcMgr *transport.RPCManager) error {
	ntpIface, err := rpcMgr.GetClient("ntp")
	if err != nil {
		return err
	}
	if ntp, ok := ntpIface.(ntp.Client); ok {
		return ntp.GetTimeConfiguration(ctx, config.Config.SystemID)
	}
	return nil
	// TODO add other services that fetch config from region controller
}
