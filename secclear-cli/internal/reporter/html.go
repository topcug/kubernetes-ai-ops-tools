package reporter

import (
	"fmt"
	"html"
	"sort"
	"strings"
	"time"

	"github.com/secclear/secclear-cli/internal/aggregator"
)

type HTMLReporter struct{}

func NewHTMLReporter() *HTMLReporter {
	return &HTMLReporter{}
}

func (h *HTMLReporter) GenerateComparison(result *aggregator.AggregatedResult, clusterName string) string {
	var sb strings.Builder

	sb.WriteString(`<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Scanner Comparison: ` + html.EscapeString(clusterName) + `</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { font-size: 2.5em; margin-bottom: 10px; color: #1a1a1a; }
        h2 { font-size: 1.8em; margin: 30px 0 15px; color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        h3 { font-size: 1.3em; margin: 20px 0 10px; color: #34495e; }
        .timestamp { color: #7f8c8d; font-size: 0.9em; margin-bottom: 30px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border: 1px solid #ddd; }
        th { background: #3498db; color: white; font-weight: bold; }
        tr:nth-child(even) { background: #f8f9fa; }
        .agreement-box { background: #e8f5e9; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #4caf50; }
        .unique-box { background: #fff3e0; padding: 15px; margin: 15px 0; border-radius: 5px; border-left: 4px solid #ff9800; }
        .recommendation { background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #2196f3; }
        ul { margin: 15px 0; padding-left: 25px; }
        li { margin: 8px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Scanner Comparison Report: ` + html.EscapeString(clusterName) + `</h1>
        <div class="timestamp">Generated: ` + time.Now().Format("2006-01-02 15:04:05") + `</div>
`)

	h.writeScannerComparisonHTML(&sb, result)

	sb.WriteString(`    </div>
</body>
</html>`)

	return sb.String()
}

func (h *HTMLReporter) writeScannerComparisonHTML(sb *strings.Builder, result *aggregator.AggregatedResult) {
	// Separate image scanners from cluster scanner
	imageScanners := []string{}
	
	for _, scanner := range result.Scanners {
		if scanner != "Kubescape" && scanner != "Kube-bench" && scanner != "Popeye" {
			imageScanners = append(imageScanners, scanner)
		}
	}
	
	// Count vulnerabilities per scanner
	scannerStats := make(map[string]map[string]int)
	for _, scanner := range result.Scanners {
		scannerStats[scanner] = map[string]int{
			"CRITICAL": 0,
			"HIGH":     0,
			"MEDIUM":   0,
			"LOW":      0,
			"TOTAL":    0,
		}
	}
	
	configIssues := 0
	configHigh := 0
	
	for _, vuln := range result.Vulnerabilities {
		if vuln.Package == "kubernetes-config" {
			configIssues++
			if vuln.Severity == "HIGH" || vuln.Severity == "CRITICAL" {
				configHigh++
			}
			continue
		}
		for _, scanner := range vuln.FoundBy {
			scannerStats[scanner][vuln.Severity]++
			scannerStats[scanner]["TOTAL"]++
		}
	}
	
	// Calculate agreement
	multiScannerVulns := 0
	uniqueFindings := make(map[string]int)
	imageVulns := 0
	
	for _, vuln := range result.Vulnerabilities {
		if vuln.Package != "kubernetes-config" {
			imageVulns++
			if len(vuln.FoundBy) > 1 {
				multiScannerVulns++
			} else if len(vuln.FoundBy) == 1 {
				uniqueFindings[vuln.FoundBy[0]]++
			}
		}
	}
	
	agreementPercent := 0
	if imageVulns > 0 {
		agreementPercent = int(float64(multiScannerVulns) / float64(imageVulns) * 100)
	}
	
	// WHAT TO DO section
	sb.WriteString(`        <div class="recommendation">
            <h2>WHAT TO DO</h2>
`)
	
	sb.WriteString(fmt.Sprintf(`            <p><strong>1. Keep using all %d scanners</strong> - Each catches different problems</p>
            <ul>
`, len(result.Scanners)))
	
	for _, scanner := range imageScanners {
		if scanner == "Popeye" || scanner == "Kube-bench" {
			continue
		}
		stats := scannerStats[scanner]
		sb.WriteString(fmt.Sprintf(`                <li>%s: Finds CVEs in container images (%d total, %d CRITICAL)</li>
`, html.EscapeString(scanner), stats["TOTAL"], stats["CRITICAL"]))
	}
	
	for _, scanner := range result.Scanners {
		if scanner == "Kubescape" || scanner == "Popeye" || scanner == "Kube-bench" {
			scannerIssues := 0
			scannerHigh := 0
			for _, vuln := range result.Vulnerabilities {
				if vuln.Package == "kubernetes-config" {
					for _, foundBy := range vuln.FoundBy {
						if foundBy == scanner {
							scannerIssues++
							if vuln.Severity == "HIGH" || vuln.Severity == "CRITICAL" {
								scannerHigh++
							}
							break
						}
					}
				}
			}
			sb.WriteString(fmt.Sprintf(`                <li>%s: Finds cluster config problems (%d issues, %d HIGH)</li>
`, html.EscapeString(scanner), scannerIssues, scannerHigh))
		}
	}
	
	sb.WriteString(`            </ul>
`)
	
	totalUnique := 0
	for _, count := range uniqueFindings {
		totalUnique += count
	}
	
	if len(imageScanners) >= 2 {
		sb.WriteString(fmt.Sprintf(`            <p><strong>2. Fix high-confidence issues first</strong><br>
            %d vulnerabilities found by multiple scanners</p>

            <p><strong>3. Review single-scanner findings</strong><br>
            %d total - may include false positives</p>
            <ul>
`, multiScannerVulns, totalUnique))
		
		for _, scanner := range imageScanners {
			if count, ok := uniqueFindings[scanner]; ok {
				sb.WriteString(fmt.Sprintf(`                <li>%s only: %d vulns</li>
`, html.EscapeString(scanner), count))
			}
		}
		
		sb.WriteString(`            </ul>
`)
	}
	
	sb.WriteString(`        </div>
`)
	
	// Scanner Performance
	sb.WriteString(`        <h2>Scanner Performance</h2>
        <div class="agreement-box">
`)
	
	// Image scanners only
	for _, scanner := range imageScanners {
		if scanner == "Kube-bench" || scanner == "Popeye" {
			continue
		}
		stats := scannerStats[scanner]
		sb.WriteString(fmt.Sprintf(`            <p><strong>%s:</strong> %d vulns (%d CRITICAL, %d HIGH)</p>
`, html.EscapeString(scanner), stats["TOTAL"], stats["CRITICAL"], stats["HIGH"]))
	}
	
	// Cluster scanners
	for _, scanner := range result.Scanners {
		if scanner == "Kubescape" || scanner == "Kube-bench" || scanner == "Popeye" {
			scannerIssues := 0
			scannerHigh := 0
			for _, vuln := range result.Vulnerabilities {
				if vuln.Package == "kubernetes-config" {
					for _, foundBy := range vuln.FoundBy {
						if foundBy == scanner {
							scannerIssues++
							if vuln.Severity == "HIGH" || vuln.Severity == "CRITICAL" {
								scannerHigh++
							}
							break
						}
					}
				}
			}
			sb.WriteString(fmt.Sprintf(`            <p><strong>%s:</strong> %d config issues (%d HIGH)</p>
`, html.EscapeString(scanner), scannerIssues, scannerHigh))
		}
	}
	
	sb.WriteString(`            <p style="margin-top: 20px; padding: 15px; background: white; border-radius: 5px;"><strong>ACTION PLAN:</strong></p>
            <ol style="margin-left: 20px;">
`)
	
	if len(imageScanners) >= 2 {
		sb.WriteString(fmt.Sprintf(`                <li>Fix %d high-confidence vulnerabilities (multiple scanners agree)</li>
`, multiScannerVulns))
		sb.WriteString(fmt.Sprintf(`                <li>Review %d single-scanner findings for false positives</li>
`, totalUnique))
		if configHigh > 0 {
			sb.WriteString(fmt.Sprintf(`                <li>Fix %d HIGH cluster config issues</li>
`, configHigh))
		}
	} else {
		sb.WriteString(`                <li>Fix all findings from available scanners</li>
`)
	}
	
	sb.WriteString(`            </ol>
        </div>
`)
	
	// Image Scanners Table
	actualImageScanners := []string{}
	for _, scanner := range imageScanners {
		if scanner != "Popeye" && scanner != "Kube-bench" {
			actualImageScanners = append(actualImageScanners, scanner)
		}
	}
	
	if len(actualImageScanners) >= 2 {
		sb.WriteString(`        <h2>Detailed Comparison (Image Scanners)</h2>
        <table>
            <tr>
                <th>Scanner</th>
                <th>CRITICAL</th>
                <th>HIGH</th>
                <th>MEDIUM</th>
                <th>LOW</th>
                <th>TOTAL</th>
                <th>Unique</th>
            </tr>
`)
		
		for _, scanner := range actualImageScanners {
			stats := scannerStats[scanner]
			unique := uniqueFindings[scanner]
			sb.WriteString(fmt.Sprintf(`            <tr>
                <td><strong>%s</strong></td>
                <td>%d</td>
                <td>%d</td>
                <td>%d</td>
                <td>%d</td>
                <td>%d</td>
                <td>%d</td>
            </tr>
`, html.EscapeString(scanner), stats["CRITICAL"], stats["HIGH"], stats["MEDIUM"], stats["LOW"], stats["TOTAL"], unique))
		}
		
		sb.WriteString(`        </table>
`)
		
		sb.WriteString(fmt.Sprintf(`        <p><strong>Agreement:</strong> %d vulns found by 2+ scanners (%d%%)</p>
`, multiScannerVulns, agreementPercent))
	}
	
	// Cluster Scanners Table
	clusterScanners := []string{}
	for _, scanner := range result.Scanners {
		if scanner == "Kubescape" || scanner == "Kube-bench" || scanner == "Popeye" {
			clusterScanners = append(clusterScanners, scanner)
		}
	}
	
	if len(clusterScanners) > 0 {
		sb.WriteString(`        <h2>Cluster Scanners</h2>
        <table>
            <tr>
                <th>Scanner</th>
                <th>HIGH</th>
                <th>MEDIUM</th>
                <th>LOW</th>
                <th>TOTAL</th>
            </tr>
`)
		
		for _, scanner := range clusterScanners {
			scannerHigh := 0
			scannerMedium := 0
			scannerLow := 0
			scannerTotal := 0
			
			for _, vuln := range result.Vulnerabilities {
				if vuln.Package == "kubernetes-config" {
					for _, foundBy := range vuln.FoundBy {
						if foundBy == scanner {
							scannerTotal++
							if vuln.Severity == "HIGH" || vuln.Severity == "CRITICAL" {
								scannerHigh++
							} else if vuln.Severity == "MEDIUM" {
								scannerMedium++
							} else if vuln.Severity == "LOW" {
								scannerLow++
							}
							break
						}
					}
				}
			}
			
			sb.WriteString(fmt.Sprintf(`            <tr>
                <td><strong>%s</strong></td>
                <td>%d</td>
                <td>%d</td>
                <td>%d</td>
                <td>%d</td>
            </tr>
`, html.EscapeString(scanner), scannerHigh, scannerMedium, scannerLow, scannerTotal))
		}
		
		sb.WriteString(`        </table>
`)
	}
}

func (h *HTMLReporter) Generate(result *aggregator.AggregatedResult, clusterName string) string {
	var sb strings.Builder

	// HTML header with inline CSS
	sb.WriteString(`<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Security Report: ` + html.EscapeString(clusterName) + `</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            background: #f5f5f5;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 40px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            color: #1a1a1a;
        }
        h2 {
            font-size: 1.8em;
            margin: 30px 0 15px;
            color: #2c3e50;
            border-bottom: 2px solid #3498db;
            padding-bottom: 10px;
        }
        .timestamp {
            color: #7f8c8d;
            font-size: 0.9em;
            margin-bottom: 30px;
        }
        .risk-box {
            background: linear-gradient(135deg, #56ab2f 0%, #a8e063 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin: 20px 0;
            font-size: 1.2em;
        }
        .risk-box.medium { background: linear-gradient(135deg, #f2994a 0%, #f2c94c 100%); }
        .risk-box.high { background: linear-gradient(135deg, #eb3349 0%, #f45c43 100%); }
        .actions {
            background: #ecf0f1;
            padding: 25px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .action-item {
            background: white;
            padding: 20px;
            margin: 15px 0;
            border-radius: 5px;
            border-left: 4px solid #3498db;
        }
        .action-header {
            font-size: 1.1em;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 10px;
        }
        .action-risk {
            color: #e74c3c;
            font-weight: bold;
            margin-bottom: 10px;
        }
        .action-packages {
            margin-left: 20px;
            margin-top: 10px;
        }
        .action-pkg {
            color: #555;
            margin: 5px 0;
        }
        hr {
            border: none;
            border-top: 1px solid #e0e0e0;
            margin: 30px 0;
        }
        .details {
            margin-top: 40px;
        }
        .vuln-card {
            background: #fff5f5;
            padding: 15px;
            margin: 10px 0;
            border-radius: 5px;
            border-left: 4px solid #e74c3c;
        }
        .vuln-header {
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 8px;
        }
        .vuln-info {
            font-size: 0.95em;
            color: #555;
            margin: 3px 0;
        }
        code {
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        .config-section {
            background: #fff8e1;
            padding: 20px;
            border-radius: 8px;
            margin: 15px 0;
        }
    </style>
</head>
<body>
    <div class="container">
`)

	// Title and timestamp
	sb.WriteString(fmt.Sprintf(`        <h1>Security Report: %s</h1>
        <div class="timestamp">Generated: %s</div>
`, html.EscapeString(clusterName), time.Now().Format("2006-01-02 15:04:05")))

	// Risk assessment
	h.writeRiskScore(&sb, result)
	
	// Top actions
	h.writeTopActions(&sb, result)
	
	// Details
	h.writeDetails(&sb, result)

	// Close HTML
	sb.WriteString(`    </div>
</body>
</html>`)

	return sb.String()
}

func (h *HTMLReporter) writeRiskScore(sb *strings.Builder, result *aggregator.AggregatedResult) {
	severityCounts := h.countBySeverity(result.Vulnerabilities)
	
	criticalCount := severityCounts["CRITICAL"]
	highCount := severityCounts["HIGH"]
	mediumCount := severityCounts["MEDIUM"]
	lowCount := severityCounts["LOW"]
	
	riskScore := criticalCount*10 + highCount*5
	
	riskLevel := "LOW"
	riskClass := ""
	recommendation := "Cluster is in good shape"
	
	if riskScore > 50 {
		riskLevel = "HIGH"
		riskClass = "high"
		recommendation = "Immediate action required"
	} else if riskScore > 20 {
		riskLevel = "MEDIUM"
		riskClass = "medium"
		recommendation = "Schedule fixes soon"
	}
	
	sb.WriteString(fmt.Sprintf(`        <div class="risk-box %s">
            <strong>RISK: %s</strong><br>
            %s | Score: %d | CRITICAL: %d | HIGH: %d | MEDIUM: %d | LOW: %d
        </div>
`, riskClass, riskLevel, recommendation, riskScore, criticalCount, highCount, mediumCount, lowCount))
}

func (h *HTMLReporter) writeTopActions(sb *strings.Builder, result *aggregator.AggregatedResult) {
	sb.WriteString(`        <h2>WHAT TO DO (Top 5)</h2>
        <div class="actions">
`)
	
	// Group by image
	imageGroups := h.groupByImage(result.Vulnerabilities)
	
	type imageScore struct {
		image     string
		criticals int
		highs     int
		score     int
		vulns     []aggregator.AggregatedVulnerability
	}
	
	var scores []imageScore
	for img, vulns := range imageGroups {
		criticals := 0
		highs := 0
		for _, v := range vulns {
			if v.Severity == "CRITICAL" {
				criticals++
			} else if v.Severity == "HIGH" {
				highs++
			}
		}
		score := criticals*10 + highs*5
		if score > 0 {
			scores = append(scores, imageScore{img, criticals, highs, score, vulns})
		}
	}
	
	sort.Slice(scores, func(i, j int) bool {
		return scores[i].score > scores[j].score
	})
	
	// Show top 5 images
	for i, is := range scores {
		if i >= 5 {
			break
		}
		
		shortImage := h.shortImageName(is.image)
		sb.WriteString(fmt.Sprintf(`            <div class="action-item">
                <div class="action-header">%d. UPDATE IMAGE: %s</div>
                <div class="action-risk">Risk: %d CRITICAL + %d HIGH</div>
                <div class="action-packages">
`, i+1, html.EscapeString(shortImage), is.criticals, is.highs))
		
		// Show top 3 packages to update in this image
		packageMap := make(map[string][]aggregator.AggregatedVulnerability)
		for _, v := range is.vulns {
			if v.Severity == "CRITICAL" || v.Severity == "HIGH" {
				packageMap[v.Package] = append(packageMap[v.Package], v)
			}
		}
		
		type pkgScore struct {
			pkg   string
			count int
			fix   string
		}
		var pkgs []pkgScore
		for pkg, vulns := range packageMap {
			fix := ""
			if len(vulns) > 0 && vulns[0].FixVersion != "" {
				fix = vulns[0].FixVersion
			}
			pkgs = append(pkgs, pkgScore{pkg, len(vulns), fix})
		}
		sort.Slice(pkgs, func(i, j int) bool {
			return pkgs[i].count > pkgs[j].count
		})
		
		for j, p := range pkgs {
			if j >= 3 {
				break
			}
			fixText := h.cleanFixVersion(p.fix)
			if fixText != "" {
				sb.WriteString(fmt.Sprintf(`                    <div class="action-pkg">• %s → %s (%d vulns)</div>
`, html.EscapeString(p.pkg), html.EscapeString(fixText), p.count))
			} else {
				sb.WriteString(fmt.Sprintf(`                    <div class="action-pkg">• %s (needs update, %d vulns)</div>
`, html.EscapeString(p.pkg), p.count))
			}
		}
		
		sb.WriteString(`                </div>
            </div>
`)
	}
	
	// Kubescape config issues
	configIssues := h.filterByPackage(result.Vulnerabilities, "kubernetes-config")
	if len(configIssues) > 0 {
		highConfig := 0
		for _, c := range configIssues {
			if c.Severity == "HIGH" || c.Severity == "CRITICAL" {
				highConfig++
			}
		}
		if highConfig > 0 {
			sb.WriteString(fmt.Sprintf(`            <div class="action-item">
                <div class="action-header">%d. FIX CLUSTER CONFIG</div>
                <div class="action-risk">%d HIGH/CRITICAL misconfigurations</div>
                <div class="action-packages">
                    <div class="action-pkg">See 'Configuration Issues' section below</div>
                </div>
            </div>
`, len(scores)+1, highConfig))
		}
	}
	
	sb.WriteString(`        </div>
`)
}

func (h *HTMLReporter) writeDetails(sb *strings.Builder, result *aggregator.AggregatedResult) {
	sb.WriteString(`        <div class="details">
`)
	
	// Critical details
	criticalVulns := aggregator.FilterBySeverity(result.Vulnerabilities, []string{"CRITICAL"})
	if len(criticalVulns) > 0 {
		sb.WriteString(fmt.Sprintf(`            <h2>CRITICAL Issues (%d)</h2>
`, len(criticalVulns)))
		
		sort.Slice(criticalVulns, func(i, j int) bool {
			return criticalVulns[i].CVSS > criticalVulns[j].CVSS
		})

		for _, vuln := range criticalVulns {
			imageList := "cluster"
			if len(vuln.Images) > 0 {
				imageList = h.shortImageName(vuln.Images[0])
				if len(vuln.Images) > 1 {
					imageList += fmt.Sprintf(" (+%d more)", len(vuln.Images)-1)
				}
			}
			
			foundByText := strings.Join(vuln.FoundBy, ", ")
			confidence := ""
			if len(vuln.FoundBy) > 1 {
				confidence = " 🔒 HIGH CONFIDENCE"
			}
			sb.WriteString(fmt.Sprintf(`            <div class="vuln-card">
                <div class="vuln-header">%s | %s | CVSS %.1f</div>
                <div class="vuln-info">Found by: <strong>%s</strong>%s</div>
                <div class="vuln-info">Package: <code>%s</code> (%s)</div>
`, html.EscapeString(vuln.ID), html.EscapeString(imageList), vuln.CVSS,
   html.EscapeString(foundByText), confidence,
   html.EscapeString(vuln.Package), html.EscapeString(vuln.Version)))
			
			if vuln.FixVersion != "" {
				sb.WriteString(fmt.Sprintf(`                <div class="vuln-info">Fix: Update to <code>%s</code></div>
`, html.EscapeString(vuln.FixVersion)))
			} else {
				sb.WriteString(`                <div class="vuln-info">Fix: No fix available yet</div>
`)
			}
			
			sb.WriteString(`            </div>
`)
		}
	}
	
	// Config issues
	configIssues := h.filterByPackage(result.Vulnerabilities, "kubernetes-config")
	if len(configIssues) > 0 {
		sb.WriteString(`            <hr>
            <h2>Configuration Issues</h2>
`)
		
		configSeverity := make(map[string][]aggregator.AggregatedVulnerability)
		for _, vuln := range configIssues {
			configSeverity[vuln.Severity] = append(configSeverity[vuln.Severity], vuln)
		}
		
		for _, sev := range []string{"CRITICAL", "HIGH", "MEDIUM", "LOW"} {
			if vulns, ok := configSeverity[sev]; ok && len(vulns) > 0 {
				sort.Slice(vulns, func(i, j int) bool {
					return vulns[i].ID < vulns[j].ID
				})
				
				sb.WriteString(fmt.Sprintf(`            <div class="config-section">
                <strong>%s (%d)</strong><br><br>
`, sev, len(vulns)))
				
				for _, vuln := range vulns {
					foundByText := strings.Join(vuln.FoundBy, ", ")
					sb.WriteString(fmt.Sprintf(`                • %s: %s <em>[%s]</em><br>
`, html.EscapeString(vuln.ID), html.EscapeString(vuln.Title), html.EscapeString(foundByText)))
				}
				
				sb.WriteString(`            </div>
`)
			}
		}
	}
	
	// Footer
	multiScannerVulns := 0
	imageVulns := 0
	for _, vuln := range result.Vulnerabilities {
		if vuln.Package != "kubernetes-config" {
			imageVulns++
			if len(vuln.FoundBy) > 1 {
				multiScannerVulns++
			}
		}
	}
	
	sb.WriteString(fmt.Sprintf(`            <hr>
            <p style="color: #7f8c8d; text-align: center;">
                Scanned: %d images | Scanners: %s | High confidence: %d/%d vulns (found by 2+ scanners)
            </p>
`, result.UniqueImages, html.EscapeString(strings.Join(result.Scanners, ", ")), multiScannerVulns, imageVulns))
	
	sb.WriteString(`        </div>
`)
}

func (h *HTMLReporter) shortImageName(fullImage string) string {
	if fullImage == "" {
		return "unknown"
	}
	
	parts := strings.Split(fullImage, "/")
	if len(parts) > 0 {
		return parts[len(parts)-1]
	}
	return fullImage
}

func (h *HTMLReporter) countBySeverity(vulns []aggregator.AggregatedVulnerability) map[string]int {
	counts := make(map[string]int)
	for _, vuln := range vulns {
		counts[vuln.Severity]++
	}
	return counts
}

func (h *HTMLReporter) filterByPackage(vulns []aggregator.AggregatedVulnerability, pkg string) []aggregator.AggregatedVulnerability {
	var filtered []aggregator.AggregatedVulnerability
	for _, vuln := range vulns {
		if vuln.Package == pkg {
			filtered = append(filtered, vuln)
		}
	}
	return filtered
}

func (h *HTMLReporter) groupByImage(vulns []aggregator.AggregatedVulnerability) map[string][]aggregator.AggregatedVulnerability {
	groups := make(map[string][]aggregator.AggregatedVulnerability)
	for _, vuln := range vulns {
		if vuln.Package == "kubernetes-config" {
			continue
		}
		
		if len(vuln.Images) > 0 {
			for _, img := range vuln.Images {
				groups[img] = append(groups[img], vuln)
			}
		}
	}
	return groups
}

func (h *HTMLReporter) cleanFixVersion(version string) string {
	if version == "" {
		return ""
	}
	
	// If it's a commit hash (0.0.0-20201216223049-8b5274cf687f)
	if strings.HasPrefix(version, "0.0.0-") && len(version) > 20 {
		return "latest"
	}
	
	// If it looks like a commit hash in general (contains 40+ hex chars)
	if len(version) >= 40 {
		return "latest"
	}
	
	return version
}
