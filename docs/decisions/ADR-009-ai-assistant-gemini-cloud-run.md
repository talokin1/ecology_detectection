# ADR-009 — In-app AI assistant: Gemini on Vertex AI behind a Cloud Run service

- Status: Proposed (direction set by Molfarion on 2026-11-15; team confirmation pending)
- Date: 2026-11-15
- Deciders (names): Molfarion; team to confirm
- Requirement IDs: R-13 (SI suggests variables), R-10/R-11 support; ADR-001 candidate element 6

## Context
ADR-001 lists an "in-app SI assistant grounded on catalog + computed numbers" as a candidate
differentiator. The team chose to build it with Google Gemini on Google Cloud. Constraints:
- The web app is a static site on GitHub Pages; it cannot hold credentials (CLAUDE.md rule 5).
- Every number shown must be reproducible from code + cached data (rule 2). An LLM must not
  produce statistics, only explain the ones the pipeline computed.
- SI output in the product must be labelled (rule 6, R-35).

## Options
1. **Cloud Run service + Vertex AI with the service account** — no API key exists anywhere;
   Google-managed auth; scales to zero. Needs a GCP project with billing.
2. Cloud Run + Gemini Developer API key in Secret Manager — simpler setup, but a long-lived key
   to protect and rotate.
3. Call Gemini from the browser — rejected: exposes credentials.

## Decision
Option 1. `backend/trend_detective/assistant/` is a FastAPI service (`POST /v1/chat`) deployed
on Cloud Run from `deploy/assistant/Dockerfile`. It calls `gemini-3.8-flash` (GA, retirement not
before 2027-09-02; configurable with `GEMINI_MODEL`) through the `google-genai` SDK in enterprise
(Vertex AI) mode with Application Default Credentials.

Grounding and honesty safeguards:
- The browser sends only the question, the ids of the analysis on screen and recent turns. The
  **server** loads that analysis from the same precomputed JSON the app ships (the image contains
  `frontend/public/data/{index,catalog}.json`, `analysis/` and `docs/10-methods.md`), so a visitor
  cannot inject numbers into the prompt.
- The system instruction allows only numbers from the grounding, forbids stronger wording than the
  verdict, causal claims beyond `why_it_trends`, and predictions.
- A server-side **number check** flags any number in a reply that no grounded value rounds to; the
  UI shows "Check these numbers" next to it.
- Suggestions are ids only; the server drops unknown ids and pairs without an analysis, and fills
  names, verdict headlines and links from the data.
- Replies are labelled "AI-generated · <model>" with a note that the verdict card is the reference.
- Cost/abuse guard: CORS allow-list, 600-character questions, per-client rate limit, per-instance
  daily cap, Cloud Run `--max-instances`.
- The button appears only when the build sets `VITE_ASSISTANT_URL`; without it the app is unchanged.

## Consequences
- New runtime dependency outside NASA: Google Cloud (billing account, Vertex AI API). If it is down
  or the budget is spent, the app still works; the assistant shows a polite error.
- The image must be rebuilt whenever `frontend/public/data` changes, or explanations go stale.
- The number check is a heuristic (small whole numbers 0–12 are ignored); it reduces, not
  eliminates, the risk of a wrong number. Before the demo, the team reviews sample answers for the
  case questions (log them in `docs/08-si-usage-log.md`).
- Deployment steps: `docs/11-assistant.md`.

## Amendment 1 (2026-11-15): tool calling over our precomputed results
At first the model saw only the analysis on screen, so it could not answer "where", "A vs B" or
"what happened in 2010". We chose **tool calling** over embedding-based RAG: the data are exact
structured numbers (rankings, comparisons, yearly values), which similarity search retrieves
poorly, and the text corpus (the Methods page) already fits in the prompt.

`backend/trend_detective/assistant/tools.py` declares five **read-only** tools over the files the
app ships: `get_analysis`, `rank_regions`, `compare_regions`, `get_series`, `map_cell`. None
computes a new statistic. `compare_regions` returns a tested difference only where one was
precomputed (story regions); otherwise it returns both results with `difference_tested: false`
and the rule that neither may be called faster. `rank_regions` carries a multiple-places caveat.
Tool results join the facts for the number check; successful lookups are listed under the answer
with links. At most `ASSISTANT_MAX_TOOL_ROUNDS` (4) rounds; the last round has no tools.

Cost: about 1.5–2× per question (each round resends the prompt; implicit caching softens it).

## Amendment 2 (2026-11-15): replies in the visitor's language
The interface, documentation and default stay English (CLAUDE.md rule 1, submission rule). Only the
assistant's reply follows the language of the visitor's latest question (English when unclear), with
the cautious wording translated faithfully. The number check reads decimal commas ("0,54") as well as
thousands separators ("1,000"), so invented numbers are still flagged in other languages. Live check:
Ukrainian and English questions answered in kind; all numbers grounded.

## Amendment 3 (2026-11-15): Google Search for context
The assistant may use Gemini's Grounding with Google Search, for **context only** (named events,
physical explanations, published research, how instruments work). The prompt forbids using the web
for the app's own trends, rates, ranges, p-values or verdicts, forbids searching when the app's data
answers, and requires naming the source in the sentence. Web sources are listed under the answer as
"From the web (not our data)" with Google's URIs unmodified; Google's Search Suggestions HTML is shown
unmodified in a sandboxed frame (no scripts). Numbers inside answer segments that grounding cites to
a web source are not flagged; every other number must still come from the app's data or tools.
Search is billed per query (third-party sources: about $14 per 1,000 for Gemini 3; Google's page not
read, verify before judging): `ASSISTANT_WEB_SEARCH` switches it off, `ASSISTANT_SEARCHES_PER_DAY`
(default 500 per instance) caps it. Live check: a mixed question used NOAA for the cause and the app's
own 2010 values for "was it unusual"; a pure data question did not search.
