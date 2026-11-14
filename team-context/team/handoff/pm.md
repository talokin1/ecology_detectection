# Handoff: Project manager (agent [id removed])
Updated 2026-11-14 14:00 (Europe/Kiev)
## Done
- Researched every bot's context and aligned the team; wrote /workspace/spaceapps/TEAM_BRIEF.md.
- Relayed the team lead's rules: the Critique gate, big questions to the team lead, data-analysis-only scope, the speed/shared-computer rule, and handoff docs.
- Tracked the Ukraine study through two Critique rounds to final approval; logged that the GES DISC blocker is cleared.
- Wrote handoff/README_TEAM_ARCHITECTURE.md (rules, architecture, recreate steps).
## In progress
- Waiting for every bot to create its handoff file (thinker, worker, researcher, researcher2, critique .md); will verify they exist and are complete.
- Waiting for the team lead's low-token signal. When it comes, tell every bot to STOP and document what's left, then work on the migration with the team lead.
- Thinker is producing analysis questions and methods; route its output to Critique, then to Worker and the Researchers.
## Details
- Message bots with SendToAgent (priority true only when they must act). Read their histories with ReadTranscript.
- Open nits (deferred): a NaN family-size field, the T2M SON anti-conservative flag at r=-0.00, and a temp pickle written to /tmp.
## Files
/workspace/spaceapps/TEAM_BRIEF.md, /workspace/spaceapps/handoff/*, /workspace/critique/ukraine_methods_review.md, /workspace/ukraine_samples/
## Recreate
Create a Project manager agent, give it the team ids from README section 2, and have it read README_TEAM_ARCHITECTURE.md, TEAM_BRIEF.md and every handoff file. Then it messages each bot with the rules and its next task, and keeps the brief and this file updated after each change.
- CDS: I accepted the cc-by licence via the API at 14:46 (PUT /api/profiles/v1/account/licences/cc-by, revision 1).
- 15:20 MIGRATION: told all bots to stop, document, and stage in repo_staging/<bot>/ with MANIFEST.md; asked Thinker for the GitHub plan. Next: collect done-reports, have Critique check the staging, get the team lead approval, then push. CDS test job killed while queued; rerun later with Researcher 2 cds_requests.py.
