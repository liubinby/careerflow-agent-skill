# Contributing

Use fictional data in examples, issues and tests. Do not commit private career workspaces, application PDFs, browser profiles, credentials or employer material without rights to redistribute it.

The runtime source is `careerflow/`. Skill instructions live in `skills/job-application-workflow/`; the ZIP is generated, not edited. Add runtime modules to the explicit packaging allowlist when needed and cover standalone behavior in tests. Keep provider-specific UI metadata optional. Do not add automatic submissions, model API dependencies or telemetry to routine local operations.

Run `python3 -m unittest discover -s tests -v` with the PDF extra and Poppler installed, then `python3 scripts/package_skill.py`. Test public artifacts in a fresh temporary workspace, not a candidate's database. Changes to final PDF layout need visual inspection of every changed page in addition to tests. Record migrations and recovery implications when changing persistent data formats.

Keep changes tied to demonstrated use cases. Preserve stable claims, provenance, selected dependency invalidation, explicit review and immutable submissions. Agent/client installation reports are welcome; distinguish tested client behavior from compatibility inferred from the skill format.

Contributions are provided under the repository's MIT license. Dependencies retain their own licenses. Use GitHub issues for minimized reproducible problems and pull requests for changes; do not post private records to either.
