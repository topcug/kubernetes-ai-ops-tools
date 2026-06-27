package reporter

import (
	"fmt"
	"sort"
	"strings"
	"time"

	"github.com/secclear/secclear-cli/internal/aggregator"
)

type MarkdownReporter struct{}

func NewMarkdownReporter() *MarkdownReporter {
	return &MarkdownReporter{}
}

func (m *MarkdownReporter) Generate(result *aggregator.AggregatedResult, clusterName string) string {
	var sb strings.Builder

	sb.WriteString(fmt.Sprintf("# Security Report: %s\n\n", clusterName))
	sb.WriteString(fmt.Sprintf("Generated: %s\n\n", time.Now().Format("2006-01-02 15:04:05")))

	m.writeRiskScore(&sb, result)
	m.writeTopActions(&sb, result)
	m.writeDetailedSections(&sb, result)

	return sb.String()
}

func (m *MarkdownReporter) GenerateComparison(result *aggregator.AggregatedResult, clusterName string) string {
	var sb strings.Builder

	sb.WriteString(fmt.Sprintf("# Scanner Comparison Report: %s\n\n", clusterName))
	sb.WriteString(fmt.Sprintf("Generated: %s\n\n", time.Now().Format("2006-01-02 15:04:05")))

	m.writeScannerComparison(&sb, result)

	return sb.String()
}

func (m *MarkdownReporter) writeScannerComparison(sb *strings.Builder, result *aggregator.AggregatedResult) {
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
	sb.WriteString("## WHAT TO DO\n\n")
	
	sb.WriteString(fmt.Sprintf("1. **Keep using all %d scanners** - Each catches different problems\n", len(result.Scanners)))
	for _, scanner := range imageScanners {
		stats := scannerStats[scanner]
		if scanner == "Popeye" || scanner == "Kube-bench" {
			continue
		}
		sb.WriteString(fmt.Sprintf("   - %s: Finds CVEs in container images (%d total, %d CRITICAL)\n", 
			scanner, stats["TOTAL"], stats["CRITICAL"]))
	}
	
	// Cluster scanners
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
			if scannerIssues > 0 || scanner == "Kubescape" || scanner == "Popeye" || scanner == "Kube-bench" {
				sb.WriteString(fmt.Sprintf("   - %s: Finds cluster config problems (%d issues, %d HIGH)\n", scanner, scannerIssues, scannerHigh))
			}
		}
	}
	sb.WriteString("\n")
	
	if len(imageScanners) >= 2 {
		sb.WriteString(fmt.Sprintf("2. **Fix high-confidence issues first** (%d vulns found by multiple scanners)\n\n", 
			multiScannerVulns))
		
		totalUnique := 0
		for _, count := range uniqueFindings {
			totalUnique += count
		}
		
		sb.WriteString(fmt.Sprintf("3. **Review single-scanner findings** (%d total - may include false positives)\n", totalUnique))
		for _, scanner := range imageScanners {
			if count, ok := uniqueFindings[scanner]; ok {
				sb.WriteString(fmt.Sprintf("   - %s only: %d vulns\n", scanner, count))
			}
		}
	}
	
	sb.WriteString("\n---\n\n")
	
	// Scanner Performance
	sb.WriteString("## Scanner Performance\n\n")
	
	// Image scanners
	for _, scanner := range imageScanners {
		if scanner == "Popeye" || scanner == "Kube-bench" {
			continue
		}
		stats := scannerStats[scanner]
		sb.WriteString(fmt.Sprintf("**%s:** %d vulns (%d CRITICAL, %d HIGH)\n", 
			scanner, stats["TOTAL"], stats["CRITICAL"], stats["HIGH"]))
	}
	
	sb.WriteString("\n")
	
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
			sb.WriteString(fmt.Sprintf("**%s:** %d config issues (%d HIGH)\n", scanner, scannerIssues, scannerHigh))
		}
	}
	
	// Calculate total unique for action plan
	totalUnique := 0
	for _, count := range uniqueFindings {
		totalUnique += count
	}
	
	sb.WriteString("\n**ACTION PLAN:**\n")
	if len(imageScanners) >= 2 {
		sb.WriteString(fmt.Sprintf("1. Fix %d high-confidence vulnerabilities (multiple scanners agree)\n", multiScannerVulns))
		sb.WriteString(fmt.Sprintf("2. Review %d single-scanner findings for false positives\n", totalUnique))
		if configHigh > 0 {
			sb.WriteString(fmt.Sprintf("3. Fix %d HIGH cluster config issues\n", configHigh))
		}
	} else {
		sb.WriteString("Fix all findings from available scanners\n")
	}
	sb.WriteString("\n")
	
	sb.WriteString("---\n\n")
	
	// Image Scanners Table
	actualImageScanners := []string{}
	for _, scanner := range imageScanners {
		if scanner != "Popeye" && scanner != "Kube-bench" {
			actualImageScanners = append(actualImageScanners, scanner)
		}
	}
	
	if len(actualImageScanners) >= 2 {
		sb.WriteString("## Detailed Comparison (Image Scanners)\n\n")
		
		sb.WriteString("| Scanner | CRITICAL | HIGH | MEDIUM | LOW | TOTAL | Unique |\n")
		sb.WriteString("|---------|----------|------|--------|-----|-------|--------|\n")
		
		for _, scanner := range actualImageScanners {
			stats := scannerStats[scanner]
			unique := uniqueFindings[scanner]
			sb.WriteString(fmt.Sprintf("| %s | %d | %d | %d | %d | %d | %d |\n",
				scanner,
				stats["CRITICAL"],
				stats["HIGH"],
				stats["MEDIUM"],
				stats["LOW"],
				stats["TOTAL"],
				unique))
		}
		
		sb.WriteString(fmt.Sprintf("\n**Agreement:** %d vulns found by 2+ scanners (%d%%)\n\n", 
			multiScannerVulns, agreementPercent))
	}
	
	// Cluster Scanners Table
	clusterScanners := []string{}
	for _, scanner := range result.Scanners {
		if scanner == "Kubescape" || scanner == "Kube-bench" || scanner == "Popeye" {
			clusterScanners = append(clusterScanners, scanner)
		}
	}
	
	if len(clusterScanners) > 0 {
		sb.WriteString("## Cluster Scanners\n\n")
		
		sb.WriteString("| Scanner | HIGH | MEDIUM | LOW | TOTAL |\n")
		sb.WriteString("|---------|------|--------|-----|-------|\n")
		
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
			
			sb.WriteString(fmt.Sprintf("| %s | %d | %d | %d | %d |\n",
				scanner,
				scannerHigh,
				scannerMedium,
				scannerLow,
				scannerTotal))
		}
		sb.WriteString("\n")
	}
}

func (m *MarkdownReporter) writeRiskScore(sb *strings.Builder, result *aggregator.AggregatedResult) {
	severityCounts := m.countBySeverity(result.Vulnerabilities)
	
	criticalCount := severityCounts["CRITICAL"]
	highCount := severityCounts["HIGH"]
	
	riskScore := criticalCount*10 + highCount*5
	
	riskLevel := "LOW"
	recommendation := "Cluster is in good shape"
	
	if riskScore > 50 {
		riskLevel = "HIGH"
		recommendation = "Immediate action required"
	} else if riskScore > 20 {
		riskLevel = "MEDIUM"
		recommendation = "Schedule fixes soon"
	}
	
	sb.WriteString(fmt.Sprintf("## RISK: %s\n\n", riskLevel))
	sb.WriteString(fmt.Sprintf("%s | Score: %d | CRITICAL: %d | HIGH: %d | MEDIUM: %d | LOW: %d\n\n",
		recommendation,
		riskScore,
		severityCounts["CRITICAL"],
		severityCounts["HIGH"],
		severityCounts["MEDIUM"],
		severityCounts["LOW"]))
	sb.WriteString("---\n\n")
}

func (m *MarkdownReporter) writeTopActions(sb *strings.Builder, result *aggregator.AggregatedResult) {
	sb.WriteString("## WHAT TO DO (Top 5)\n\n")
	
	// Group by image
	imageGroups := m.groupByImage(result.Vulnerabilities)
	
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
		
		shortImage := m.shortImageName(is.image)
		sb.WriteString(fmt.Sprintf("%d. UPDATE IMAGE: %s\n", i+1, shortImage))
		sb.WriteString(fmt.Sprintf("   Risk: %d CRITICAL + %d HIGH\n", is.criticals, is.highs))
		
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
			fixText := m.cleanFixVersion(p.fix)
			if fixText != "" {
				sb.WriteString(fmt.Sprintf("   - %s -> %s (%d vulns)\n", p.pkg, fixText, p.count))
			} else {
				sb.WriteString(fmt.Sprintf("   - %s (needs update, %d vulns)\n", p.pkg, p.count))
			}
		}
		sb.WriteString("\n")
	}
	
	// Kubescape config issues
	configIssues := m.filterByPackage(result.Vulnerabilities, "kubernetes-config")
	if len(configIssues) > 0 {
		highConfig := 0
		for _, c := range configIssues {
			if c.Severity == "HIGH" || c.Severity == "CRITICAL" {
				highConfig++
			}
		}
		if highConfig > 0 {
			sb.WriteString(fmt.Sprintf("%d. FIX CLUSTER CONFIG\n", len(scores)+1))
			sb.WriteString(fmt.Sprintf("   %d HIGH/CRITICAL misconfigurations\n", highConfig))
			sb.WriteString("   See 'Configuration Issues' section below\n\n")
		}
	}
	
	sb.WriteString("---\n\n")
}

func (m *MarkdownReporter) writeDetailedSections(sb *strings.Builder, result *aggregator.AggregatedResult) {
	// Critical details (collapsible)
	criticalVulns := aggregator.FilterBySeverity(result.Vulnerabilities, []string{"CRITICAL"})
	if len(criticalVulns) > 0 {
		sb.WriteString(fmt.Sprintf("## CRITICAL Issues (%d)\n\n", len(criticalVulns)))
		
		sort.Slice(criticalVulns, func(i, j int) bool {
			return criticalVulns[i].CVSS > criticalVulns[j].CVSS
		})

		for _, vuln := range criticalVulns {
			imageList := "cluster"
			if len(vuln.Images) > 0 {
				imageList = m.shortImageName(vuln.Images[0])
				if len(vuln.Images) > 1 {
					imageList += fmt.Sprintf(" (+%d more)", len(vuln.Images)-1)
				}
			}
			
			foundByText := strings.Join(vuln.FoundBy, ", ")
			confidence := ""
			if len(vuln.FoundBy) > 1 {
				confidence = " 🔒"
			}
			sb.WriteString(fmt.Sprintf("**%s** | %s | CVSS %.1f | Found by: %s%s\n", vuln.ID, imageList, vuln.CVSS, foundByText, confidence))
			sb.WriteString(fmt.Sprintf("- Package: %s (%s)\n", vuln.Package, vuln.Version))
			if vuln.FixVersion != "" {
				sb.WriteString(fmt.Sprintf("- Fix: Update to %s\n", vuln.FixVersion))
			} else {
				sb.WriteString("- Fix: No fix available yet\n")
			}
			if len(vuln.References) > 0 {
				sb.WriteString(fmt.Sprintf("- Info: %s\n", vuln.References[0]))
			}
			sb.WriteString("\n")
		}
		sb.WriteString("---\n\n")
	}
	
	// High severity (summary only, first 10)
	highVulns := aggregator.FilterBySeverity(result.Vulnerabilities, []string{"HIGH"})
	if len(highVulns) > 0 {
		sb.WriteString(fmt.Sprintf("## HIGH Issues (%d)\n\n", len(highVulns)))
		
		sort.Slice(highVulns, func(i, j int) bool {
			return highVulns[i].CVSS > highVulns[j].CVSS
		})

		displayCount := 10
		if len(highVulns) < displayCount {
			displayCount = len(highVulns)
		}
		
		for i := 0; i < displayCount; i++ {
			vuln := highVulns[i]
			imageList := "cluster"
			if len(vuln.Images) > 0 {
				imageList = m.shortImageName(vuln.Images[0])
			}
			
			fix := vuln.FixVersion
			if fix == "" {
				fix = "no fix"
			}
			foundByText := strings.Join(vuln.FoundBy, ", ")
			confidence := ""
			if len(vuln.FoundBy) > 1 {
				confidence = " 🔒"
			}
			sb.WriteString(fmt.Sprintf("- **%s** | %s | %s -> %s | Found by: %s%s\n", vuln.ID, imageList, vuln.Package, fix, foundByText, confidence))
		}
		
		if len(highVulns) > displayCount {
			sb.WriteString(fmt.Sprintf("\n...and %d more\n", len(highVulns)-displayCount))
		}
		sb.WriteString("\n---\n\n")
	}
	
	// Config issues
	configIssues := m.filterByPackage(result.Vulnerabilities, "kubernetes-config")
	if len(configIssues) > 0 {
		sb.WriteString("## Configuration Issues\n\n")
		
		configSeverity := make(map[string][]aggregator.AggregatedVulnerability)
		for _, vuln := range configIssues {
			configSeverity[vuln.Severity] = append(configSeverity[vuln.Severity], vuln)
		}
		
		for _, sev := range []string{"CRITICAL", "HIGH", "MEDIUM", "LOW"} {
			if vulns, ok := configSeverity[sev]; ok && len(vulns) > 0 {
				sort.Slice(vulns, func(i, j int) bool {
					return vulns[i].ID < vulns[j].ID
				})
				
				sb.WriteString(fmt.Sprintf("**%s** (%d)\n", sev, len(vulns)))
				for _, vuln := range vulns {
					foundByText := strings.Join(vuln.FoundBy, ", ")
					sb.WriteString(fmt.Sprintf("- %s: %s [%s]\n", vuln.ID, vuln.Title, foundByText))
				}
				sb.WriteString("\n")
			}
		}
		sb.WriteString("---\n\n")
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
	
	sb.WriteString(fmt.Sprintf("Scanned: %d images | Scanners: %s | High confidence: %d/%d vulns (found by 2+ scanners)\n",
		result.UniqueImages,
		strings.Join(result.Scanners, ", "),
		multiScannerVulns,
		imageVulns))
}

func (m *MarkdownReporter) shortImageName(fullImage string) string {
	if fullImage == "" {
		return "unknown"
	}
	
	// registry.k8s.io/coredns/coredns:v1.12.1 -> coredns:v1.12.1
	// gcr.io/k8s-minikube/storage-provisioner:v5 -> storage-provisioner:v5
	
	parts := strings.Split(fullImage, "/")
	if len(parts) > 0 {
		return parts[len(parts)-1]
	}
	return fullImage
}

func (m *MarkdownReporter) countBySeverity(vulns []aggregator.AggregatedVulnerability) map[string]int {
	counts := make(map[string]int)
	for _, vuln := range vulns {
		counts[vuln.Severity]++
	}
	return counts
}

func (m *MarkdownReporter) filterByPackage(vulns []aggregator.AggregatedVulnerability, pkg string) []aggregator.AggregatedVulnerability {
	var filtered []aggregator.AggregatedVulnerability
	for _, vuln := range vulns {
		if vuln.Package == pkg {
			filtered = append(filtered, vuln)
		}
	}
	return filtered
}

func (m *MarkdownReporter) groupByImage(vulns []aggregator.AggregatedVulnerability) map[string][]aggregator.AggregatedVulnerability {
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

func (m *MarkdownReporter) cleanFixVersion(version string) string {
	if version == "" {
		return ""
	}
	
	// If it's a commit hash (0.0.0-20201216223049-8b5274cf687f)
	if strings.HasPrefix(version, "0.0.0-") && len(version) > 20 {
		return "latest"
	}
	
	// If it looks like a commit hash in general (contains 40+ hex chars)
	if len(version) >= 40 && strings.Contains(version, "abcdef0123456789") {
		return "latest"
	}
	
	return version
}
