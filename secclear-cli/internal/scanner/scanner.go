package scanner

type Vulnerability struct {
	ID          string
	Severity    string
	Title       string
	Description string
	Package     string
	Version     string
	FixVersion  string
	CVSS        float64
	References  []string
	FoundBy     []string
	Image       string   // Which image has this vuln
}

type ScanResult struct {
	Scanner        string
	Target         string   // Image name
	Vulnerabilities []Vulnerability
}

type Scanner interface {
	Name() string
	Scan(target string) (*ScanResult, error)
	IsInstalled() bool
}
