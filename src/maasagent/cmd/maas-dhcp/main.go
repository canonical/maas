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

package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"

	"github.com/canonical/microcluster/v2/state"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
	"gopkg.in/yaml.v3"

	"maas.io/core/src/maasagent/internal/apiclient"
	"maas.io/core/src/maasagent/internal/cluster"
	"maas.io/core/src/maasagent/internal/dhcp"
)

var (
	dataPath  string
	dbDir     string
	reportDir string
	logDest   string
	logLvl    string
	logColor  bool
	id        string
)

var (
	ErrInvalidDataPath = errors.New("the path provided is not a valid dhcp data file")
)

func setupLogger(lvl, dst string, color bool) (func() error, error) {
	var (
		out     io.Writer
		cleanup func() error
	)

	if dst != "" {
		f, err := os.OpenFile(dst, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644) //nolint:gosec // this for a log
		if err != nil {
			return nil, err
		}

		out = f
		cleanup = f.Close
	} else {
		out = os.Stdout
		cleanup = func() error { return nil }
	}

	writer := zerolog.ConsoleWriter{Out: out, NoColor: !color}
	writer.PartsOrder = []string{
		zerolog.LevelFieldName,
		zerolog.CallerFieldName,
		zerolog.MessageFieldName,
	}
	log.Logger = zerolog.New(writer).With().Logger()

	ll, err := zerolog.ParseLevel(lvl)
	if err != nil {
		if f, ok := out.(*os.File); ok {
			cErr := f.Close()
			if cErr != nil {
				fmt.Println(cErr)
			}
		}

		return nil, err
	}

	zerolog.SetGlobalLevel(ll)

	log.Info().Msgf("Logger is configured with log level %q", ll.String())

	return cleanup, nil
}

func loadData(p string) (dhcp.ConfigDQLiteParam, error) {
	var config dhcp.ConfigDQLiteParam

	data, err := os.ReadFile(filepath.Clean(p))
	if err != nil {
		return dhcp.ConfigDQLiteParam{}, err
	}

	if strings.HasSuffix(filepath.Base(p), ".yaml") || strings.HasSuffix(filepath.Base(p), ".yml") {
		err = yaml.Unmarshal([]byte(data), &config)
		if err != nil {
			return dhcp.ConfigDQLiteParam{}, err
		}

		return config, nil
	} else if strings.HasSuffix(filepath.Base(p), ".json") {
		err = json.Unmarshal([]byte(data), &config)
		if err != nil {
			return dhcp.ConfigDQLiteParam{}, err
		}

		return config, nil
	}

	return dhcp.ConfigDQLiteParam{}, ErrInvalidDataPath
}

func run() int {
	flag.StringVar(&dataPath, "f", "./data.yaml", "path to yaml file with test data")
	flag.StringVar(&logDest, "o", "", "where to output logs, unset will output to stdout")
	flag.StringVar(&logLvl, "l", "info", "log level to output")
	flag.BoolVar(&logColor, "c", false, "enable log color highlighting")
	flag.StringVar(&dbDir, "d", "/tmp/maas-dhcp-db", "path to create microcluster data dir")
	flag.StringVar(&id, "i", "maas-dhcp-test", "id for services to identify as")
	flag.StringVar(&reportDir, "r", "/tmp/", "path to dhcp report data")
	flag.Parse()

	cleanup, err := setupLogger(logLvl, logDest, logColor)
	if err != nil {
		fmt.Println(err)

		return 2
	}

	defer func() {
		err = cleanup()
		if err != nil {
			// if we fail to cleanup a log file, output to stdout without the logger
			fmt.Printf("failed to cleanup log file: %s\n", err)
		}
	}()

	data, err := loadData(dataPath)
	if err != nil {
		log.Err(err).Msg("failed loading test data")

		return 2
	}

	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	var (
		clusterService *cluster.ClusterService
		dhcpService    *dhcp.DHCPService
	)

	testServer := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusCreated)
	}))

	testURL, err := url.Parse("http://localhost/dummy")
	if err != nil {
		log.Err(err).Send()
		return 2
	}

	mockAPIClient := apiclient.NewAPIClient(testURL, testServer.Client())

	dhcpService = dhcp.NewDHCPService(
		id,
		nil,
		nil,
		true,
		dhcp.WithDataPathFactory(func(s string) string {
			return filepath.Join(reportDir, s)
		}),
		dhcp.WithAPIClient(mockAPIClient),
	)

	clusterService, err = cluster.NewClusterService(
		id,
		cluster.WithDataPathFactory(func(s string) string {
			return filepath.Join(dbDir, s)
		}),
		cluster.WithClusterHooks(&state.Hooks{
			PreInit: func(_ context.Context, _ state.State, _ bool, _ map[string]string) error { return nil },
			OnStart: func(ctx context.Context, _ state.State) error {
				log.Info().Msg("microcluster started")

				return clusterService.OnStart(ctx)
			},
			PostBootstrap: func(ctx context.Context, s state.State, _ map[string]string) error {
				log.Info().Msg("microcluster bootstrapped")

				err = dhcpService.OnBootstrap(ctx, s)
				if err != nil {
					log.Err(err).Send()
					return err
				}

				err = dhcpService.ConfigureDQLiteDirect(ctx, data)
				log.Err(err).Send()

				return err
			},
			PostJoin: func(ctx context.Context, s state.State, _ map[string]string) error {
				log.Info().Msg("microcluster joined a cluster")

				err = dhcpService.OnJoin(ctx, s)
				if err != nil {
					return err
				}

				return dhcpService.ConfigureDQLiteDirect(ctx, data)
			},
		}),
	)
	if err != nil {
		log.Err(err).Msg("failed to initial cluster service")

		return 2
	}

	fatal := make(chan error)

	go func() {
		cErr := clusterService.ConfigureDirect(ctx)
		if cErr != nil {
			fatal <- cErr
		}
	}()

	sig := make(chan os.Signal, 2)
	signal.Notify(sig, syscall.SIGINT, syscall.SIGTERM)

	select {
	case <-sig:
		return 0
	case err = <-fatal:
		log.Err(err).Send()

		return 1
	}
}

func main() {
	os.Exit(run())
}
