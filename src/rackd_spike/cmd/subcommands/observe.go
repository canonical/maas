package subcommands

import (
	"github.com/rs/zerolog/log"
	"github.com/spf13/cobra"
)

var (
	ObserveCMD = &cobra.Command{
		Use:   "observe",
		Short: "network observation commands",
	}
	ObserveArpCMD = &cobra.Command{
		Use:   "arp",
		Short: "observes the traffic on the specified interface, looking for ARP traffic",
		RunE:  RunObserveARPCMD,
	}
	ObserveBeaconsCMD = &cobra.Command{
		Use:   "beacons",
		Short: "observe beacon traffic on specified interface",
		RunE:  RunObserveBeaconCMD,
	}
	ObserveDHCPCMD = &cobra.Command{
		Use:   "dhcp",
		Short: "observe DHCP traffic on specified interface",
		RunE:  RunObserveDHCPCMD,
	}
	ObserveMDNSCMD = &cobra.Command{
		Use:   "mdns",
		Short: "use the 'avahi-browse' utility mDNS activity on the network",
		RunE:  RunObserveMDNSCMD,
	}
)

func init() {
	ObserveCMD.AddCommand(ObserveArpCMD)
	ObserveCMD.AddCommand(ObserveBeaconsCMD)
	ObserveCMD.AddCommand(ObserveDHCPCMD)
	ObserveCMD.AddCommand(ObserveMDNSCMD)
}

func RunObserveARPCMD(cmd *cobra.Command, args []string) error {
	log.Debug().Msg("running observe-arp...")
	return nil
}

func RunObserveBeaconCMD(cmd *cobra.Command, args []string) error {
	log.Debug().Msg("running observe-beacons")
	return nil
}

func RunObserveDHCPCMD(cmd *cobra.Command, args []string) error {
	log.Debug().Msg("running observe-dhcp")
	return nil
}

func RunObserveMDNSCMD(cmd *cobra.Command, args []string) error {
	log.Debug().Msg("running observe-mdns")
	return nil
}
