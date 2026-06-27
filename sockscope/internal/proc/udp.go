package proc

import (
	"os"
	"path/filepath"

	"github.com/topcug/sockscope/internal/model"
)

// ReadUDPSockets reads /proc/net/udp and /proc/net/udp6 and filters
// by the given inode set. UDP does not carry a connection state in
// the same way TCP does, so we blank out the State field.
func ReadUDPSockets(inodes map[string]struct{}) ([]model.SocketSummary, error) {
	var out []model.SocketSummary
	for _, name := range []string{"udp", "udp6"} {
		rows, err := parseNetFile(filepath.Join(ProcRoot, "net", name), name == "udp6")
		if err != nil {
			if os.IsNotExist(err) {
				continue
			}
			return nil, err
		}
		for _, r := range rows {
			if _, ok := inodes[r.Inode]; !ok {
				continue
			}
			r.Kind = model.KindUDP
			r.State = ""
			out = append(out, r)
		}
	}
	return out, nil
}
