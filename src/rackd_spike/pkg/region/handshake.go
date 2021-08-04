package region

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"os"

	"rackd/internal/config"
	machinehelpers "rackd/internal/machine_helpers"
	"rackd/internal/transport"
	auth "rackd/pkg/authenticate"
	"rackd/pkg/controller"
	reg "rackd/pkg/register"

	"github.com/rs/zerolog"
)

var (
	ErrNoAuthenticatorProvided = errors.New("error no authenticator was provided")
	ErrNoRegistererProvided    = errors.New("error no registerer was provided")
	ErrRegionNotAuthed         = errors.New("error unable to authenticate with region")
)

func authenticate(ctx context.Context, region string, rpcMgr *transport.RPCManager) error {
	authenticatorIface, err := rpcMgr.GetClient("authenticator")
	if err != nil {
		return err
	}
	authenticator, ok := authenticatorIface.(auth.Authenticator)
	if !ok {
		return ErrNoAuthenticatorProvided
	}
	message := make([]byte, 16)
	_, err = rand.Read(message)
	if err != nil {
		return err
	}
	secret, err := hex.DecodeString(config.Config.Secret)
	if err != nil {
		return err
	}
	creds, err := authenticator.Authenticate(ctx, region, secret, message)
	if err != nil {
		return err
	}
	if !creds.Verify(secret, message) {
		return fmt.Errorf("%w: credential verification failed", ErrRegionNotAuthed)
	}
	return nil
}

func register(
	ctx context.Context,
	region, localVersion string,
	rpcMgr *transport.RPCManager,
	ctrlr *controller.RackController,
) error {
	registererIface, err := rpcMgr.GetClient("registerer")
	if err != nil {
		return err
	}
	registerer, ok := registererIface.(reg.Registerer)
	if !ok {
		return ErrNoRegistererProvided
	}

	clusterUUID := config.Config.ClusterUUID
	systemId := config.Config.SystemID
	if err != nil {
		return err
	}
	interfaces, err := machinehelpers.GetAllInterfacesDefinition(ctx, false)
	if err != nil {
		return err
	}
	hostname, err := os.Hostname()
	if err != nil {
		return err
	}
	err = registerer.Register(
		ctx,
		ctrlr,
		region,
		clusterUUID,
		systemId,
		hostname,
		localVersion,
		interfaces,
	)
	if err != nil {
		return err
	}
	return nil
}

// Handeshake executes the full handshake with a region controller
func Handshake(ctx context.Context, region, localVersion string, rpcMgr *transport.RPCManager) error {
	log := zerolog.Ctx(ctx)

	err := authenticate(ctx, region, rpcMgr)
	if err != nil {
		log.Err(err).Msg("error authenticating")
		return err
	}
	rackCtrlr, err := rpcMgr.GetHandler("rack-controller")
	if err != nil {
		log.Err(err).Msg("error registering")
		return err
	}
	ctrlr, ok := rackCtrlr.(*controller.RackController)
	if !ok {
		return controller.ErrInvalidRackController
	}
	return register(ctx, region, localVersion, rpcMgr, ctrlr)
}
