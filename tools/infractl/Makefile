BINARY  := infractl
VERSION := 1.0.0
LDFLAGS := -ldflags="-s -w -X main.version=$(VERSION)"

.PHONY: build build-linux tidy clean

build:
	go build $(LDFLAGS) -o $(BINARY) .

build-linux:
	CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build $(LDFLAGS) -o $(BINARY)-linux .

tidy:
	go mod tidy

clean:
	rm -f $(BINARY) $(BINARY)-linux
