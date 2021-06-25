VERSION:=develop-$(shell git rev-list -1 HEAD)

all: test build

build: rackd

build-dir:
	mkdir -p ./build

rackd: build-dir
	go build -ldflags "-X main.Version=$(VERSION)" -o ./build/rackd ./cmd/rackd.go

test:
	go test ./...
