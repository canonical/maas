package config

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"os"

	"github.com/rs/zerolog/log"
)

func GetMetricsTlsConfig(ctx context.Context) (*tls.Config, error) {
	if Config.Metrics.Cert == "" && Config.Metrics.Key == "" {
		return nil, nil
	}

	cer, err := tls.LoadX509KeyPair(Config.Metrics.Cert, Config.Metrics.Key)
	if err != nil {
		log.Ctx(ctx).Err(err).Msgf("failed to load cert %v - %v", Config.Metrics.Cert, Config.Metrics.Key)
		return nil, ErrBadTlsConfig
	}

	cfg := &tls.Config{
		Certificates: []tls.Certificate{cer},
	}

	if Config.Metrics.CACert != "" {
		// Load CA cert
		caCert, err := os.ReadFile(Config.Metrics.CACert)
		if err != nil {
			log.Ctx(ctx).Err(err).Msgf("failed to load CA cert %v", Config.Metrics.CACert)
			return nil, ErrBadTlsConfig
		}

		cfg.RootCAs = x509.NewCertPool()
		cfg.RootCAs.AppendCertsFromPEM(caCert)
	}

	return cfg, nil
}

func GetRpcTlsConfig(ctx context.Context) (*tls.Config, error) {
	cfg := &tls.Config{
		InsecureSkipVerify: Config.Tls.SkipCaCheck,
	}

	if Config.Tls.CACert != "" {
		// Load CA cert
		caCert, err := os.ReadFile(Config.Tls.CACert)
		if err != nil {
			log.Ctx(ctx).Err(err).Msgf("failed to load CA cert %v", Config.Tls.CACert)
			return nil, ErrBadTlsConfig
		}

		cfg.RootCAs = x509.NewCertPool()
		cfg.RootCAs.AppendCertsFromPEM(caCert)
	}

	if Config.Tls.Cert == "" && Config.Tls.Key == "" {
		return cfg, nil
	}

	cer, err := tls.LoadX509KeyPair(Config.Tls.Cert, Config.Tls.Key)
	if err != nil {
		log.Ctx(ctx).Err(err).Msgf("failed to load cert %v - %v", Config.Tls.Cert, Config.Tls.Key)
		return nil, ErrBadTlsConfig
	}
	cfg.Certificates = []tls.Certificate{cer}

	return cfg, nil
}
