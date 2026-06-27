package proc

import "github.com/topcug/sockscope/internal/model"

// ReadSocketsForPID is the one-shot entry point for the cmd layer.
// It discovers every socket inode owned by the PID and then asks
// the per-family readers to resolve them.
func ReadSocketsForPID(pid int) ([]model.SocketSummary, error) {
	inodes, err := SocketInodes(pid)
	if err != nil {
		return nil, err
	}
	if len(inodes) == 0 {
		return nil, nil
	}

	var all []model.SocketSummary

	tcp, err := ReadTCPSockets(inodes)
	if err != nil {
		return nil, err
	}
	all = append(all, tcp...)

	udp, err := ReadUDPSockets(inodes)
	if err != nil {
		return nil, err
	}
	all = append(all, udp...)

	unix, err := ReadUnixSockets(inodes)
	if err != nil {
		return nil, err
	}
	all = append(all, unix...)

	return all, nil
}
