# JSON climate pipeline example

`input.json` contains five **synthetic** 1981–2024 regional series: air temperature, mean daily
maximum/minimum temperature, precipitation and soil wetness. `output.json` is the computed result,
including trends, uncertainty, FDR audit, SPI/SPEI and monthly/annual diagnostic series.

These files demonstrate the contract; their numbers are not observations or findings about Ukraine.
The example uses 999 bootstrap/permutation replicates. Their minimum p-value is 0.001;
the FDR audit reports the resolution limitation. Use `--bootstrap-samples 39` only for quick smoke runs.
Version 1.1.0 replaces unstable SPEI fitting with unbiased PWM and uses Firth event estimates;
sparse-event significance is explicitly unavailable. Details and limitations are in the linked guide.

Regenerate from the repository root:

```powershell
python scripts/make_climate_example.py --output examples/climate/input.json
python scripts/analyze_climate.py --input examples/climate/input.json --output examples/climate/output.json
```

For daily indices, generate input with `--daily` and choose a separate output filename.
Full instructions: [climate statistics pipeline](../../docs/climate-statistics-pipeline.md).

Example generator and pipeline implementation: SI-assisted with OpenAI Codex; human review pending.
