# Private workspace and career evidence

Run all commands through `python <skill-directory>/scripts/manage_applications.py --root <workspace>` (abbreviated `careerflow` below). Source-checkout users can run `python -m careerflow --root <workspace>`. Place `--root` before the command.

## Onboard without a prepared profile

```bash
careerflow init
careerflow doctor
careerflow profile-set --key name --value 'Candidate name' --source 'Candidate statement'
careerflow profile-set --key email --value 'candidate@example.com' --source 'Candidate statement'
```

`init` creates a blank structured profile and shared layout, with private material ignored by Git. It refuses an existing profile or template. `init --profile profile.json` imports a compatible structured profile; it does not read or extract PDFs. Ask the agent to inspect a candidate-provided resume and normalize supported facts first, preserving source files under `evidence/`. Do not use the fictional demo as a candidate's real profile.

Collect preferred roles/industries, location/remote preferences, level/pay, availability and work eligibility only as needed. Eligibility is not inferred from name or country. Keep private answers in preferences, not resume output. Start with confirmed basics and a few relevant projects instead of requiring a perfect life history.

Use `employment-set <stable-id> --file employment.json --source 'Candidate confirmation'`; the JSON contains `employer`, `title` and `dates`. Education is a list of candidate-confirmed text entries in `data/profile.json`; preserve revisions/provenance in the evidence notes when editing it. An employment group may represent a clearly labeled independent project, volunteer work or internship; do not invent employment for candidates without jobs.

```bash
careerflow profile-intake --employer example --project 'Project name' --text 'Candidate statement' --source 'Candidate conversation, date'
careerflow profile-accept NOTE_ID --text 'Accurately scoped accomplishment' --tags domain,project
careerflow claims --employer example --query 'relevant topic' --limit 8
careerflow preference-set --key work_location --value '"Remote or preferred city"' --source 'Candidate statement'
```

`profile-intake --kind boundary` records explicit lack of experience. An experience claim can be corrected with `profile-accept NOTE_ID --supersedes CLAIM_ID`; the stable ID and revision history survive. The same accepted intake is idempotent. Run `impact CLAIM_ID`, batch affected prose changes, then rebuild selected drafts. Do not silently reconcile conflicting prose into the profile.

## Authority and continuity

| Material | Authority |
|---|---|
| Candidate fields, employment, education, claims, preferences | `data/profile.json` |
| Original source statements and later intake | `evidence/`, `data/intake/` |
| Jobs, screening, source snapshots, state/history | `data/careerflow.sqlite3` |
| Readable recovery checkpoints | Generated `data/jobs.jsonl`, `data/posting-snapshots.json` |
| Draft claim selections and editable letters | `applications/<id>/content.json`, `letter.md` |
| Exact built and submitted versions | Immutable `builds/` and `submissions/` per application |
| Interview/training state and linked narrative artifacts | `interviews/*.json`, `training/*.json` and referenced Markdown/files |
| Navigation | Generated `APPLICATIONS.html` and `.md` |

Use `list --query ... --limit 20`, `show ID`, `context ID --query ... --limit 8`, and `learning-list --limit 20` to resume cheaply. Context search is lexical, not a confidence score. Validate and regenerate the dashboard after a completed change batch.

`checkpoint` exports job/source records only. Back up the entire private workspace, including evidence, profile, interviews/training and PDFs. `restore <backup>/data/jobs.jsonl` restores jobs/sources into an empty database; copy the matching profile, notes and artifacts as well. Never remove a live database to test restore. Use a separate temporary workspace. Keep any Git backup private and check ignored files before relying on it as a complete backup.
