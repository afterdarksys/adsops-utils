# After Dark Systems Change Management - Makefile

.PHONY: all build clean test lint run-api run-cli migrate help proto-gen proto-lint proto-breaking

# Go parameters
GOCMD=go
GOBUILD=$(GOCMD) build
GOTEST=$(GOCMD) test
GOGET=$(GOCMD) get
GOMOD=$(GOCMD) mod
BINARY_API=bin/api
BINARY_CLI=bin/changes
BINARY_WORKER=bin/worker
BINARY_MIGRATE=bin/migrate

# Build flags
LDFLAGS=-ldflags "-s -w"

all: build

## build: Build all binaries
build: build-api build-cli build-worker build-migrate

## build-api: Build the API server
build-api:
	$(GOBUILD) $(LDFLAGS) -o $(BINARY_API) ./cmd/api

## build-cli: Build the CLI tool
build-cli:
	$(GOBUILD) $(LDFLAGS) -o $(BINARY_CLI) ./cmd/cli

## build-worker: Build the background worker
build-worker:
	$(GOBUILD) $(LDFLAGS) -o $(BINARY_WORKER) ./cmd/worker

## build-migrate: Build the migration tool
build-migrate:
	$(GOBUILD) $(LDFLAGS) -o $(BINARY_MIGRATE) ./cmd/migrate

## clean: Remove build artifacts
clean:
	rm -rf bin/
	rm -f coverage.out coverage.html

## test: Run tests
test:
	$(GOTEST) -v -race -coverprofile=coverage.out ./...

## test-coverage: Run tests and generate coverage report
test-coverage: test
	$(GOCMD) tool cover -html=coverage.out -o coverage.html
	@echo "Coverage report generated: coverage.html"

## lint: Run linter
lint:
	golangci-lint run ./...

## run-api: Run the API server
run-api:
	$(GOCMD) run ./cmd/api

## run-cli: Run the CLI tool
run-cli:
	$(GOCMD) run ./cmd/cli $(ARGS)

## run-worker: Run the background worker
run-worker:
	$(GOCMD) run ./cmd/worker

## deps: Download dependencies
deps:
	$(GOMOD) download
	$(GOMOD) tidy

## migrate-up: Run database migrations
migrate-up:
	$(GOCMD) run ./cmd/migrate up

## migrate-down: Rollback database migrations
migrate-down:
	$(GOCMD) run ./cmd/migrate down

## migrate-status: Show migration status
migrate-status:
	$(GOCMD) run ./cmd/migrate status

## docker-build: Build Docker images
docker-build:
	docker build -f deployments/docker/Dockerfile.api -t adsops-api:latest .
	docker build -f deployments/docker/Dockerfile.cli -t adsops-cli:latest .
	docker build -f deployments/docker/Dockerfile.worker -t adsops-worker:latest .

## docker-compose-up: Start services with Docker Compose
docker-compose-up:
	docker-compose -f deployments/docker/docker-compose.yml up -d

## docker-compose-down: Stop services with Docker Compose
docker-compose-down:
	docker-compose -f deployments/docker/docker-compose.yml down

## generate: Generate code (mocks, etc.)
generate:
	$(GOCMD) generate ./...

## install-tools: Install development tools
install-tools:
	go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest
	go install github.com/golang-migrate/migrate/v4/cmd/migrate@latest
	go install github.com/air-verse/air@latest

## dev: Run API with live reload (requires air)
dev:
	air

## help: Show this help message
help:
	@echo "After Dark Systems Change Management"
	@echo ""
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@sed -n 's/^##//p' $(MAKEFILE_LIST) | column -t -s ':' | sed -e 's/^/ /'

## proto-gen: Generate Go and Python bindings from .proto files
proto-gen:
	buf generate
	find gen/python -type d -exec touch {}/__init__.py \;

## proto-lint: Lint .proto files
proto-lint:
	buf lint proto/

## proto-breaking: Check for breaking changes against main
proto-breaking:
	buf breaking proto/ --against '.git#branch=main,subdir=proto'
