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
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"sync/atomic"
	"time"

	"go.temporal.io/sdk/activity"
	tworkflow "go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/apiclient"
	"maas.io/core/src/maasagent/internal/atomicfile"
	"maas.io/core/src/maasagent/internal/dhcpd/omapi"
	"maas.io/core/src/maasagent/internal/pathutil"
)

const (
	dhcpdOMAPIV4Endpoint = "localhost:7911"
	dhcpdOMAPIV6Endpoint = "localhost:7912"
)

var (
	ErrV4NotActive = errors.New("dhcpd4 is not active and cannot configure IPv4 hosts")
	ErrV6NotActive = errors.New("dhcpd6 is not active and cannot configure IPv6 hosts")
)

// DHCPService is a service that is responsible for setting up DHCP on MAAS Agent.
type DHCPService struct {
	fatal              chan error
	client             *apiclient.APIClient
	omapiConnFactory   omapiConnFactory
	omapiClientFactory omapiClientFactory
	dataPathFactory    dataPathFactory
	runningV4          *atomic.Bool
	runningV6          *atomic.Bool
	running            *atomic.Bool
	systemID           string
}

type omapiConnFactory func(string, string) (net.Conn, error)

type omapiClientFactory func(net.Conn, omapi.Authenticator) (omapi.OMAPI, error)

type dataPathFactory func(string) string

type DHCPServiceOption func(*DHCPService)

func NewDHCPService(systemID string, options ...DHCPServiceOption) *DHCPService {
	s := &DHCPService{
		systemID:           systemID,
		omapiConnFactory:   net.Dial,
		omapiClientFactory: omapi.NewClient,
		dataPathFactory:    pathutil.GetDataPath,
		runningV4:          &atomic.Bool{},
		runningV6:          &atomic.Bool{},
		running:            &atomic.Bool{},
	}

	for _, opt := range options {
		opt(s)
	}

	return s
}

// WithAPIClient allows setting internal API client that will be used for
// communication with MAAS Region Controller.
func WithAPIClient(c *apiclient.APIClient) DHCPServiceOption {
	return func(s *DHCPService) {
		s.client = c
	}
}

func WithOMAPIConnFactory(factory omapiConnFactory) DHCPServiceOption {
	return func(s *DHCPService) {
		s.omapiConnFactory = factory
	}
}

func WithOMAPIClientFactory(factory omapiClientFactory) DHCPServiceOption {
	return func(s *DHCPService) {
		s.omapiClientFactory = factory
	}
}

// WithDataPathFactory used for testing.
func WithDataPathFactory(factory dataPathFactory) DHCPServiceOption {
	return func(s *DHCPService) {
		s.dataPathFactory = factory
	}
}

func (s *DHCPService) ConfigurationWorkflows() map[string]interface{} {
	return map[string]interface{}{"configure-dhcp-service": s.configure}
}

func (s *DHCPService) ConfigurationActivities() map[string]interface{} {
	return map[string]interface{}{
		// This activity should be called to force DHCP configuration update.
		"apply-dhcp-config-via-file":  s.configureViaFile,
		"apply-dhcp-config-via-omapi": s.configureViaOMAPI,
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

type ConfigureDHCPForAgentParam struct {
	SystemID        string `json:"system_id"`
	StaticIPAddrIDs []int  `json:"static_ip_addr_ids"` // for parity with python definition, agent should never assign this
	ReservedIPIDs   []int  `json:"reserved_ip_ids"`    // for parity with python definition, agent should never assign this
	FullReload      bool   `json:"full_reload"`
}

func (s *DHCPService) configure(ctx tworkflow.Context, config DHCPServiceConfigParam) error {
	if !config.Enabled {
		return run(ctx, s.stop)
	}

	err := run(ctx, s.start)
	if err != nil {
		return err
	}

	childCtx := tworkflow.WithChildOptions(ctx, tworkflow.ChildWorkflowOptions{
		WorkflowID: fmt.Sprintf("configure-dhcp:%s", s.systemID),
		TaskQueue:  "region",
	})

	return tworkflow.ExecuteChildWorkflow(childCtx, "configure-dhcp-for-agent", ConfigureDHCPForAgentParam{
		SystemID:   s.systemID,
		FullReload: true,
	}).Get(ctx, nil)
}

func (s *DHCPService) start(ctx context.Context) error {
	// TODO: start processing loop
	s.running.Store(true)
	return nil
}

func (s *DHCPService) stop(ctx context.Context) error {
	// TODO: stop processing loop & clean up resources
	s.running.Store(false)

	return nil
}

type Host struct {
	Hostname string           `json:"hostname"`
	IP       net.IP           `json:"ip"`
	MAC      net.HardwareAddr `json:"mac"`
}

type ApplyConfigViaOMAPIParam struct {
	Secret string `json:"secret"`
	Hosts  []Host `json:"hosts"`
}

func (s *DHCPService) configureViaOMAPI(ctx context.Context, param ApplyConfigViaOMAPIParam) error {
	log := activity.GetLogger(ctx)

	log.Debug("DHCPService OMAPI update in progress..")

	var (
		clientV4 omapi.OMAPI
		clientV6 omapi.OMAPI
		err      error
	)

	runningV4 := s.runningV4.Load()
	runningV6 := s.runningV6.Load()

	authenticator := omapi.NewHMACMD5Authenticator("omapi_key", param.Secret)

	// TODO move opening/closing of the omapi client to the start/stop of dhcpd
	// once the config file activity is in place
	if runningV4 {
		var connV4 net.Conn

		connV4, err = s.omapiConnFactory("tcp", dhcpdOMAPIV4Endpoint)
		if err != nil {
			return err
		}

		clientV4, err = s.omapiClientFactory(connV4, &authenticator)
		if err != nil {
			return err
		}

		defer func() {
			cErr := clientV4.Close()
			if err == nil && cErr != nil {
				err = cErr
			}
		}()
	}

	// TODO move opening/closing of the omapi client to the start/stop of dhcpd
	// once the config file activity is in place
	if runningV6 {
		var connV6 net.Conn

		connV6, err = s.omapiConnFactory("tcp", dhcpdOMAPIV6Endpoint)
		if err != nil {
			return err
		}

		clientV6, err = s.omapiClientFactory(connV6, &authenticator)
		if err != nil {
			return err
		}

		defer func() {
			cErr := clientV6.Close()
			if err == nil && cErr != nil {
				err = cErr
			}
		}()
	}

	for _, host := range param.Hosts {
		if v4 := host.IP.To4(); v4 != nil {
			if !runningV4 {
				return ErrV4NotActive
			}

			err = clientV4.AddHost(host.IP, host.MAC)
			if err != nil {
				return err
			}
		} else {
			if !runningV6 {
				return ErrV6NotActive
			}

			err = clientV6.AddHost(host.IP, host.MAC)
			if err != nil {
				return err
			}
		}
	}

	return nil
}

// dhcpConfig represents the DHCP configuration returned by the Region Controller.
// This configuration is required for isc-dhcp, and each field contains data encoded
// in base64 format. The structure includes configuration and interface details
// for both DHCPv4 and DHCPv6.
type dhcpConfig struct {
	DHCPv4Config     string `json:"dhcpd"`
	DHCPv4Interfaces string `json:"dhcpd_interfaces"`
	DHCPv6Interfaces string `json:"dhcpd6_interfaces"`
	DHCPv6Config     string `json:"dhcpd6"`
}

// configureViaFile registered as a Temporal Activity that is invoked during the
// DHCP configuration workflow. This activity is used when the configuration must
// be applied via a file, which requires restarting the dhcpd daemon.
func (s *DHCPService) configureViaFile(ctx context.Context) error {
	config, err := s.getConfig(ctx)
	if err != nil {
		return err
	}

	files := map[string]string{
		"dhcpd.conf":        config.DHCPv4Config,
		"dhcpd-interfaces":  config.DHCPv4Interfaces,
		"dhcpd6.conf":       config.DHCPv6Config,
		"dhcpd6-interfaces": config.DHCPv6Interfaces,
	}

	for file, config := range files {
		data, err := base64.StdEncoding.DecodeString(config)
		if err != nil {
			return err
		}

		if err := s.writeConfigFile(file, data); err != nil {
			return err
		}
	}

	return nil
}

// getConfig retrieves the DHCP configuration from the Region Controller by
// sending a GET request to the relevant endpoint based on the systemID.
func (s *DHCPService) getConfig(ctx context.Context) (*dhcpConfig, error) {
	var config dhcpConfig

	path := fmt.Sprintf("/agents/%s/services/dhcp/config", s.systemID)

	resp, err := s.client.Request(ctx, http.MethodGet, path, nil)
	if err != nil {
		return nil, err
	}

	//nolint:errcheck // should be safe to ignore an error from Close()
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	return &config, json.Unmarshal(body, &config)
}

func (s *DHCPService) writeConfigFile(path string, data []byte) error {
	path = s.dataPathFactory(path)

	return atomicfile.WriteFile(path, data, 0o640)
}

func (s *DHCPService) Error() error {
	err := <-s.fatal
	s.running.Store(false)

	return err
}
