module maas.io/core/src/maasagent

go 1.23.3

replace github.com/canonical/microcluster/v2 => github.com/troyanov/microcluster/v2 v2.0.0-20250311134004-d90590de8324

require (
	github.com/canonical/lxd v0.0.0-20250113143058-52441d41dab7
	github.com/canonical/microcluster/v2 v2.1.0
	github.com/canonical/pebble v1.10.2
	github.com/cenkalti/backoff/v4 v4.3.0
	github.com/google/gopacket v1.1.19
	github.com/hashicorp/golang-lru/v2 v2.0.7
	github.com/miekg/dns v1.1.63
	github.com/packetcap/go-pcap v0.0.0-20230509084824-080a85fb093e
	github.com/prometheus/client_golang v1.20.5
	github.com/rs/zerolog v1.29.1
	github.com/stretchr/testify v1.10.0
	go.opentelemetry.io/otel v1.33.0
	go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracehttp v1.29.0
	go.opentelemetry.io/otel/exporters/prometheus v0.50.0
	go.opentelemetry.io/otel/metric v1.33.0
	go.opentelemetry.io/otel/sdk v1.33.0
	go.opentelemetry.io/otel/sdk/metric v1.31.0
	go.opentelemetry.io/otel/trace v1.33.0
	go.temporal.io/api v1.36.0
	go.temporal.io/sdk v1.28.1
	go.temporal.io/sdk/contrib/opentelemetry v0.6.0
	golang.org/x/net v0.34.0
	golang.org/x/sync v0.10.0
	golang.org/x/tools v0.29.0
	gopkg.in/yaml.v3 v3.0.1
)

require (
	github.com/Rican7/retry v0.3.1 // indirect
	github.com/armon/go-proxyproto v0.1.0 // indirect
	github.com/beorn7/perks v1.0.1 // indirect
	github.com/canonical/go-dqlite/v2 v2.0.0 // indirect
	github.com/cespare/xxhash/v2 v2.3.0 // indirect
	github.com/davecgh/go-spew v1.1.2-0.20180830191138-d8f796af33cc // indirect
	github.com/facebookgo/clock v0.0.0-20150410010913-600d898af40a // indirect
	github.com/flosch/pongo2 v0.0.0-20200913210552-0d938eb266f3 // indirect
	github.com/fsnotify/fsnotify v1.8.0 // indirect
	github.com/go-jose/go-jose/v4 v4.0.4 // indirect
	github.com/go-logr/logr v1.4.2 // indirect
	github.com/go-logr/stdr v1.2.2 // indirect
	github.com/gogo/protobuf v1.3.2 // indirect
	github.com/golang/mock v1.6.0 // indirect
	github.com/google/renameio v1.0.1 // indirect
	github.com/google/uuid v1.6.0 // indirect
	github.com/gorilla/mux v1.8.1 // indirect
	github.com/gorilla/securecookie v1.1.2 // indirect
	github.com/gorilla/websocket v1.5.3 // indirect
	github.com/grpc-ecosystem/go-grpc-middleware v1.4.0 // indirect
	github.com/grpc-ecosystem/grpc-gateway/v2 v2.25.1 // indirect
	github.com/kballard/go-shellquote v0.0.0-20180428030007-95032a82bc51 // indirect
	github.com/klauspost/compress v1.17.11 // indirect
	github.com/kr/fs v0.1.0 // indirect
	github.com/mattn/go-colorable v0.1.14 // indirect
	github.com/mattn/go-isatty v0.0.20 // indirect
	github.com/mattn/go-sqlite3 v1.14.24 // indirect
	github.com/muhlemmer/gu v0.3.1 // indirect
	github.com/munnerz/goautoneg v0.0.0-20191010083416-a7dc8b61c822 // indirect
	github.com/nexus-rpc/sdk-go v0.0.9 // indirect
	github.com/pborman/uuid v1.2.1 // indirect
	github.com/pkg/errors v0.9.1 // indirect
	github.com/pkg/sftp v1.13.7 // indirect
	github.com/pkg/xattr v0.4.10 // indirect
	github.com/pmezard/go-difflib v1.0.1-0.20181226105442-5d4384ee4fb2 // indirect
	github.com/prometheus/client_model v0.6.1 // indirect
	github.com/prometheus/common v0.61.0 // indirect
	github.com/prometheus/procfs v0.15.1 // indirect
	github.com/robfig/cron v1.2.0 // indirect
	github.com/robfig/cron/v3 v3.0.1 // indirect
	github.com/sirupsen/logrus v1.9.3 // indirect
	github.com/stretchr/objx v0.5.2 // indirect
	github.com/zitadel/logging v0.6.1 // indirect
	github.com/zitadel/oidc/v3 v3.34.0 // indirect
	github.com/zitadel/schema v1.3.0 // indirect
	go.opentelemetry.io/auto/sdk v1.1.0 // indirect
	go.opentelemetry.io/otel/exporters/otlp/otlptrace v1.33.0 // indirect
	go.opentelemetry.io/proto/otlp v1.4.0 // indirect
	golang.org/x/crypto v0.32.0 // indirect
	golang.org/x/exp v0.0.0-20250103183323-7d7fa50e5329 // indirect
	golang.org/x/mod v0.22.0 // indirect
	golang.org/x/oauth2 v0.25.0 // indirect
	golang.org/x/sys v0.30.0 // indirect
	golang.org/x/term v0.28.0 // indirect
	golang.org/x/text v0.21.0 // indirect
	golang.org/x/time v0.5.0 // indirect
	google.golang.org/genproto/googleapis/api v0.0.0-20250102185135-69823020774d // indirect
	google.golang.org/genproto/googleapis/rpc v0.0.0-20250102185135-69823020774d // indirect
	google.golang.org/grpc v1.69.2 // indirect
	google.golang.org/protobuf v1.36.2 // indirect
	gopkg.in/yaml.v2 v2.4.0 // indirect
)
