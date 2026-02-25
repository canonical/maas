// Copyright (c) 2026 Canonical Ltd
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU Affero General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU Affero General Public License for more details.
//
// You should have received a copy of the GNU Affero General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.

package cli

import (
	"context"

	"github.com/spf13/cobra"
)

func RootCmd(ctx context.Context) *cobra.Command {
	cmd := &cobra.Command{
		Use:   "maas-agent",
		Short: "MAAS agent - take control of your rack internals!",
		// Silence because we want to use our logger instead
		SilenceErrors:     true,
		SilenceUsage:      true,
		CompletionOptions: cobra.CompletionOptions{DisableDefaultCmd: true},
		// TODO: Extract version information
		// Version:           version.Version(),
		RunE: func(cmd *cobra.Command, args []string) error {
			return cmd.Help()
		},
	}

	cmd.SetVersionTemplate("{{.Version}}\n")
	cmd.PersistentFlags().BoolP("help", "h", false,
		"Help information about a command")

	cmd.AddCommand(initCmd(ctx))
	cmd.AddCommand(startCmd(ctx))

	cmd.InitDefaultHelpCmd()

	return cmd
}
