# Job research, drafting and submission records

Commands below follow the entrypoint and `--root` convention in [workspace](workspace.md).

## Intake and screen

`import jobs.jsonl` accepts one object per line with `employer`, `title`, `url`, optional `requisition`, `location`, `family`, and `requirements`. URLs must be public HTTP(S). Requisition identity deduplicates across URL slugs. Use employer URLs and record uncertainty when only a mirror or supplied text is available.

`source ID --file posting.txt --url URL --kind employer|mirror|provided` records the actual retrieved description by content hash and provenance. It does not fetch the page. Do not fabricate historical snapshots or mark a search snippet as a full employer description. Verify live availability again before submission.

`screen-batch decisions.jsonl` processes one decision per line:

```json
{"id":"example-co-r001","pursuit":"pursue","priority":"normal","checks":[{"key":"interest","status":"pass","detail":"Candidate expressed interest"},{"key":"location","status":"review","detail":"Attendance expectation unknown"},{"key":"eligibility","status":"review","detail":"Not yet confirmed"},{"key":"level_compensation","status":"review","detail":"Range not provided"},{"key":"technical_fit","status":"pass","detail":"Relevant scoped evidence; assess gaps"},{"key":"source_freshness","status":"pass","detail":"Employer posting retrieved today"}],"reason":"Relevant role; material conditions still open"}
```

Valid pursuit values are `review`, `pursue`, `defer`, `decline`; priorities are `high`, `normal`, `low`; check statuses are `pass`, `review`, `fail`. Preserve distinct pursuit, priority, pipeline stage, and outcome. A declined unsubmitted role is not an employer rejection. Do not claim interview probability from a match score.

`shortlist ID` gates production on a pursue decision and resolved conditions. `--override 'Candidate requested a draft despite unresolved location'` documents an authorized review exception; it cannot bypass failed checks. Do not introduce approval gates for routine unknown skill details.

## Tailor and review

`draft ID` creates the first empty claim selection and letter. `draft ID --from-application OTHER_ID` reuses a role-family selection when available. Both refuse existing drafts. Tailor `resume.headline`, `summary`, `skills`, and `experience` in `content.json`; each experience selection contains an `employment_id` and `claim_ids`. Select active factual claims under the correct employer. Summary and skill lines require the same factual review as claims.

Keep `letter.md` empty unless useful or requested. When writing it, list its underlying claim IDs in `letter_claim_ids`, including evidence absent from the resume. Public contact fields come from the profile. Private eligibility/preferences stay out of output. Any application-specific email or display-title override requires candidate provenance; it must not rewrite the master or submitted copies.

`build ID` makes one styled resume by default; `--layout plain`, `--layout both`, and `--letter` are optional. Run `doctor` for dependencies. A changed relevant input creates a new build; cached identical builds are reused. Do not edit built PDFs in place.

Extract text, render all final PDF pages with `pdftoppm -png FILE PREFIX`, and inspect each image using available image tools. Ensure readable text, consistent hierarchy, no clipping/overlap, correct contacts and employer/project scope. `review ID --visual --note 'Evidence of final page inspection'` records actual inspection; `--candidate` records actual candidate approval. Neither can be inferred from a successful build. If the candidate approves only submission intent, describe that precisely rather than claiming they inspected PDFs.

## Actual submission and outcomes

The CLI never submits an application or sends a message. Use available external tools only within the candidate's authorization, and separately resolve any required legal/financial consent. Record the exact final reviewed document only after observing confirmation or receiving the candidate's report:

```bash
careerflow record-submission ID --date YYYY-MM-DD --confirmation 'Observed portal confirmation or candidate report'
careerflow advance ID --stage interviewing --note 'Candidate-reported invitation'
careerflow advance ID --stage closed --outcome rejected --note 'Employer decision reported by candidate'
```

Submission recording checks review gates and hashes, then freezes the package. Missing original documents or review proof must stay unknown; do not manufacture a build to represent a historical submission. Historical applications without matching artifacts can be retained as clearly attributed narrative evidence until a dedicated import path exists.

Run `validate`, `dashboard`, and `checkpoint` after changes. The dashboard is generated navigation, never a second status database. Open it locally in a browser; if serving it, bind to `127.0.0.1` and keep the private workspace off public hosting.
