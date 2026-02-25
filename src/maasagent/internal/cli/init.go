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
	"io"
	"os"
	"strings"

	"github.com/spf13/cobra"
)

func initCmd(ctx context.Context) *cobra.Command {
	var token string

	cmd := &cobra.Command{
		Use:          "init",
		Short:        "Connect with MAAS region controller.",
		Example:      "maas-agent init --token <token>",
		SilenceUsage: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			if token == "-" {
				input, err := io.ReadAll(os.Stdin)
				if err != nil {
					return fmt.Errorf("failed to read token from stdin: %w", err)
				}

				token = strings.TrimSpace(string(input))
			}

			if token == "" {
				return fmt.Errorf("--token (-t) must be specified")
			}

			return nil
		},
	}

	cmd.Flags().StringVarP(&token, "token", "t", "",
		"Bootstrap token used to initialize MAAS agent (use '-' to read from stdin)")

	return cmd
}
