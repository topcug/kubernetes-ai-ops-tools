package proc

import (
	"bufio"
	"encoding/hex"
	"fmt"
	"net"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/topcug/sockscope/internal/model"
)

// TCP state codes used in /proc/net/tcp. The kernel encodes these
// as two-digit hex values in the "st" column.
var tcpStates = map[string]string{
	"01": "ESTABLISHED",
	"02": "SYN_SENT",
	"03": "SYN_RECV",
	"04": "FIN_WAIT1",
	"05": "FIN_WAIT2",
	"06": "TIME_WAIT",
	"07": "CLOSE",
	"08": "CLOSE_WAIT",
	"09": "LAST_ACK",
	"0A": "LISTEN",
	"0B": "CLOSING",
	"0C": "NEW_SYN_RECV",
}

// ReadTCPSockets reads /proc/net/tcp and /proc/net/tcp6, returning
// any socket whose inode appears in the given set. The ipv6 flag on
// each row is handled transparently by parseHexAddr.
func ReadTCPSockets(inodes map[string]struct{}) ([]model.SocketSummary, error) {
	var out []model.SocketSummary
	for _, name := range []string{"tcp", "tcp6"} {
		rows, err := parseNetFile(filepath.Join(ProcRoot, "net", name), name == "tcp6")
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
			r.Kind = model.KindTCP
			out = append(out, r)
		}
	}
	return out, nil
}

// netRow is a narrow intermediate type shared by tcp.go and udp.go.
type netRow = model.SocketSummary

func parseNetFile(path string, ipv6 bool) ([]netRow, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	var rows []netRow
	scanner := bufio.NewScanner(f)
	// /proc/net/tcp lines can get long on busy hosts; bump the buffer.
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)
	header := true
	for scanner.Scan() {
		if header {
			header = false
			continue
		}
		fields := strings.Fields(scanner.Text())
		// Columns: sl local_address rem_address st tx_queue:rx_queue tr:tm_when retrnsmt uid timeout inode ...
		if len(fields) < 10 {
			continue
		}
		local, err := parseHexAddr(fields[1], ipv6)
		if err != nil {
			continue
		}
		remote, err := parseHexAddr(fields[2], ipv6)
		if err != nil {
			continue
		}
		state := tcpStates[strings.ToUpper(fields[3])]
		if state == "" {
			state = fields[3]
		}
		rows = append(rows, netRow{
			LocalAddress:  local,
			RemoteAddress: remote,
			State:         state,
			Inode:         fields[9],
		})
	}
	if err := scanner.Err(); err != nil {
		return nil, err
	}
	return rows, nil
}

// parseHexAddr decodes a hex address:port pair as used in
// /proc/net/tcp{,6} and /proc/net/udp{,6}. IPv4 addresses are stored
// in little-endian order per 32-bit word; IPv6 is stored as four
// little-endian 32-bit words. The port is always big-endian hex.
func parseHexAddr(s string, ipv6 bool) (string, error) {
	parts := strings.Split(s, ":")
	if len(parts) != 2 {
		return "", fmt.Errorf("bad addr %q", s)
	}
	hexAddr, hexPort := parts[0], parts[1]

	port64, err := strconv.ParseUint(hexPort, 16, 32)
	if err != nil {
		return "", err
	}
	port := uint16(port64)

	raw, err := hex.DecodeString(hexAddr)
	if err != nil {
		return "", err
	}

	var ip net.IP
	if !ipv6 {
		if len(raw) != 4 {
			return "", fmt.Errorf("ipv4 addr wrong size: %d", len(raw))
		}
		// Kernel writes each 32-bit word in host (little-endian)
		// order. For IPv4 there's exactly one word.
		ip = net.IPv4(raw[3], raw[2], raw[1], raw[0])
	} else {
		if len(raw) != 16 {
			return "", fmt.Errorf("ipv6 addr wrong size: %d", len(raw))
		}
		ip = make(net.IP, 16)
		// Reverse each 4-byte word.
		for w := 0; w < 4; w++ {
			for b := 0; b < 4; b++ {
				ip[w*4+b] = raw[w*4+(3-b)]
			}
		}
	}

	return fmt.Sprintf("%s:%d", ip.String(), port), nil
}
