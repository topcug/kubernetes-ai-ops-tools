package proc

import (
	"bufio"
	"os"
	"path/filepath"
	"strings"

	"github.com/topcug/sockscope/internal/model"
)

// ReadUnixSockets reads /proc/net/unix and returns any entry whose
// inode appears in the given set. The path column is optional in the
// kernel output; abstract and unnamed sockets leave it empty.
//
// /proc/net/unix columns:
//
//	Num RefCount Protocol Flags Type St Inode [Path]
func ReadUnixSockets(inodes map[string]struct{}) ([]model.SocketSummary, error) {
	f, err := os.Open(filepath.Join(ProcRoot, "net", "unix"))
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	defer f.Close()

	var out []model.SocketSummary
	scanner := bufio.NewScanner(f)
	header := true
	for scanner.Scan() {
		if header {
			header = false
			continue
		}
		fields := strings.Fields(scanner.Text())
		if len(fields) < 7 {
			continue
		}
		inode := fields[6]
		if _, ok := inodes[inode]; !ok {
			continue
		}
		path := ""
		if len(fields) >= 8 {
			path = fields[7]
		}
		out = append(out, model.SocketSummary{
			Kind:  model.KindUnix,
			Inode: inode,
			Path:  path,
		})
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return out, nil
}
