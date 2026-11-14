#!/bin/bash
# Gate for this archive. Run from the repository root.
cd "$(dirname "$0")/../../../.."
python team-context/tools/sync_check.py
