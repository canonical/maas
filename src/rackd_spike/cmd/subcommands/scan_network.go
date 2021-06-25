package subcommands

import (
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"
)

var (
	ScanNetworkCMD = &cobra.Command{
		Use:   "scan-network",
		Short: "Scan local networks for on-link hosts.",
		RunE:  RunScanNetworkCMD,
	}
)

func RunScanNetworkCMD(cmd *cobra.Command, args []string) error {
	log.Debug().Msg("running scan-network...")
	return nil
}
