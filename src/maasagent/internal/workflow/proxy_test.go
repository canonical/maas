package workflow

import (
	"context"
	"errors"
	"net/http"
	"net/url"
	"os"
	"path"
	"testing"

	"github.com/stretchr/testify/assert"
)

func TestGetSocketPath(t *testing.T) {
	testcases := map[string]struct {
		in  func(t *testing.T)
		out string
	}{
		"snap": {
			in: func(t *testing.T) {
				t.Setenv("SNAP", "/snap/maas/x1")
				t.Setenv("SNAP_DATA", "/var/snap/maas/x1")
			},
			out: "/var/snap/maas/x1/agent-http-proxy.sock",
		},
		"deb": {
			in: func(t *testing.T) {
				t.Setenv("SNAP", "")
			}, out: "/var/lib/maas/agent-http-proxy.sock",
		},
	}

	for name, tc := range testcases {
		tc := tc

		t.Run(name, func(t *testing.T) {
			tc.in(t)
			res := getSocketFilePath()
			assert.Equal(t, tc.out, res)
		})
	}
}

func TestHTTPProxyConfiguratorConfigureHTTPProxy(t *testing.T) {
	table := map[string]struct {
		NumCalls int
		Params   []configureHTTPProxyParam
		Err      error
	}{
		"one_call": {
			NumCalls: 1,
			Params: []configureHTTPProxyParam{
				{
					Endpoints: []struct {
						Endpoint string
						Subnet   string
					}{
						{
							Endpoint: "http://localhost:5240/MAAS",
							Subnet:   "0.0.0.0/0", // allow all IPs to match
						},
					},
				},
			},
		},
		"two_calls": {
			NumCalls: 2,
			Params: []configureHTTPProxyParam{
				{
					Endpoints: []struct {
						Endpoint string
						Subnet   string
					}{
						{
							Endpoint: "http://localhost:5240/MAAS",
							Subnet:   "0.0.0.0/0",
						},
					},
				},
				{
					Endpoints: []struct {
						Endpoint string
						Subnet   string
					}{
						{
							Endpoint: "http://10.0.0.1:5240/MAAS",
							Subnet:   "0.0.0.0/0",
						},
					},
				},
			},
		},
		"three_calls": {
			NumCalls: 3,
			Params: []configureHTTPProxyParam{
				{
					Endpoints: []struct {
						Endpoint string
						Subnet   string
					}{
						{
							Endpoint: "http://localhost:5240/MAAS",
							Subnet:   "0.0.0.0/0",
						},
					},
				},
				{
					Endpoints: []struct {
						Endpoint string
						Subnet   string
					}{
						{
							Endpoint: "http://10.0.0.1:5240/MAAS",
							Subnet:   "0.0.0.0/0",
						},
					},
				},
				{
					Endpoints: []struct {
						Endpoint string
						Subnet   string
					}{
						{
							Endpoint: "http://10.0.1.1:5240/MAAS",
							Subnet:   "0.0.0.0/0",
						},
					},
				},
			},
		},
		"no-matching-origins": {
			NumCalls: 1,
			Params: []configureHTTPProxyParam{
				{
					Endpoints: []struct {
						Endpoint string
						Subnet   string
					}{
						{
							Endpoint: "http://1.1.1.1:5240/MAAS",
							Subnet:   "1.1.1.1/32",
						},
					},
				},
			},
			Err: ErrNoConfiguredOrigins,
		},
	}

	for tname, tcase := range table {
		t.Run(tname, func(tt *testing.T) {
			tmpDir, err := os.MkdirTemp("", "TestConfigureHTTPProxy*")
			if err != nil {
				tt.Fatal(err)
			}

			configurator := &HTTPProxyConfigurator{
				ready:               make(chan struct{}),
				imageCacheSize:      1,
				imageCacheLocation:  tmpDir,
				proxySocketLocation: path.Join(tmpDir, "maas-http-proxy.sock"),
			}

			ctx, cancel := context.WithCancel(context.Background())
			start := make(chan struct{})
			done := make(chan struct{})

			go func() {
				for {
					select {
					case <-ctx.Done():
						done <- struct{}{}
						return
					case <-configurator.Ready():
						start <- struct{}{}
						err = configurator.Proxies.Listen(ctx)
						if err != nil && !errors.Is(err, http.ErrServerClosed) {
							// panic to exit and fail test from non-test goroutine
							panic(err)
						}
					}
				}
			}()

			for i := 0; i < tcase.NumCalls; i++ {
				err = configurator.ConfigureHTTPProxy(ctx, tcase.Params[i])
				if err != nil {
					if tcase.Err != nil {
						assert.ErrorIs(tt, err, tcase.Err)
						cancel()
						return
					}

					tt.Fatal(err)
				}

				<-start

				for j := 0; j < configurator.Proxies.Size(); j++ {
					proxy := configurator.Proxies.GetProxyAt(j)

					var origin *url.URL

					origin, err = proxy.GetOrigin()
					if err != nil {
						tt.Fatal(err)
					}

					assert.Equal(tt, tcase.Params[i].Endpoints[0].Endpoint, origin.String())
				}
			}

			err = configurator.Proxies.Teardown(ctx)
			if err != nil {
				tt.Fatal(err)
			}

			cancel()
			<-done
		})
	}
}
