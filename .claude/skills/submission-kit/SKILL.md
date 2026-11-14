---
name: submission-kit
description: Produce and check the NASA Space Apps 2026 submission package for the Trend Detective project — project page fields, 30-second demo video script with English subtitles, ≤7-slide deck, NASA Data and References fields, SI usage text, final eligibility checklist. Use for any pitch, demo, slide, video, submission text or final pre-submit check.
---

# Submission kit

Rules source: NASA Space Apps 2026 Project Submission Guide and Judging & Awards Guide
(summarised in `docs/01-challenge-brief.md` and `docs/03-judging-rubric.md`).

## Project page fields (all English)
1. **Project Name** — short, memorable, says the benefit.
2. **High-Level Project Summary** — what we built, how it answers the challenge (what/where/how much/
   significant), why it matters. ~150 words.
3. **Link to Project Demo** — public video (≤ 30 s) or slides (≤ 7). Test in a private window.
4. **Link to Final Project** — live app URL + GitHub repo (public, no login).
5. **Detailed Project Description** — what it does, how it works (data → stats → visuals), benefits,
   goals, tools/languages. Include 2–3 screenshots (JPG/PNG/GIF ≤ 10 MB).
6. **Use of Super Intelligence** — from `docs/08-si-usage-log.md` (not shown to judges, but SI indicators
   in the project are).
7. **NASA Data** — specific datasets with short names/versions (from catalog + `09-references.md`).
8. **Space Agency Partner Data and Other References** — every library, dataset, image, font.

## 30-second video script template (timings from the official guide)
| Time | Content |
|---|---|
| 0:00–0:02 | Team name + who we are |
| 0:02–0:05 | Hook: the challenge in one question ("Is your region really drying out?") |
| 0:05–0:10 | Product name + tagline on screen |
| 0:10–0:20 | Screen recording: pick variable → region → trend map → verdict; mention NASA datasets |
| 0:20–0:30 | Future: classrooms, any region, any variable; closing frame with URL |
English subtitles burned in if speech is not English. No minors' faces/voices. Watermark SI-generated
footage. Final render must be ≤ 30.0 s — verify with `ffprobe`.

## 7-slide deck template
1. Title: project name, team name, member names, challenge name.
2. Problem: many variables, regional opposite trends, students can't test significance.
3. Solution: product screenshot + one-line value proposition.
4. User experience: wizard → map → verdict (3 screenshots).
5. Science: data sources (NASA), method (Sen + autocorrelation-aware MK + FDR), validation table.
6. Case file highlight: one striking result (e.g. opposite trends) with its verdict.
7. Impact & future + links.
Readable fonts (≥ 24 pt), few words, strong visuals.

## Final eligibility checklist (all must be ✅)
- [ ] All members on the team page, same Local Event, not waitlisted.
- [ ] Every required field filled, English.
- [ ] Demo ≤ 30 s or ≤ 7 slides; public link works logged-out.
- [ ] Final project link public; app loads logged-out on another network.
- [ ] ≥ 1 NASA dataset named in NASA Data field.
- [ ] References complete (code, data, images, fonts).
- [ ] SI usage described; SI media watermarked; no NASA branding in generated content.
- [ ] Both checkboxes ticked; "Submit for Judging" clicked; confirmation banner screenshot saved.
- [ ] Submitted before Sunday 23:59 local time of the Local Event.

## Quality bar
Run the `judge-panel` subagent on the draft page + demo script and fix every item it scores below 5.
