package main

import (
	"os"
	"os/signal"
	"syscall"

	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"

	"rackd/cmd/subcommands"
)

type opts struct {
	Euid     bool
	Version  bool
	NoDaemon bool
	NoSave   bool
	GID      uint32
	UID      uint32
	Chroot   string
	RunDir   string
	LogFile  string
	Logger   string
	PIDFile  string
	Syslog   string
}

var rootCMD = &cobra.Command{
	Use:   "rackd",
	Short: "rack controller daemon",
	RunE: func(cmd *cobra.Command, args []string) error {
		log.Info().Msg("rackd started successfully")
		sigChan := make(chan os.Signal)
		signal.Notify(sigChan, syscall.SIGTERM, syscall.SIGINT)
		<-sigChan
		return nil
	},
}

func main() {
	zerolog.TimeFieldFormat = zerolog.TimeFormatUnix
	rootCMD.AddCommand(subcommands.RegisterCMD)
	rootCMD.AddCommand(subcommands.ConfigCMD)
	rootCMD.AddCommand(subcommands.ObserveCMD)
	rootCMD.Execute()
}
