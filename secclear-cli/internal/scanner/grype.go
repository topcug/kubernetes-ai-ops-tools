package scanner

import (
	"encoding/json"
	"fmt"
	"os/exec"
)

type GrypeScanner struct{}

type grypeResult struct {
	Matches []struct {
		Vulnerability struct {
			ID          string   `json:"id"`
			Severity    string   `json:"severity"`
			Description string   `json:"description"`
			URLs        []string `json:"urls"`
		} `json:"vulnerability"`
		Artifact struct {
			Name    string `json:"name"`
			Version string `json:"version"`
		} `json:"artifact"`
		MatchDetails []struct {
			Found struct {
				VersionConstraint string `json:"versionConstraint"`
			} `json:"found"`
		} `json:"matchDetails"`
	} `json:"matches"`
}

func NewGrypeScanner() *GrypeScanner {
	return &GrypeScanner{}
}

func (g *GrypeScanner) Name() string {
	return "grype"
}

func (g *GrypeScanner) IsInstalled() bool {
	_, err := exec.LookPath("grype")
	return err == nil
}

func (g *GrypeScanner) Scan(target string) (*ScanResult, error) {
	if !g.IsInstalled() {
		return nil, fmt.Errorf("grype is not installed")
	}

	cmd := exec.Command("grype", target, "-o", "json", "-q")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("grype scan failed: %w", err)
	}

	var grypeRes grypeResult
	if err := json.Unmarshal(output, &grypeRes); err != nil {
		return nil, fmt.Errorf("failed to parse grype output: %w", err)
	}

	result := &ScanResult{
		Scanner: "Grype",
		Target:  target,
	}

	for _, match := range grypeRes.Matches {
		fixVersion := ""
		if len(match.MatchDetails) > 0 {
			fixVersion = match.MatchDetails[0].Found.VersionConstraint
		}

		vuln := Vulnerability{
			ID:          match.Vulnerability.ID,
			Severity:    match.Vulnerability.Severity,
			Title:       "",
			Description: match.Vulnerability.Description,
			Package:     match.Artifact.Name,
			Version:     match.Artifact.Version,
			FixVersion:  fixVersion,
			CVSS:        0.0,
			References:  match.Vulnerability.URLs,
			Image:       target,
		}
		result.Vulnerabilities = append(result.Vulnerabilities, vuln)
	}

	return result, nil
}
