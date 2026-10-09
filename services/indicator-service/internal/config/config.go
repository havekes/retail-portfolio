package config

import (
	"fmt"
	"strings"
)

// Config holds runtime configuration for indicator-service.
//
// Values are read from the environment:
//   - PORT: HTTP listen port (default "8080").
//   - ENVIRONMENT: deployment environment ("prod" or "dev", default "dev").
//   - LOG_LEVEL: log level override ("DEBUG", "INFO", "WARN"/"WARNING", "ERROR").
type Config struct {
	Port        string
	Environment string
	LogLevel    string
}

const (
	defaultPort        = "8080"
	defaultEnvironment = "dev"
)

// Load reads configuration using the provided getenv function.
// If LOG_LEVEL is invalid, it returns an error naming LOG_LEVEL.
func Load(getenv func(string) string) (Config, error) {
	env := strings.ToLower(strings.TrimSpace(getenv("ENVIRONMENT")))
	if env == "" {
		env = defaultEnvironment
	}

	logLevel := strings.ToUpper(strings.TrimSpace(getenv("LOG_LEVEL")))
	if logLevel != "" {
		switch logLevel {
		case "DEBUG", "INFO", "WARN", "WARNING", "ERROR":
		default:
			return Config{}, fmt.Errorf("invalid LOG_LEVEL %q: must be DEBUG, INFO, WARN, WARNING, or ERROR", logLevel)
		}
	}

	port := strings.TrimSpace(getenv("PORT"))
	if port == "" {
		port = defaultPort
	}

	return Config{
		Port:        port,
		Environment: env,
		LogLevel:    logLevel,
	}, nil
}
