package scanner

import (
	"bufio"
	"bytes"
	"fmt"
	"os/exec"
	"strings"
)

type KubeBenchScanner struct{}

func NewKubeBenchScanner() *KubeBenchScanner {
	return &KubeBenchScanner{}
}

func (k *KubeBenchScanner) Name() string {
	return "Kube-bench"
}

func (k *KubeBenchScanner) IsInstalled() bool {
	cmd := exec.Command("kube-bench", "version")
	return cmd.Run() == nil
}

func (k *KubeBenchScanner) Scan(target string) (*ScanResult, error) {
	// Try without sudo first
	cmd := exec.Command("kube-bench", "run")
	output, err := cmd.CombinedOutput()
	
	if err != nil {
		fmt.Printf("Warning: kube-bench failed (may need: sudo kube-bench run)\n")
		return &ScanResult{
			Scanner:         "Kube-bench",
			Target:          target,
			Vulnerabilities: []Vulnerability{},
		}, nil
	}

	result := &ScanResult{
		Scanner: "Kube-bench",
		Target:  target,
	}

	// Parse text output
	scanner := bufio.NewScanner(bytes.NewReader(output))
	for scanner.Scan() {
		line := scanner.Text()
		
		// Look for [FAIL] lines
		if strings.HasPrefix(line, "[FAIL]") {
			// Extract test ID and description
			parts := strings.SplitN(line, " ", 3)
			if len(parts) < 3 {
				continue
			}
			
			testID := parts[1]
			desc := parts[2]
			
			severity := "MEDIUM"
			if strings.Contains(desc, "encryption") || 
			   strings.Contains(desc, "authentication") ||
			   strings.Contains(desc, "600") ||
			   strings.Contains(desc, "644") {
				severity = "HIGH"
			}
			
			vuln := Vulnerability{
				ID:          testID,
				Severity:    severity,
				Title:       desc,
				Description: desc,
				Package:     "kubernetes-config",
				Version:     "cluster",
				FixVersion:  "See CIS Benchmark",
				Image:       "cluster",
			}
			result.Vulnerabilities = append(result.Vulnerabilities, vuln)
		}
	}

	return result, nil
}
