package version

import "runtime/debug"

// Version is overridden at build time via -ldflags by GoReleaser.
// When installed via `go install`, it falls back to the module version
// embedded in the binary by the Go toolchain.
var (
	Version = "dev"
	Commit  = "none"
	Date    = "unknown"
)

func init() {
	if Version != "dev" {
		return
	}
	info, ok := debug.ReadBuildInfo()
	if !ok {
		return
	}
	if info.Main.Version != "" && info.Main.Version != "(devel)" {
		Version = info.Main.Version
	}
}
