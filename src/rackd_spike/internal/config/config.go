package config

import (
	"context"
	"fmt"
	"math"
	"os"
	"path/filepath"

	valid "github.com/asaskevich/govalidator"
	"github.com/rs/zerolog/log"
	"gopkg.in/yaml.v3"
)

const (
	ConfigFileEnvVarname = "MAAS_CLUSTER_CONFIG"
	ConfigFileDftFile    = "/etc/maas/rackd.conf"
	BaseDirEnvVarname    = "MAAS_DATA"
	TftpGrubDir          = "grub" // FIXME move this to TFTP module
)

type RackConfig struct {
	BasePath    string      `yaml:"-"`
	MaasUrl     StringArray `yaml:"maas_url,flow"`
	TftpRoot    string      `yaml:"tftp_root,omitempty"`
	TftpPort    int         `yaml:"tftp_port,omitempty"`
	ClusterUUID string      `yaml:"cluster_uuid,omitempty"`
	Debug       bool        `yaml:"debug,omitempty"`
}

// Config global rackd configuration
var (
	Config *RackConfig = new()
)

func isValid(c *RackConfig) error {
	if len(c.MaasUrl) == 0 {
		return fmt.Errorf("missing maas_url value")
	}
	for _, u := range c.MaasUrl {
		if !valid.IsURL(u) {
			return fmt.Errorf("invalid maas_url value: %v", u)
		}
	}
	if !valid.IsUnixFilePath(c.BasePath) {
		return fmt.Errorf("invalid MAAS_DATA value: %v", c.BasePath)
	}
	if !valid.IsUnixFilePath(c.TftpRoot) {
		return fmt.Errorf("invalid tftp_root value: %v", c.TftpRoot)
	}
	if !valid.InRange(c.TftpPort, 1, math.Pow(2, 16)-1) {
		return fmt.Errorf("invalid tftp_port value: %v", c.TftpPort)
	}
	if len(c.ClusterUUID) > 0 && !valid.IsUUIDv4(c.ClusterUUID) {
		return fmt.Errorf("invalid cluster_uuid value: %v", c.ClusterUUID)
	}
	return nil
}

func new() *RackConfig {
	return &RackConfig{
		BasePath: "/var/lib/maas",
		MaasUrl:  []string{"http://localhost:5240/MAAS"},
		TftpRoot: "boot-resources/current",
		TftpPort: 69,
	}
}

func getConfigFile(filename string) string {
	if len(filename) > 0 {
		return filename
	}

	if f, ok := os.LookupEnv(ConfigFileEnvVarname); ok {
		return f
	}

	return ConfigFileDftFile
}

func Load(ctx context.Context, filename string) (err error) {
	defer func() {
		log.Ctx(ctx).Err(err).Msgf("configuration file: %s", filename)
	}()

	filename = getConfigFile(filename)
	if _, err = os.Stat(filename); os.IsNotExist(err) {
		// not fatal
		log.Ctx(ctx).Warn().Msg("configuration file does not exist")
		return nil
	}

	newCfg := new()

	if f, ok := os.LookupEnv(BaseDirEnvVarname); ok && len(f) > 0 {
		newCfg.BasePath = f
	}

	data, err := os.ReadFile(filename)
	if err != nil {
		return err
	}

	err = yaml.Unmarshal([]byte(data), newCfg)
	if err != nil {
		return
	}

	err = isValid(newCfg)
	if err != nil {
		return
	}

	*Config = *newCfg
	return
}

func Save(ctx context.Context, filename string) (err error) {
	defer func() {
		log.Ctx(ctx).Err(err).Msgf("save configuration file: %s", filename)
	}()

	filename = getConfigFile(filename)

	err = isValid(Config)
	if err != nil {
		return
	}

	data, err := yaml.Marshal(Config)
	if err != nil {
		return
	}

	err = os.WriteFile(filename, []byte(data), 0644)
	return
}

func GetAbsPath(path string) string {
	if !filepath.IsAbs(path) {
		return filepath.Join(Config.BasePath, path)
	}
	return path
}

func GetTftpPath(path string) string {
	return filepath.Join(GetAbsPath(Config.TftpRoot), path)
}
