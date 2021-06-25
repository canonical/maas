package subcommands

import (
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"
)

var (
	SetupDNSCMD = &cobra.Command{
		Use:   "setup-dns",
		Short: "Setup MAAS DNS configuration.",
		RunE:  RunSetupDNSCMD,
	}
)

func RunSetupDNSCMD(cmd *cobra.Command, args []string) error {
	log.Debug().Msg("running setup-dns...")
	return nil
}
