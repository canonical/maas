package subcommands

import (
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"
)

var (
	ConfigCMD = &cobra.Command{
		Use:   "config",
		Short: "update configuration settings",
		RunE:  RunConfigCMD,
	}
)

func RunConfigCMD(cmd *cobra.Command, args []string) error {
	log.Debug().Msg("running config command...")
	return nil
}
