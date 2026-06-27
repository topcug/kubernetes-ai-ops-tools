package config

import (
	"os"
	"path/filepath"

	"gopkg.in/yaml.v3"
)

// Config holds optional user configuration loaded from .kubectl-triage.yaml.
// All fields are optional — zero values mean "use the default".
type Config struct {
	DefaultNamespace string `yaml:"defaultNamespace"`
	OutputFormat     string `yaml:"outputFormat"`
	TimeoutSeconds   int    `yaml:"timeoutSeconds"`
	Verbose          bool   `yaml:"verbose"`
	Quiet            bool   `yaml:"quiet"`
}

// Load reads .kubectl-triage.yaml from the current directory or $HOME.
// Returns an empty Config (no error) if no config file is found.
func Load() (*Config, error) {
	candidates := []string{
		".kubectl-triage.yaml",
		filepath.Join(os.Getenv("HOME"), ".kubectl-triage.yaml"),
	}

	for _, path := range candidates {
		data, err := os.ReadFile(path)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return nil, err
		}
		cfg := &Config{}
		if err := yaml.Unmarshal(data, cfg); err != nil {
			return nil, err
		}
		return cfg, nil
	}

	return &Config{}, nil
}
