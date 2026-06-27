.PHONY: build test lint install clean release-snapshot

BINARY := kubectl-triage
VERSION ?= $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
LDFLAGS := -s -w -X main.version=$(VERSION)

## build: compile for the current platform
build:
	go build -ldflags "$(LDFLAGS)" -o bin/$(BINARY) ./main.go

## test: run all tests with race detector
test:
	go test -race -count=1 ./...

## fmt: format all Go source files
fmt:
	gofmt -w ./...

## lint: run golangci-lint (requires golangci-lint installed)
lint:
	golangci-lint run ./...

## install: install the plugin to GOPATH/bin so 'kubectl triage' works immediately
install:
	go install -ldflags "$(LDFLAGS)" ./...

## clean: remove build artefacts
clean:
	rm -rf bin/ dist/

## release-snapshot: test goreleaser without publishing
release-snapshot:
	goreleaser release --snapshot --clean

## snapshot: test goreleaser without publishing (alias)
snapshot: release-snapshot

## help: print this help
help:
	@grep -E '^##' Makefile | sed 's/## //'
