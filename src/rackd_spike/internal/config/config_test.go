package config_test

import (
	"context"
	"os"
	"rackd/internal/config"
	"reflect"

	"testing"
)

func TestRackConfig_Load(t *testing.T) {
	tests := []struct {
		name      string
		contents  string
		maas_data string
		c         *config.RackConfig
		wantErr   bool
	}{
		{
			"defaults",
			``,
			"",
			&config.RackConfig{
				BasePath: "/var/lib/maas",
				MaasUrl:  []string{"http://localhost:5240/MAAS"},
				TftpRoot: "boot-resources/current",
				TftpPort: 69,
			},
			false,
		},
		{
			"environment set",
			``,
			"/my-dir",
			&config.RackConfig{
				BasePath: "/my-dir",
				MaasUrl:  []string{"http://localhost:5240/MAAS"},
				TftpRoot: "boot-resources/current",
				TftpPort: 69,
			},
			false,
		},
		{
			"invalid port",
			`tftp_port: 100000
			`,
			"",
			nil,
			true,
		},
		{
			"valid UUID",
			`cluster_uuid: 6d56b4e7-8df0-4bd3-b428-4a5bff6852eb`,
			"",
			&config.RackConfig{
				BasePath:    "/var/lib/maas",
				MaasUrl:     []string{"http://localhost:5240/MAAS"},
				TftpRoot:    "boot-resources/current",
				TftpPort:    69,
				ClusterUUID: "6d56b4e7-8df0-4bd3-b428-4a5bff6852eb",
			},
			false,
		},
		{
			"invalid UUID",
			`cluster_uuid: i-dont-know-what-a-uuid-is`,
			"",
			nil,
			true,
		},
		{
			"single URL",
			`maas_url: http://host1:5240/MAAS`,
			"",
			&config.RackConfig{
				BasePath: "/var/lib/maas",
				MaasUrl:  []string{"http://host1:5240/MAAS"},
				TftpRoot: "boot-resources/current",
				TftpPort: 69,
			},
			false,
		},
		{
			"multiple URLs",
			`maas_url: ['http://host1:5240/MAAS', 'http://host2/MAAS']`,
			"",
			&config.RackConfig{
				BasePath: "/var/lib/maas",
				MaasUrl: []string{
					"http://host1:5240/MAAS",
					"http://host2/MAAS",
				},
				TftpRoot: "boot-resources/current",
				TftpPort: 69,
			},
			false,
		},
		{
			"invalid URLs",
			`maas_url: ['host1:5240/MAAS', '/host2/MAAS', 'http://']`,
			"",
			nil,
			true,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if len(tt.maas_data) > 0 {
				os.Setenv(config.BaseDirEnvVarname, tt.maas_data)
				defer os.Unsetenv(config.BaseDirEnvVarname)
			}

			f, _ := os.CreateTemp(t.TempDir(), "config_test")
			_, _ = f.Write([]byte(tt.contents))
			f.Close()

			if err := config.Load(context.TODO(), f.Name()); (err != nil) != tt.wantErr {
				t.Fatalf("RackConfig.Load() error = %v, wantErr %v", err, tt.wantErr)
			}

			if !tt.wantErr && !reflect.DeepEqual(config.Config, tt.c) {
				t.Errorf("RackConfig.Load() got %v, wants %v", config.Config, tt.c)
			}
		})
	}
}

func TestRackConfig_SaveAndReload(t *testing.T) {
	tests := []struct {
		name    string
		c       *config.RackConfig
		wantErr bool
	}{
		{
			"defaults",
			&config.RackConfig{
				BasePath: "/var/lib/maas",
				MaasUrl:  []string{"http://localhost:5240/MAAS"},
				TftpRoot: "boot-resources/current",
				TftpPort: 69,
			},
			false,
		},
		{
			"multi-region",
			&config.RackConfig{
				BasePath: "/var/lib/maas",
				MaasUrl:  []string{"http://host1:5240/MAAS", "http://host2:5240/MAAS"},
				TftpRoot: "boot-resources/current",
				TftpPort: 69,
			},
			false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			*config.Config = *tt.c

			f, _ := os.CreateTemp(t.TempDir(), "config_test")
			f.Close()

			if err := config.Save(context.TODO(), f.Name()); (err != nil) != tt.wantErr {
				t.Fatalf("RackConfig.Save() error = %v, wantErr %v", err, tt.wantErr)
			}

			if err := config.Load(context.TODO(), f.Name()); (err != nil) != tt.wantErr {
				t.Fatalf("RackConfig.Load() error = %v, wantErr %v", err, tt.wantErr)
			}

			if !tt.wantErr && !reflect.DeepEqual(config.Config, tt.c) {
				t.Errorf("RackConfig.Load() got %v, wants %v", config.Config, tt.c)
			}
		})
	}
}
