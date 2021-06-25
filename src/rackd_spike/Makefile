all: test build

build: rackd

build-dir:
	mkdir -p ./build

rackd: build-dir
	go build -o ./build/rackd ./cmd/rackd.go

test:
	go test ./...
