package model

// Socket kinds supported in v1. These are strings rather than an
// enum so JSON output stays human readable and stable across versions.
const (
	KindTCP  = "tcp"
	KindUDP  = "udp"
	KindUnix = "unix"
)

// Socket states we surface. We do not invent new names; we pass
// through the kernel's own state labels for TCP (ESTABLISHED, LISTEN,
// TIME_WAIT, etc.) and leave UDP and UNIX sockets stateless in output.
type SocketSummary struct {
	Kind          string `json:"kind"`
	LocalAddress  string `json:"local_address,omitempty"`
	RemoteAddress string `json:"remote_address,omitempty"`
	State         string `json:"state,omitempty"`
	Inode         string `json:"inode,omitempty"`
	Path          string `json:"path,omitempty"`
}

// IsExternal returns true when the remote address is set and is not
// a loopback address. It is a small helper used by the triage layer.
func (s SocketSummary) IsExternal() bool {
	if s.Kind != KindTCP && s.Kind != KindUDP {
		return false
	}
	if s.RemoteAddress == "" {
		return false
	}
	return !isLoopback(s.RemoteAddress) && !isZeroAddr(s.RemoteAddress)
}

// IsLoopback returns true when both local and remote are on 127.0.0.0/8
// or ::1. Listening sockets without a remote are not counted here.
func (s SocketSummary) IsLoopback() bool {
	if s.Kind != KindTCP && s.Kind != KindUDP {
		return false
	}
	if s.RemoteAddress == "" {
		return false
	}
	return isLoopback(s.LocalAddress) && isLoopback(s.RemoteAddress)
}

// IsListening returns true for TCP LISTEN sockets. UDP does not have
// a listen state in the same sense, so we return false there.
func (s SocketSummary) IsListening() bool {
	return s.Kind == KindTCP && s.State == "LISTEN"
}

// IsAbstract returns true for UNIX sockets in the abstract namespace
// (path starts with '@') or unnamed sockets (empty path).
func (s SocketSummary) IsAbstract() bool {
	if s.Kind != KindUnix {
		return false
	}
	return s.Path == "" || (len(s.Path) > 0 && s.Path[0] == '@')
}

func isLoopback(addr string) bool {
	if addr == "" {
		return false
	}
	// Strip :port if present. IPv6 addresses in /proc output are
	// already bracket-free in our parsed form, so we split on the
	// last colon only.
	host := addr
	if i := lastColon(addr); i >= 0 {
		host = addr[:i]
	}
	if host == "127.0.0.1" || host == "::1" {
		return true
	}
	// 127.0.0.0/8 covers the full loopback range.
	if len(host) >= 4 && host[:4] == "127." {
		return true
	}
	return false
}

func isZeroAddr(addr string) bool {
	host := addr
	if i := lastColon(addr); i >= 0 {
		host = addr[:i]
	}
	return host == "0.0.0.0" || host == "::" || host == ""
}

func lastColon(s string) int {
	for i := len(s) - 1; i >= 0; i-- {
		if s[i] == ':' {
			return i
		}
	}
	return -1
}
