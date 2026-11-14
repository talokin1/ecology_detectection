"""Offline, catalog-aware JSON climate statistics.

Public API: ``analyze(payload)`` and ``analyze_file(input_path, output_path)``.

SI-assisted (OpenAI Codex); see docs/08-si-usage-log.md. Human science review pending.
"""

from .pipeline import analyze, analyze_file

__all__ = ["analyze", "analyze_file"]
