.PHONY: build clean install release

VERSION ?= $(shell git describe --tags --always --dirty)

build:
	go build -ldflags "-X main.version=$(VERSION)" -o secclear ./cmd/secclear

clean:
	rm -f secclear secclear-*

install: build
	sudo mv secclear /usr/local/bin/

release:
	GOOS=linux GOARCH=amd64 go build -ldflags "-X main.version=$(VERSION)" -o secclear-linux-amd64 ./cmd/secclear
	GOOS=darwin GOARCH=amd64 go build -ldflags "-X main.version=$(VERSION)" -o secclear-darwin-amd64 ./cmd/secclear
	GOOS=darwin GOARCH=arm64 go build -ldflags "-X main.version=$(VERSION)" -o secclear-darwin-arm64 ./cmd/secclear
	GOOS=windows GOARCH=amd64 go build -ldflags "-X main.version=$(VERSION)" -o secclear-windows-amd64.exe ./cmd/secclear

test:
	go test ./...
