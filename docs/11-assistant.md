# 11 — AI assistant (Gemini on Google Cloud): run and deploy

Design and safeguards: [ADR-009](decisions/ADR-009-ai-assistant-gemini-cloud-run.md).
Code: `backend/trend_detective/assistant/` · tests: `backend/tests/test_assistant.py` ·
UI: `frontend/src/components/Assistant.tsx`.

## Current deployment (2026-11-15)
- URL: `https://td-assistant-179871734109.europe-west1.run.app` (Cloud Run service `td-assistant`,
  region `europe-west1`, model `gemini-3.8-flash`, max 2 instances, service account with
  `roles/aiplatform.user` only). Ask Molfarion for access to the GCP project.
- Allowed origins: `https://talokin1.github.io`, `http://localhost:5173`, `http://localhost:4173`.
- Live checks passed: explanation of Ukraine air temperature (wording rules, all numbers grounded),
  a no-clear-trend result (Ukraine soil: verdict stated plainly, FDR-passing sub-findings named),
  and a prompt-injection + forecast request (refused; "2050" flagged as unverified).

## Tools (read-only lookups Gemini can call; ADR-009 amendment 1)
| Tool | Answers | Reads |
|---|---|---|
| `get_analysis(region_id, variable_id)` | any place's full result | `analysis/*.json` |
| `rank_regions(variable_id, direction, place_set, min_level, limit)` | where a variable changes most | `index.json` verdicts |
| `compare_regions(region_a, region_b, variable_id)` | A vs B (tested only for story-region pairs) | `compare/*.json`, verdicts |
| `get_series(region_id, variable_id, start_year, end_year)` | yearly (and one year's monthly) anomalies | `analysis/*.json` series |
| `map_cell(variable_id, lat, lon)` | the trend in one 2° map square | `map/*.json` |

Replies list the lookups under `looked_up` (label and link); the log line lists `tools`
(`!` marks a rejected call). `ASSISTANT_MAX_TOOL_ROUNDS` (default 4) caps the loop.

## API
`POST /v1/chat`

```json
{ "message": "What does this mean?", "region_id": "ukraine", "variable_id": "t2m",
  "history": [{ "role": "user", "text": "..." }, { "role": "assistant", "text": "..." }] }
```

Reply: `answer`, `suggestions[]` (ids, names, verdict, `href`), `unverified_numbers[]`, `model`,
`disclaimer`. Errors: 400 bad id, 422 invalid body, 429 rate limit, 502 model unavailable.
`GET /health` returns `{"ok": true}`.

## Environment variables
| Variable | Default | Meaning |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | — (required) | GCP project that pays for Vertex AI |
| `GOOGLE_CLOUD_LOCATION` | `global` | Vertex AI location |
| `GEMINI_MODEL` | `gemini-3.8-flash` | Model id (check the Vertex AI model-versions page before changing) |
| `ALLOWED_ORIGINS` | localhost dev ports | Comma-separated browser origins (CORS). With `gcloud --set-env-vars`, use a custom delimiter: `"^@^A=1@ALLOWED_ORIGINS=https://x,http://y"` |
| `ASSISTANT_PER_MINUTE` | `6` | Questions per client per minute |
| `ASSISTANT_PER_DAY` | `300` | Questions per instance per day (in-memory; resets when an instance restarts, so it limits abuse but is not a hard spending cap) |
| `PRICE_INPUT_PER_M`, `PRICE_CACHED_PER_M`, `PRICE_OUTPUT_PER_M` | `0.75`, `0.075`, `3.75` | USD per 1M tokens used only for the `est_usd` field in the logs |
| `ASSISTANT_MAX_OUTPUT_TOKENS` | `2048` | Reply length cap |
| `ASSISTANT_WEB_SEARCH` | `1` | Google Search grounding for context (`0` = off; ADR-009 amendment 3) |
| `ASSISTANT_SEARCHES_PER_DAY` | `500` | Search queries per instance per day; then answers use the app's data only |
| `PRICE_SEARCH_PER_1K` | `14` | USD per 1,000 search queries, only for `est_usd` in the logs |
| `ASSISTANT_DATA_DIR`, `ASSISTANT_METHODS` | repo paths | Set by the Dockerfile |

No API key is used: authentication is Application Default Credentials.

## Run locally (PowerShell)
```powershell
pip install -r requirements-assistant.txt
gcloud auth application-default login
$env:GOOGLE_CLOUD_PROJECT = "<project-id>"
python -m uvicorn trend_detective.assistant.app:app --app-dir backend --port 8080
# second terminal
cd frontend
$env:VITE_ASSISTANT_URL = "http://localhost:8080"
npm run dev
```
(bash: `export VAR=value` instead of `$env:VAR = "value"`.)

## Deploy to Cloud Run (once, by whoever owns the GCP project)
```powershell
$P = "<project-id>"; $R = "europe-west1"; $IMG = "$R-docker.pkg.dev/$P/trend-detective/assistant"
gcloud config set project $P
gcloud services enable run.googleapis.com aiplatform.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com
gcloud artifacts repositories create trend-detective --repository-format=docker --location=$R
gcloud iam service-accounts create td-assistant --display-name "Trend Detective assistant"
gcloud projects add-iam-policy-binding $P --member "serviceAccount:td-assistant@$P.iam.gserviceaccount.com" --role roles/aiplatform.user

# from the repo root (uploads only the files listed in .gcloudignore)
gcloud builds submit --config deploy/assistant/cloudbuild.yaml --substitutions "_IMAGE=$IMG"
gcloud run deploy td-assistant --image $IMG --region $R `
  --service-account "td-assistant@$P.iam.gserviceaccount.com" `
  --allow-unauthenticated --max-instances 2 --memory 512Mi --cpu 1 --timeout 60 `
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$P,GOOGLE_CLOUD_LOCATION=global,ALLOWED_ORIGINS=https://<org>.github.io"
```
Then set the repository variable **`ASSISTANT_URL`** (Settings → Secrets and variables → Actions →
Variables) to the Cloud Run URL. The next push to `main` builds the site with the assistant button.

Set a **budget alert** on the billing account before the judging period.

## Keep it in sync
The image contains a copy of `frontend/public/data`. After `scripts/make_app_data.py` changes the
data, rebuild and redeploy the image (the two `gcloud` commands above).

## Cost (measured 2026-11-15, gemini-3.8-flash, global endpoint)
Each answer writes one `assistant_reply` line to Cloud Logging with token counts and `est_usd`:
```powershell
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="td-assistant" AND jsonPayload.message="assistant_reply"' --project <project-id> --limit 50 --format="value(jsonPayload.prompt_tokens,jsonPayload.cached_tokens,jsonPayload.output_tokens,jsonPayload.est_usd)"
```
- First 7 live questions: 11.5k–16.8k input tokens, 110–430 output tokens, $0.009–0.014 each at
  the introductory price ($0.75 / $3.75 per 1M input / output tokens until 2026-12-31; reported to
  double from 2027-01-01).
- The static part of the prompt (~10k tokens) comes first, so Gemini's implicit cache can bill it at
  the cached rate; one hit gave 8.1k cached tokens and $0.0035 (−61%). Hits are best-effort.
- Cloud Run time (~2–7 s per answer) stays inside the monthly free tier at demo volumes.
- Ceiling: 2 instances × `ASSISTANT_PER_DAY=300` ≈ 600 answers ≈ $8/day now, ≈ $17/day in 2027.
  The per-instance count resets on restart, so a billing budget alert is the real safety net.
