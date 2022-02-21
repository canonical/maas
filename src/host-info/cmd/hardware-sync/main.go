// Copyright 2022 Canonical Ltd.  This software is licensed under the
// GNU Affero General Public License version 3 (see the file LICENSE).

package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"os"

	"host-info/pkg/info"
)

// MAASVersion corresponds with the running MAAS version hardware-sync reports to
var MAASVersion = "" // set at compile time

const TokenFormat = "'consumer-key:token-key:token-secret[:consumer_secret]'"

type getMachineTokenOptions struct {
	SystemId  string
	TokenFile string
}

type reportResultsOptions struct {
	Config       string
	MachineToken string
	MetadataUrl  string
}

type cmdOptions struct {
	Debug              bool
	MachineResourceRun bool
	GetMachineToken    getMachineTokenOptions
	ReportResults      reportResultsOptions
}

func parseCmdLine() (opts cmdOptions) {
	flag.BoolVar(&opts.Debug, "debug", false, "print verbose debug messages")
	flag.BoolVar(&opts.MachineResourceRun, "machine-resources", false, "when set, will read machine resources and print the info to stdout")
	flag.StringVar(&opts.GetMachineToken.SystemId, "system-id", "", "system ID for the machine to get credentials for")
	flag.StringVar(&opts.GetMachineToken.TokenFile, "token-file", "", "path for the file to write the token to")
	flag.StringVar(
		&opts.ReportResults.Config,
		"config",
		"",
		"cloud-init config with MAAS credentials and endpoint, (e.g. /etc/cloud/cloud.cfg.d/90_dpkg_local_cloud_config.cfg)",
	)
	flag.StringVar(
		&opts.ReportResults.MachineToken,
		"machine-token",
		"",
		fmt.Sprintf("Machine OAuth token, in the %s form", TokenFormat),
	)
	flag.StringVar(
		&opts.ReportResults.MetadataUrl,
		"metadata-url",
		"",
		"MAAS metadata URL",
	)
	flag.Parse()
	return opts
}

func getMachineResources() error {
	machineResources, err := info.GetInfo()
	if err != nil {
		return err
	}
	encoder := json.NewEncoder(os.Stdout)
	return encoder.Encode(machineResources)
}

func run() int {
	opts := parseCmdLine()

	if opts.MachineResourceRun {
		err := getMachineResources()
		if err != nil {
			fmt.Printf("an error occurred while fetching machine resources: %s\n", err)
			return 1
		}
		return 0
	}

	// TODO embed scripts and call out to maas_run_scripts
	return 0
}

func main() {
	os.Exit(run())
}
