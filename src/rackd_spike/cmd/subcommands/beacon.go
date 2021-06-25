package subcommands

import (
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"
)

var (
	SendBeaconCMD = &cobra.Command{
		Use:   "send-beacons",
		Short: "Sends out beacons, waits for replies, and optionally print debug info.",
		RunE:  RunSendBeaconCMD,
	}
)

func RunSendBeaconCMD(cmd *cobra.Command, args []string) error {
	log.Debug().Msg("running send-beacon...")
	return nil
}
