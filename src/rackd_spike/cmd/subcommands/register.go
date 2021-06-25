package subcommands

import (
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"
)

const (
	// TODO update with authentication credentials once that process is designed
	registerDescription = `
	Examples of command usage (with interactive input):
	- Supplying both URL and <credential>
	`
)

var (
	RegisterCMD = &cobra.Command{
		Use:   "register",
		Short: "register this rack controller with a region controller",
		Long:  registerDescription,
		RunE:  runRegisterCMD,
	}
)

func runRegisterCMD(cmd *cobra.Command, args []string) error {
	log.Debug().Msg("registering rack controller...")
	return nil
}
