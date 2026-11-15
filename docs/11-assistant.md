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
| `ASSISTANT_PER_DAY` | `2000` | Questions per instance per day |
| `ASSISTANT_MAX_OUTPUT_TOKENS` | `2048` | Reply length cap |
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
