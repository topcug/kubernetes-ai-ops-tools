package render

import (
	"encoding/json"
	"io"

	"github.com/topcug/sockscope/internal/model"
)

// JSON writes the report as indented JSON. This is the stable format
// for automation and piping into jq or a SIEM ingestion pipeline.
func JSON(w io.Writer, r model.Report) error {
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	return enc.Encode(r)
}
