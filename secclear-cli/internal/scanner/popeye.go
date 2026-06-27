package scanner

import (
	"encoding/json"
	"fmt"
	"os/exec"
)

type PopeyeScanner struct{}

func NewPopeyeScanner() *PopeyeScanner {
	return &PopeyeScanner{}
}

func (p *PopeyeScanner) Name() string {
	return "Popeye"
}

func (p *PopeyeScanner) IsInstalled() bool {
	cmd := exec.Command("popeye", "version")
	return cmd.Run() == nil
}

func (p *PopeyeScanner) Scan(target string) (*ScanResult, error) {
	cmd := exec.Command("popeye", "-A", "-s", "po,svc,deploy,cm", "-o", "json", "--force-exit-zero")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("popeye scan failed: %w", err)
	}

	var popeyeResult struct {
		Popeye struct {
			Sections []struct {
				Linter string `json:"linter"`
				Issues map[string][]struct {
					Group   string `json:"group"`
					GVR     string `json:"gvr"`
					Level   int    `json:"level"`
					Message string `json:"message"`
				} `json:"issues"`
			} `json:"sections"`
		} `json:"popeye"`
	}

	if err := json.Unmarshal(output, &popeyeResult); err != nil {
		return nil, fmt.Errorf("failed to parse popeye output: %w", err)
	}

	result := &ScanResult{
		Scanner: "Popeye",
		Target:  target,
	}

	issueCount := 0
	
	for _, section := range popeyeResult.Popeye.Sections {
		for resourceName, issues := range section.Issues {
			for _, issue := range issues {
				if issue.Level >= 2 {
					severity := "MEDIUM"
					if issue.Level == 3 {
						severity = "HIGH"
					}
					
					issueCount++
					vuln := Vulnerability{
						ID:          fmt.Sprintf("POP-%d", issueCount),
						Severity:    severity,
						Title:       issue.Message,
						Description: fmt.Sprintf("%s: %s", section.Linter, resourceName),
						Package:     "kubernetes-config",
						Version:     "cluster",
						FixVersion:  "Configuration remediation required",
						Image:       resourceName,
					}
					result.Vulnerabilities = append(result.Vulnerabilities, vuln)
				}
			}
		}
	}

	return result, nil
}
