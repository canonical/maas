package subcommands

import (
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"
)

var (
	SupportDumpCMD = &cobra.Command{
		Use:   "support-dump",
		Short: "Dump support information. By default, dumps everything available.",
		RunE:  RunSupportDumpCMD,
	}
)

func RunSupportDumpCMD(cmd *cobra.Command, args []string) error {
	log.Debug().Msg("running support-dump...")
	return nil
}
