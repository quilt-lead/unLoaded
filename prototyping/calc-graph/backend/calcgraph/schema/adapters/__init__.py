"""Adapters: existing calc-graph outputs -> the F1 schema. Each `convert()` returns
(Bundle, Tally); the Tally says what was rejected and why, which provenance fields the
adapter had to supply, and how many numbers carry a unit. See scripts/schema_audit.py."""
