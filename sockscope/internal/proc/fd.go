package proc

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

// SocketInodes returns the set of socket inode numbers owned by a
// process. It walks /proc/<pid>/fd and collects the inode from any
// symlink target of the form "socket:[12345]".
//
// We return a map so the caller can do O(1) membership checks when
// cross-referencing /proc/net/{tcp,udp,unix}.
func SocketInodes(pid int) (map[string]struct{}, error) {
	fdDir := filepath.Join(ProcRoot, strconv.Itoa(pid), "fd")
	entries, err := os.ReadDir(fdDir)
	if err != nil {
		if errors.Is(err, os.ErrPermission) {
			return nil, fmt.Errorf("permission denied reading %s — try running with sudo", fdDir)
		}
		return nil, err
	}
	inodes := make(map[string]struct{}, len(entries))
	for _, e := range entries {
		target, err := os.Readlink(filepath.Join(fdDir, e.Name()))
		if err != nil {
			continue
		}
		if inode, ok := parseSocketLink(target); ok {
			inodes[inode] = struct{}{}
		}
	}
	return inodes, nil
}

// parseSocketLink extracts the inode out of a "socket:[N]" symlink
// target. Any other link type (regular files, pipes, anon_inode)
// returns ok=false.
func parseSocketLink(target string) (string, bool) {
	const prefix = "socket:["
	if !strings.HasPrefix(target, prefix) || !strings.HasSuffix(target, "]") {
		return "", false
	}
	inner := target[len(prefix) : len(target)-1]
	if inner == "" {
		return "", false
	}
	return inner, true
}
