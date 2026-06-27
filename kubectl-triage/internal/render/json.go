package render

import (
	"encoding/json"
	"fmt"
	"io"

	"github.com/topcug/kubectl-triage/pkg/types"
)

// JSON renders the TriageReport as indented JSON.
func JSON(w io.Writer, r *types.TriageReport) error {
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	if err := enc.Encode(r); err != nil {
		return fmt.Errorf("marshal report: %w", err)
	}
	return nil
}
