VERSION:=develop-$(shell git rev-list -1 HEAD)

PATH:=$(shell go env GOPATH)/bin:${PATH}
export PATH

LDFLAGS="-X main.Version=$(VERSION) -s -w"

all: version test build

version:
	@go version

build: rackd

build-dir:
	mkdir -p ./build

rackd: build-dir
	go build -ldflags $(LDFLAGS) -o ./build/rackd ./cmd/rackd.go

test:
	go test ./...

lint:
	go vet ./...

format:
	gofmt -s -d ./cmd ./internal ./pkg
