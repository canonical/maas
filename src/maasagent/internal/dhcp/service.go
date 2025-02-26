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
	"os"
	"os/exec"
	"sync/atomic"
	"syscall"
	"time"

	"github.com/cenkalti/backoff/v4"
	"go.temporal.io/sdk/activity"
	tworkflow "go.temporal.io/sdk/workflow"
	"maas.io/core/src/maasagent/internal/apiclient"
	"maas.io/core/src/maasagent/internal/atomicfile"
	"maas.io/core/src/maasagent/internal/dhcpd"
	"maas.io/core/src/maasagent/internal/dhcpd/omapi"
	"maas.io/core/src/maasagent/internal/pathutil"
	"maas.io/core/src/maasagent/internal/servicecontroller"
	"maas.io/core/src/maasagent/internal/workflow"
	"maas.io/core/src/maasagent/internal/workflow/log/tag"
)

const (
	dhcpdOMAPIV4Endpoint        = "localhost:7911"
	dhcpdOMAPIV6Endpoint        = "localhost:7912"
	dhcpdNotificationSocketName = "dhcpd.sock"
	flushInterval               = 5 * time.Second
)

var (
	ErrV4NotActive               = errors.New("dhcpd4 is not active and cannot configure IPv4 hosts")
	ErrV6NotActive               = errors.New("dhcpd6 is not active and cannot configure IPv6 hosts")
	ErrFailedToPostNotifications = errors.New("error processing lease notifications")
)

var writeConfigFile func(path string, data []byte, mode os.FileMode) error

var writeConfigFileSnap = atomicfile.WriteFile

var writeConfigFileDeb = func(path string, data []byte, mode os.FileMode) error {
	scriptPath := "/usr/lib/maas/maas-write-file"
	fileName := path
	modeStr := fmt.Sprintf("%d", mode)

	// create the command that runs maas-write-file
	// #nosec G204: the inputs are sanitized and validated by `maas-write-file`
	cmd := exec.Command("sudo", scriptPath, fileName, modeStr)

	// feed the script by piping the data to stdin
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return err
	}

	// start script
	if err = cmd.Start(); err != nil {
		return err
	}

	// write to stdin
	if err = func() error {
		defer func() {
			if closeErr := stdin.Close(); closeErr != nil {
				err = closeErr
			}
		}()
		_, err = stdin.Write(data)
		return err
	}(); err != nil {
		return err
	}

	// wait for the script to finish
	if err = cmd.Wait(); err != nil {
		return err
	}

	return nil
}

// DHCPService is a service that is responsible for setting up DHCP on MAAS Agent.
type DHCPService struct {
	fatal              chan error
	client             *apiclient.APIClient
	notificationSock   net.Conn
	notificationCancel context.CancelFunc
	omapiConnFactory   omapiConnFactory
	omapiClientFactory omapiClientFactory
	dataPathFactory    dataPathFactory
	controllerV4       servicecontroller.Controller
	controllerV6       servicecontroller.Controller
	runningV4          *atomic.Bool
	runningV6          *atomic.Bool
	running            *atomic.Bool
	systemID           string
}

type omapiConnFactory func(string, string) (net.Conn, error)

type omapiClientFactory func(net.Conn, omapi.Authenticator) (omapi.OMAPI, error)

type dataPathFactory func(string) string

type DHCPServiceOption func(*DHCPService)

// Initialize the writeConfigFile based on the MAAS installation method
func init() {
	if _, isSnap := os.LookupEnv("SNAP"); isSnap {
		writeConfigFile = writeConfigFileSnap
	} else {
		writeConfigFile = writeConfigFileDeb
	}
}

func NewDHCPService(
	systemID string,
	controllerV4 servicecontroller.Controller,
	controllerV6 servicecontroller.Controller,
	options ...DHCPServiceOption,
) *DHCPService {
	s := &DHCPService{
		systemID:           systemID,
		controllerV4:       controllerV4,
		controllerV6:       controllerV6,
		omapiConnFactory:   net.Dial,
		omapiClientFactory: omapi.NewClient,
		dataPathFactory:    pathutil.GetMAASDataPath,
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

func queueFlush(c *apiclient.APIClient, interval time.Duration) func(context.Context, []*dhcpd.Notification) error {
	retry := backoff.NewExponentialBackOff()
	retry.MaxElapsedTime = interval

	return func(ctx context.Context, n []*dhcpd.Notification) error {
		body, err := json.Marshal(n)
		if err != nil {
			return err
		}

		return backoff.Retry(func() error {
			resp, err := c.Request(ctx, http.MethodPost, "/v3internal/leases", body)
			if err != nil {
				return err
			}

			if resp.StatusCode < 200 || resp.StatusCode >= 400 {
				return ErrFailedToPostNotifications
			}

			return nil
		}, retry)
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
		"restart-dhcp-service":        s.restartService,
	}
}

type DHCPServiceConfigParam struct {
	Enabled bool `json:"enabled"`
}

type ConfigureDHCPForAgentParam struct {
	SystemID        string `json:"system_id"`
	VlanIDs         []int  `json:"vlan_ids"`           // for parity with python definition, agent should never assign this
	SubnetIDs       []int  `json:"subnet_ids"`         // for parity with python definition, agent should never assign this
	IPRangeIDs      []int  `json:"ip_ranges_ids"`      // for parity with python definition, agent should never assign this
	StaticIPAddrIDs []int  `json:"static_ip_addr_ids"` // for parity with python definition, agent should never assign this
	ReservedIPIDs   []int  `json:"reserved_ip_ids"`    // for parity with python definition, agent should never assign this
	FullReload      bool   `json:"full_reload"`
}

func (s *DHCPService) configure(ctx tworkflow.Context, config DHCPServiceConfigParam) error {
	log := tworkflow.GetLogger(ctx)
	log.Info("Configuring dhcp-service")

	if err := workflow.RunAsLocalActivity(ctx, func(ctx context.Context) error {
		if !config.Enabled {
			log.Info("Stopping dhcp-service", tag.Builder().KV("enabled", config.Enabled))
			return s.stop(ctx)
		}

		if err := s.start(); err != nil {
			return err
		}

		log.Info("Started dhcp-service")

		return nil
	}); err != nil {
		return err
	}

	childCtx := tworkflow.WithChildOptions(ctx, tworkflow.ChildWorkflowOptions{
		WorkflowID: fmt.Sprintf("configure-dhcp:%s", s.systemID),
		TaskQueue:  "region",
	})

	return tworkflow.ExecuteChildWorkflow(childCtx, "configure-dhcp-for-agent", ConfigureDHCPForAgentParam{
		SystemID:        s.systemID,
		FullReload:      true,
		VlanIDs:         []int{},
		SubnetIDs:       []int{},
		IPRangeIDs:      []int{},
		StaticIPAddrIDs: []int{},
		ReservedIPIDs:   []int{},
	}).Get(ctx, nil)
}

func (s *DHCPService) start() error {
	sockPath := s.dataPathFactory(dhcpdNotificationSocketName)

	if err := syscall.Unlink(sockPath); err != nil {
		if !os.IsNotExist(err) {
			return err
		}
	}

	addr, err := net.ResolveUnixAddr("unixgram", sockPath)
	if err != nil {
		return err
	}

	s.notificationSock, err = net.ListenUnixgram("unixgram", addr)
	if err != nil {
		return err
	}

	// The dhcpd socket must be world readable/writable
	if err := os.Chmod(sockPath, 0666); err != nil { //nolint:gosec // ignore G302
		return err
	}

	notificationListener := dhcpd.NewNotificationListener(s.notificationSock,
		queueFlush(s.client, flushInterval), dhcpd.WithInterval(flushInterval))

	var ctx context.Context

	ctx, s.notificationCancel = context.WithCancel(context.Background())

	go notificationListener.Listen(ctx)

	s.running.Store(true)

	return nil
}

func (s *DHCPService) stop(ctx context.Context) error {
	if s.notificationCancel != nil {
		s.notificationCancel()
	}

	if s.notificationSock != nil {
		err := s.notificationSock.Close()
		if err != nil {
			return err
		}
	}

	s.running.Store(false)

	return nil
}

type Host struct {
	Hostname string           `json:"hostname"`
	IP       net.IP           `json:"ip"`
	MAC      net.HardwareAddr `json:"mac"`
}

func (h Host) MarshalJSON() ([]byte, error) {
	tmp := struct {
		Hostname string `json:"hostname"`
		IP       string `json:"ip"`
		MAC      string `json:"mac"`
	}{
		Hostname: h.Hostname,
		IP:       h.IP.String(),
		MAC:      h.MAC.String(),
	}

	return json.Marshal(tmp)
}

func (h *Host) UnmarshalJSON(data []byte) error {
	var tmp struct {
		Hostname string `json:"hostname"`
		MAC      string `json:"mac"`
		IP       net.IP `json:"ip"`
	}

	if err := json.Unmarshal(data, &tmp); err != nil {
		return err
	}

	h.Hostname = tmp.Hostname
	h.IP = tmp.IP

	var err error

	h.MAC, err = net.ParseMAC(tmp.MAC)
	if err != nil {
		return fmt.Errorf("error converting net.HardwareAddr: %v", err)
	}

	return nil
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

	mode := os.FileMode(0o640)

	v4 := []bool{false, false}
	v6 := []bool{false, false}

	for file, config := range files {
		data, err := base64.StdEncoding.DecodeString(config)
		if err != nil {
			return err
		}

		hasData := len(data) != 0

		if file == "dhcpd.conf" {
			v4[0] = hasData
		}

		if file == "dhcpd-interfaces" {
			v4[1] = hasData
		}

		if file == "dhcpd6.conf" {
			v6[0] = hasData
		}

		if file == "dhcpd6-interfaces" {
			v6[1] = hasData
		}

		path := s.dataPathFactory(file)
		if err := writeConfigFile(path, data, mode); err != nil {
			return err
		}
	}

	runningV4 := v4[0] && v4[1]
	runningV6 := v6[0] && v6[1]

	s.runningV4.Store(runningV4)
	s.runningV6.Store(runningV6)
	s.running.Store(runningV4 || runningV6)

	return nil
}

func (s *DHCPService) restartService(ctx context.Context) error {
	runningV4 := s.runningV4.Load()
	runningV6 := s.runningV6.Load()

	if runningV4 {
		err := s.controllerV4.Restart(ctx)
		if err != nil {
			return err
		}
	}

	if runningV6 {
		err := s.controllerV6.Restart(ctx)
		if err != nil {
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

func (s *DHCPService) Error() error {
	err := <-s.fatal
	s.running.Store(false)

	return err
}
