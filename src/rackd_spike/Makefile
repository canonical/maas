VERSION:=develop-$(shell git rev-list -1 HEAD)

PATH:=$(shell go env GOPATH)/bin:${PATH}
export PATH

all: test build

build: rackd

build-dir:
	mkdir -p ./build

rackd: build-dir
	go build -ldflags "-X main.Version=$(VERSION)" -o ./build/rackd ./cmd/rackd.go

test:
	go test ./...

lint:
	go vet ./...

format:
	gofmt -s -d ./cmd ./internal ./pkg
