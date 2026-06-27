package aggregator

import (
	"sort"
	"github.com/secclear/secclear-cli/internal/scanner"
)

type AggregatedVulnerability struct {
	scanner.Vulnerability
	FoundBy []string
	Count   int
	Images  []string  // Which images have this vuln
}

type AggregatedResult struct {
	Scanners        []string
	TotalScans      int
	UniqueImages    int
	Vulnerabilities []AggregatedVulnerability
}

func Aggregate(results []*scanner.ScanResult) *AggregatedResult {
	agg := &AggregatedResult{
		TotalScans: len(results),
	}

	vulnMap := make(map[string]*AggregatedVulnerability)
	scannerSet := make(map[string]bool)
	imageSet := make(map[string]bool)

	for _, result := range results {
		scannerSet[result.Scanner] = true
		imageSet[result.Target] = true

		for _, vuln := range result.Vulnerabilities {
			key := vuln.ID

			if existing, found := vulnMap[key]; found {
				existing.Count++
				foundByMap := make(map[string]bool)
				for _, scanner := range existing.FoundBy {
					foundByMap[scanner] = true
				}
				if !foundByMap[result.Scanner] {
					existing.FoundBy = append(existing.FoundBy, result.Scanner)
				}
				// Keep track of all images with this vuln
				if vuln.Image != "" && vuln.Image != "cluster" {
					imageAlreadyTracked := false
					for _, img := range existing.Images {
						if img == vuln.Image {
							imageAlreadyTracked = true
							break
						}
					}
					if !imageAlreadyTracked {
						existing.Images = append(existing.Images, vuln.Image)
					}
				}
			} else {
				images := []string{}
				if vuln.Image != "" && vuln.Image != "cluster" {
					images = append(images, vuln.Image)
				}
				vulnMap[key] = &AggregatedVulnerability{
					Vulnerability: vuln,
					FoundBy:      []string{result.Scanner},
					Count:        1,
					Images:       images,
				}
			}
		}
	}

	// Sort scanners alphabetically for consistent output
	for scanner := range scannerSet {
		agg.Scanners = append(agg.Scanners, scanner)
	}
	sort.Strings(agg.Scanners)
	
	agg.UniqueImages = len(imageSet)

	// Convert map to slice
	for _, vuln := range vulnMap {
		// Sort FoundBy list for consistency
		sort.Strings(vuln.FoundBy)
		agg.Vulnerabilities = append(agg.Vulnerabilities, *vuln)
	}

	// Sort vulnerabilities by ID for deterministic output
	sort.Slice(agg.Vulnerabilities, func(i, j int) bool {
		return agg.Vulnerabilities[i].ID < agg.Vulnerabilities[j].ID
	})

	return agg
}

func FilterBySeverity(vulns []AggregatedVulnerability, severities []string) []AggregatedVulnerability {
	severityMap := make(map[string]bool)
	for _, s := range severities {
		severityMap[s] = true
	}

	var filtered []AggregatedVulnerability
	for _, vuln := range vulns {
		if severityMap[vuln.Severity] {
			filtered = append(filtered, vuln)
		}
	}
	return filtered
}
