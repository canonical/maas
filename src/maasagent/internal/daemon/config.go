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

package daemon

import (
	"bytes"
	"embed"
	"fmt"
	"math"
	"net/url"
	"path/filepath"
	"strings"
	"text/template"
	"time"

	humanize "github.com/dustin/go-humanize"
	"github.com/spf13/afero"
	"gopkg.in/yaml.v3"
	"maas.io/core/src/maasagent/internal/atomicfile"
)

const configTemplateName = "config.yaml.tmpl"

//go:embed config.yaml.tmpl
var configFS embed.FS

var configTmpl = template.Must(
	template.New(configTemplateName).
		Funcs(template.FuncMap{
			"join": filepath.Join,
		}).
		ParseFS(configFS, configTemplateName),
)

type configOptions struct {
	ControllerURL string
	CacheDir      string
	CertDir       string
}

// generateConfig generates templated config that is then stored to disk and
// returns the parsed Config.
func generateConfig(fs afero.Fs, file string, opts configOptions) (*Config, error) {
	var buf bytes.Buffer

	if err := configTmpl.Execute(&buf, opts); err != nil {
		return nil, fmt.Errorf("render config template: %w", err)
	}

	data := buf.Bytes()

	if err := atomicfile.WriteFileWithFs(fs, file, data, 0o640); err != nil {
		return nil, fmt.Errorf("writing config: %w", err)
	}

	cfg := &Config{}
	if err := yaml.Unmarshal(buf.Bytes(), cfg); err != nil {
		return nil, fmt.Errorf("parse config: %w", err)
	}

	return cfg, nil
}

// loadConfig loads config from disk and returns the parsed Config.
func loadConfig(fs afero.Fs, file string) (*Config, error) {
	data, err := afero.ReadFile(fs, file)
	if err != nil {
		return nil, fmt.Errorf("reading config: %w", err)
	}

	cfg := &Config{}
	if err := yaml.Unmarshal(data, cfg); err != nil {
		return nil, fmt.Errorf("parse config: %w", err)
	}

	return cfg, nil
}

// Config represents the set of configuration options required by the MAAS agent.
type Config struct {
	// Unmarshalled via rawConfig
	ControllerURL *url.URL            `yaml:"-"`
	TLS           TLSConfig           `yaml:"tls"`
	Observability ObservabilityConfig `yaml:"observability"`
	Services      Services            `yaml:"services"`
}

// TLSConfig holds certificate and key file locations.
type TLSConfig struct {
	KeyFile  string `yaml:"key_file"`
	CertFile string `yaml:"cert_file"`
	CAFile   string `yaml:"ca_file"`
}

// Services aggregates configuration for all services provided by the agent.
type Services struct {
	HTTPProxy HTTPProxyConfig `yaml:"http_proxy"`
	DNS       DNSConfig       `yaml:"dns"`
}

// ObservabilityConfig holds configuration for logging, tracing, metrics,
// and profiling.
type ObservabilityConfig struct {
	Logging   LoggingConfig   `yaml:"logging"`
	Metrics   MetricsConfig   `yaml:"metrics"`
	Profiling ProfilingConfig `yaml:"profiling"`
}

type LogLevel string

const (
	DebugLevel LogLevel = "debug"
	InfoLevel  LogLevel = "info"
	WarnLevel  LogLevel = "warn"
	ErrorLevel LogLevel = "error"
)

// LoggingConfig holds the configuration for agent logging.
type LoggingConfig struct {
	// Level defines the minimum logging severity level (debug, info, warn, error).
	Level LogLevel `yaml:"level"`
}

// HTTPProxyConfig contains configuration for the HTTP proxy service.
type HTTPProxyConfig struct {
	Cache HTTPProxyCache `yaml:"cache"`
}

// HTTPProxyCache specifies cache settings for the HTTP proxy service.
type HTTPProxyCache struct {
	Dir  string          `yaml:"dir"`
	Size ByteSize[int64] `yaml:"size"`
}

// DNSConfig contains configuration for the agent's DNS resolver service.
type DNSConfig struct {
	Cache          DNSCache      `yaml:"cache"`
	DialTimeout    time.Duration `yaml:"dial_timeout"`
	ConnectionPool int           `yaml:"connection_pool"`
}

// DNSCache specifies cache sizing for DNS results.
type DNSCache struct {
	Size ByteSize[int64] `yaml:"size"`
}

// MetricsConfig enables or disables metrics collection for the agent.
type MetricsConfig struct {
	Enabled bool `yaml:"enabled"`
}

// ProfilingConfig enables or disables runtime profiling for the agent.
type ProfilingConfig struct {
	Enabled bool `yaml:"enabled"`
}

type Integeric interface {
	~uint16 | ~int64 | ~uint64
}

// ByteSize represents a size in bytes.
// It provides human-readable formatting and YAML serialization.
type ByteSize[T Integeric] struct {
	Bytes T
	Raw   string
}

// String returns the byte size formatted as a human-readable string
// with no spaces (e.g., "20GB", "512MB").
func (x ByteSize[T]) String() string {
	return strings.ReplaceAll(humanize.Bytes(uint64(x.Bytes)), " ", "")
}

// UnmarshalYAML implements the yaml.Unmarshaler interface.
// It parses a human-readable byte size string (e.g., "20GB", "512MB")
// and sets the value of the receiver.
// Returns an error if the input cannot be parsed.
func (x *ByteSize[T]) UnmarshalYAML(value *yaml.Node) error {
	x.Raw = value.Value

	parsed, err := humanize.ParseBytes(value.Value)
	if err != nil {
		return err
	}

	switch any(x.Bytes).(type) {
	case uint16:
		if parsed > math.MaxUint16 {
			return fmt.Errorf("value %d exceeds uint16 capacity", parsed)
		}
	case int64:
		if parsed > math.MaxInt64 {
			return fmt.Errorf("value %d exceeds int64 capacity", parsed)
		}
	}

	x.Bytes = T(parsed)

	return nil
}

// rawConfig can be considered a helper, having simple types for un/marshaling.
// For example Controller is a string instead of *url.URL.
type rawConfig struct {
	TLS           TLSConfig           `yaml:"tls"`
	Controller    string              `yaml:"controller"`
	Observability ObservabilityConfig `yaml:"observability"`
	Services      Services            `yaml:"services"`
}

// UnmarshalYAML implements the yaml.Unmarshaler interface for Config.
// It parses YAML data into a Config, converting the URL string to a url.URL.
func (c *Config) UnmarshalYAML(value *yaml.Node) error {
	var t rawConfig

	if err := value.Decode(&t); err != nil {
		return err
	}

	url, err := url.Parse(t.Controller)
	if err != nil {
		return err
	}

	c.ControllerURL = url
	c.Services = t.Services
	c.Observability = t.Observability
	c.TLS = t.TLS

	return nil
}

// DynamicConfig is something that users cannot set via configuration file.
// It is fetched from the controller.
type DynamicConfig struct {
	// Temporal configuration (including encryption key for data codec)
	Temporal TemporalConfig
	// SystemID is the MAAS system identifier for the machine or agent.
	SystemID string
	// RPCSecret used by rackd for backward compatibility
	RPCSecret string
	// MAAS API used by rackd
	MAASURL string
}

// TemporalConfig contains configuration for agent communication with Temporal.
type TemporalConfig struct {
	// EncryptionKey is used for Data Codec (to encrypt data)
	EncryptionKey string
}
