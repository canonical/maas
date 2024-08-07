// Copyright (c) 2023-2024 Canonical Ltd
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

package dhcp

import (
	"context"
	"net/http"
	"time"

	"go.temporal.io/sdk/activity"
	tworkflow "go.temporal.io/sdk/workflow"
)

// DHCPService is a service that is responsible for setting up DHCP on MAAS Agent.
type DHCPService struct {
	fatal    chan error
	client   *http.Client
	systemID string
	running  bool
}

type DHCPServiceOption func(*DHCPService)

func NewDHCPService(systemID string, options ...DHCPServiceOption) *DHCPService {
	s := &DHCPService{
		systemID: systemID,
	}

	for _, opt := range options {
		opt(s)
	}

	return s
}

// WithHTTPClient allows setting HTTP client that will be used for communication
// with MAAS Region Controller.
func WithHTTPClient(c *http.Client) DHCPServiceOption {
	return func(s *DHCPService) {
		s.client = c
	}
}

func (s *DHCPService) ConfigurationWorkflows() map[string]interface{} {
	return map[string]interface{}{"configure-dhcp-service": s.configure}
}

func (s *DHCPService) ConfigurationActivities() map[string]interface{} {
	return map[string]interface{}{
		// This activity should be called to force DHCP configuration update.
		"update-dhcp-configuration": s.update,
	}
}

type DHCPServiceConfigParam struct {
	Enabled bool `json:"enabled"`
}

// run is a wrapper to run local activities (which are not registered)
func run(ctx tworkflow.Context, fn any, args ...any) error {
	options := tworkflow.LocalActivityOptions{
		ScheduleToCloseTimeout: 30 * time.Second,
	}

	return tworkflow.ExecuteLocalActivity(
		tworkflow.WithLocalActivityOptions(ctx, options),
		fn, args...).Get(ctx, nil)
}

func (s *DHCPService) configure(ctx tworkflow.Context, config DHCPServiceConfigParam) error {
	if !config.Enabled {
		return run(ctx, s.stop)
	}

	err := run(ctx, s.start)
	if err != nil {
		return err
	}

	return run(ctx, s.update)
}

func (s *DHCPService) start(ctx context.Context) error {
	// TODO: start processing loop
	s.running = true
	return nil
}

func (s *DHCPService) stop(ctx context.Context) error {
	// TODO: stop processing loop & clean up resources
	s.running = false

	return nil
}

func (s *DHCPService) update(ctx context.Context) error {
	log := activity.GetLogger(ctx)
	// TODO: API call to get config and template into dhcpd.conf
	log.Debug("DHCPService update in progress..")

	return nil
}

func (s *DHCPService) Error() error {
	err := <-s.fatal
	s.running = false

	return err
}
