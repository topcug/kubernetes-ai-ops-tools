package scanner

import (
	"encoding/json"
	"fmt"
	"os/exec"
)

type TrivyScanner struct{}

type trivyResult struct {
	Results []struct {
		Target          string `json:"Target"`
		Vulnerabilities []struct {
			VulnerabilityID string  `json:"VulnerabilityID"`
			PkgName         string  `json:"PkgName"`
			InstalledVersion string `json:"InstalledVersion"`
			FixedVersion    string  `json:"FixedVersion"`
			Severity        string  `json:"Severity"`
			Title           string  `json:"Title"`
			Description     string  `json:"Description"`
			CVSS            struct {
				NVD struct {
					V3Score float64 `json:"V3Score"`
				} `json:"nvd"`
			} `json:"CVSS"`
			References []string `json:"References"`
		} `json:"Vulnerabilities"`
	} `json:"Results"`
}

func NewTrivyScanner() *TrivyScanner {
	return &TrivyScanner{}
}

func (t *TrivyScanner) Name() string {
	return "trivy"
}

func (t *TrivyScanner) IsInstalled() bool {
	_, err := exec.LookPath("trivy")
	return err == nil
}

func (t *TrivyScanner) Scan(target string) (*ScanResult, error) {
	if !t.IsInstalled() {
		return nil, fmt.Errorf("trivy is not installed")
	}

	cmd := exec.Command("trivy", "image", "--format", "json", "--quiet", target)
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("trivy scan failed: %w", err)
	}

	var trivyRes trivyResult
	if err := json.Unmarshal(output, &trivyRes); err != nil {
		return nil, fmt.Errorf("failed to parse trivy output: %w", err)
	}

	result := &ScanResult{
		Scanner: "Trivy",
		Target:  target,
	}

	for _, r := range trivyRes.Results {
		for _, v := range r.Vulnerabilities {
			vuln := Vulnerability{
				ID:          v.VulnerabilityID,
				Severity:    v.Severity,
				Title:       v.Title,
				Description: v.Description,
				Package:     v.PkgName,
				Version:     v.InstalledVersion,
				FixVersion:  v.FixedVersion,
				CVSS:        v.CVSS.NVD.V3Score,
				References:  v.References,
				Image:       target,
			}
			result.Vulnerabilities = append(result.Vulnerabilities, vuln)
		}
	}

	return result, nil
}
