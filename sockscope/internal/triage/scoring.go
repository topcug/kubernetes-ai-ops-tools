package triage

// This file is deliberately empty in v1. The internal design note
// explicitly rejects risk scores like "risk score 92" because they
// create false confidence. Hints.go produces plain notes instead.
//
// If v2 introduces a structured rule engine, it should live here so
// that hints.go stays a thin, human-readable summary layer.
