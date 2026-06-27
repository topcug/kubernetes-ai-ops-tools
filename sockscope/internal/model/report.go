package model

import "time"

// SocketMix holds counts derived from the socket list. It is computed
// once at report build time and shared across all renderers.
type SocketMix struct {
	TCP      int `json:"tcp"`
	UDP      int `json:"udp"`
	Unix     int `json:"unix"`
	External int `json:"external"`
	Loopback int `json:"loopback"`
	Abstract int `json:"abstract_unix"`
	Named    int `json:"named_unix"`
}

// ComputeMix derives socket counts from a slice of SocketSummary values.
func ComputeMix(sockets []SocketSummary) SocketMix {
	var m SocketMix
	for _, s := range sockets {
		switch s.Kind {
		case KindTCP:
			m.TCP++
		case KindUDP:
			m.UDP++
		case KindUnix:
			m.Unix++
			if s.IsAbstract() {
				m.Abstract++
			} else {
				m.Named++
			}
		}
		if s.IsExternal() {
			m.External++
		}
		if s.IsLoopback() {
			m.Loopback++
		}
	}
	return m
}

// Report is the single object produced by every `sockscope inspect`
// run. All three output formats (table, json, markdown) are built
// from this struct so that outputs stay consistent.
type Report struct {
	Process     ProcessSummary  `json:"process"`
	Sockets     []SocketSummary `json:"sockets"`
	Mix         SocketMix       `json:"socket_mix"`
	Hints       []string        `json:"hints"`
	GeneratedAt time.Time       `json:"generated_at"`
}
