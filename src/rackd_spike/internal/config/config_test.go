package config

import (
	"context"
	"os"
	"reflect"

	"testing"
)

func TestRackConfig_Load(t *testing.T) {
	tests := []struct {
		name      string
		contents  string
		maas_data string
		c         *RackConfig
		wantErr   bool
	}{
		{
			"defaults",
			``,
			"",
			&RackConfig{
				BasePath:       "/var/lib/maas",
				MaasUrl:        []string{"http://localhost:5240/MAAS"},
				SupervisordURL: "http://localhost:9002",
				TftpRoot:       "boot-resources/current",
				TftpPort:       69,
				Metrics: MetricsConfig{
					Bind: "0.0.0.0",
					Port: 9090,
				},
				Tls: TlsConfig{
					SkipCaCheck: true,
				},
			},
			false,
		},
		{
			"environment set",
			``,
			"/my-dir",
			&RackConfig{
				BasePath:       "/my-dir",
				MaasUrl:        []string{"http://localhost:5240/MAAS"},
				SupervisordURL: "http://localhost:9002",
				TftpRoot:       "boot-resources/current",
				TftpPort:       69,
				Metrics: MetricsConfig{
					Bind: "0.0.0.0",
					Port: 9090,
				},
				Tls: TlsConfig{
					SkipCaCheck: true,
				},
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
			&RackConfig{
				BasePath:       "/var/lib/maas",
				MaasUrl:        []string{"http://localhost:5240/MAAS"},
				SupervisordURL: "http://localhost:9002",
				TftpRoot:       "boot-resources/current",
				TftpPort:       69,
				ClusterUUID:    "6d56b4e7-8df0-4bd3-b428-4a5bff6852eb",
				Metrics: MetricsConfig{
					Bind: "0.0.0.0",
					Port: 9090,
				},
				Tls: TlsConfig{
					SkipCaCheck: true,
				},
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
			&RackConfig{
				BasePath:       "/var/lib/maas",
				MaasUrl:        []string{"http://host1:5240/MAAS"},
				TftpRoot:       "boot-resources/current",
				TftpPort:       69,
				SupervisordURL: "http://localhost:9002",
				Metrics: MetricsConfig{
					Bind: "0.0.0.0",
					Port: 9090,
				},
				Tls: TlsConfig{
					SkipCaCheck: true,
				},
			},
			false,
		},
		{
			"multiple URLs",
			`maas_url: ['http://host1:5240/MAAS', 'http://host2/MAAS']`,
			"",
			&RackConfig{
				BasePath: "/var/lib/maas",
				MaasUrl: []string{
					"http://host1:5240/MAAS",
					"http://host2/MAAS",
				},
				SupervisordURL: "http://localhost:9002",
				TftpRoot:       "boot-resources/current",
				TftpPort:       69,
				Metrics: MetricsConfig{
					Bind: "0.0.0.0",
					Port: 9090,
				},
				Tls: TlsConfig{
					SkipCaCheck: true,
				},
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
				os.Setenv(baseDirEnvVarname, tt.maas_data)
				defer os.Unsetenv(baseDirEnvVarname)
			}

			f, _ := os.CreateTemp(t.TempDir(), "config_test")
			_, _ = f.Write([]byte(tt.contents))
			f.Close()

			if err := loadGlobal(context.TODO(), f.Name()); (err != nil) != tt.wantErr {
				t.Fatalf("RackConfig.loadGlobal() error = %v, wantErr %v", err, tt.wantErr)
			}

			if !tt.wantErr && !reflect.DeepEqual(Config, tt.c) {
				t.Errorf("RackConfig.loadGlobal() got %v, wants %v", Config, tt.c)
			}
		})
	}
}

func TestRackConfig_SaveAndReload(t *testing.T) {
	tests := []struct {
		name    string
		c       *RackConfig
		wantErr bool
	}{
		{
			"defaults",
			&RackConfig{
				BasePath:       "/var/lib/maas",
				MaasUrl:        []string{"http://localhost:5240/MAAS"},
				SupervisordURL: "http://localhost:9002",
				TftpRoot:       "boot-resources/current",
				TftpPort:       69,
				Metrics: MetricsConfig{
					Bind: "0.0.0.0",
					Port: 9090,
				},
				Tls: TlsConfig{
					SkipCaCheck: true,
				},
			},
			false,
		},
		{
			"multi-region",
			&RackConfig{
				BasePath:       "/var/lib/maas",
				MaasUrl:        []string{"http://host1:5240/MAAS", "http://host2:5240/MAAS"},
				SupervisordURL: "http://localhost:9002",
				TftpRoot:       "boot-resources/current",
				TftpPort:       69,
				Metrics: MetricsConfig{
					Bind: "0.0.0.0",
					Port: 9090,
				},
				Tls: TlsConfig{
					SkipCaCheck: true,
				},
			},
			false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			*Config = *tt.c

			f, _ := os.CreateTemp(t.TempDir(), "config_test")
			f.Close()

			if err := saveGlobal(context.TODO(), f.Name()); (err != nil) != tt.wantErr {
				t.Fatalf("RackConfig.Save() error = %v, wantErr %v", err, tt.wantErr)
			}

			if err := loadGlobal(context.TODO(), f.Name()); (err != nil) != tt.wantErr {
				t.Fatalf("RackConfig.Load() error = %v, wantErr %v", err, tt.wantErr)
			}

			if !tt.wantErr && !reflect.DeepEqual(Config, tt.c) {
				t.Errorf("RackConfig.Load() got %v, wants %v", Config, tt.c)
			}
		})
	}
}
