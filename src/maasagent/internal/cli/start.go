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
	"fmt"

	"github.com/spf13/cobra"
)

func startCmd(ctx context.Context) *cobra.Command {
	// NOTE: this argument can be removed once agent doesn't require rackd.
	// Right now it is needed as a circuit-breaker to identify when agent is
	// started directly vs started by rackd.
	var supervised bool

	cmd := &cobra.Command{
		Use:          "start",
		Short:        "Start the MAAS agent daemon.",
		Example:      "maas-agent start",
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			return nil
		},
	}

	cmd.Flags().BoolVar(&supervised, "supervised", false, "")

	err := cmd.Flags().MarkHidden("supervised")
	if err != nil {
		panic(fmt.Errorf("start initialization failed: %w", err))
	}

	return cmd
}
