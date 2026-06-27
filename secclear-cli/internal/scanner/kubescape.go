package scanner

import (
	"encoding/json"
	"fmt"
	"os/exec"
)

type KubescapeScanner struct{}

type kubescapeResult struct {
	Results []struct {
		ResourceID string `json:"resourceID"`
		Controls   []struct {
			ControlID string `json:"controlID"`
			Name      string `json:"name"`
			Status    struct {
				Status string `json:"status"`
			} `json:"status"`
		} `json:"controls"`
	} `json:"results"`
}

func NewKubescapeScanner() *KubescapeScanner {
	return &KubescapeScanner{}
}

func (k *KubescapeScanner) Name() string {
	return "kubescape"
}

func (k *KubescapeScanner) IsInstalled() bool {
	_, err := exec.LookPath("kubescape")
	return err == nil
}

func (k *KubescapeScanner) Scan(target string) (*ScanResult, error) {
	if !k.IsInstalled() {
		return nil, fmt.Errorf("kubescape is not installed")
	}

	// Kubescape scans cluster configuration, not individual images
	// We'll run it once per scan, not per image
	cmd := exec.Command("kubescape", "scan", "framework", "nsa", "--format", "json", "-l", "error", "--keep-local")
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("kubescape scan failed: %w", err)
	}

	var kubeRes kubescapeResult
	if err := json.Unmarshal(output, &kubeRes); err != nil {
		return nil, fmt.Errorf("failed to parse kubescape output: %w", err)
	}

	result := &ScanResult{
		Scanner: "Kubescape",
		Target:  target,
	}

	// Count failed controls
	failedControls := make(map[string]struct {
		name  string
		count int
	})

	for _, res := range kubeRes.Results {
		for _, control := range res.Controls {
			if control.Status.Status == "failed" {
				if existing, ok := failedControls[control.ControlID]; ok {
					existing.count++
					failedControls[control.ControlID] = existing
				} else {
					failedControls[control.ControlID] = struct {
						name  string
						count int
					}{name: control.Name, count: 1}
				}
			}
		}
	}

	// Create vulnerabilities from failed controls
	for controlID, data := range failedControls {
		severity := "MEDIUM"
		if controlID == "C-0066" || controlID == "C-0067" || controlID == "C-0068" {
			severity = "HIGH"
		}

		vuln := Vulnerability{
			ID:          controlID,
			Severity:    severity,
			Title:       data.name,
			Description: fmt.Sprintf("Failed in %d resource(s)", data.count),
			Package:     "kubernetes-config",
			Version:     "cluster",
			FixVersion:  "Configuration remediation required",
			CVSS:        0.0,
			References:  []string{},
			FoundBy:     []string{"Kubescape"},
		}
		result.Vulnerabilities = append(result.Vulnerabilities, vuln)
	}

	return result, nil
}

func mapKubescapeSeverity(severity string) string {
	switch severity {
	case "Critical", "critical":
		return "CRITICAL"
	case "High", "high":
		return "HIGH"
	case "Medium", "medium":
		return "MEDIUM"
	case "Low", "low":
		return "LOW"
	default:
		return "MEDIUM"
	}
}
