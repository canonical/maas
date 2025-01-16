// Copyright (c) 2025 Canonical Ltd
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

package workflow

import (
	"time"

	tworkflow "go.temporal.io/sdk/workflow"
)

// RunAsLocalActivity is a wrapper to run function as a Local Activity
// without registering it explicitly.
func RunAsLocalActivity(ctx tworkflow.Context, fn any, args ...any) error {
	options := tworkflow.LocalActivityOptions{
		// 5 seconds timeout to avoid another Workflow Task being scheduled
		ScheduleToCloseTimeout: 5 * time.Second,
	}

	return tworkflow.ExecuteLocalActivity(
		tworkflow.WithLocalActivityOptions(ctx, options),
		fn, args...).Get(ctx, nil)
}
