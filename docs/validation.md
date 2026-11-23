# Initial release verification

## Guided training update (0.2.0)

All 36 local tests pass. Added lifecycle and HTTP integration tests for lesson generation, persisted drafts, retries, immutable attempts, rubric review coverage, completion gates, unchanged professional claims, request queues, and shared CLI/browser records. Web tests reject cross-origin writes, missing tokens, Host rebinding and arbitrary workspace-file access; startup reuses only the same workspace. A regression test launches from a checkout with an obsolete engine to verify the child uses the correct runtime. Local socket tests require permission to bind localhost in restricted agent sandboxes.

Exercised the real browser workflow against an isolated fictional workspace: request topic, generate lesson through CLI, start, save draft, reload and restore, submit, record agent feedback, refresh and complete. Confirmed responsive layout has no horizontal document overflow at 390 CSS pixels. No candidate progress was fabricated by this demonstration.

Native host model invocation remains an explicit handoff rather than an automatically tested integration. The browser shows the prompt to paste into the user's chosen agent. The old browser-local planner remains separate; its existing data is not migrated.

## Initial alpha (0.1.0)

Verified locally on Python 3.10.15 / Linux, 2026-11-23 (27 tests):

- Synthetic unit/integration tests cover import/deduplication, atomic decisions, shortlist gates, claim revisions, dependency freshness, caching, recovery, PDF builds, review gates and immutable/tamper-checked submissions.
- New acceptance tests cover blank initialization, safe input validation and no-overwrite behavior, a first draft without a reference application, workspace-relative paths, interview state independent of submissions, training artifacts, and unchanged professional claims after practice.
- Generated skill bundles are tested from separate directories without PYTHONPATH. The same wrapper initializes private workspaces under both `.agents/skills/` and `.claude/skills/` installation layouts. This is a runtime/layout test, not a native model invocation test.
- Bundle tests add fake unlisted secrets in an isolated source copy and verify exclusion. Installer tests reject modified files, path escapes and existing destinations.
- Built a Python wheel and installed it into an isolated virtual environment. Ran init, doctor and validate from outside the checkout without ReportLab installed; metadata functions worked and missing PDF support was reported correctly.
- Built a fictional one-page project-coordinator resume, rendered its page to PNG and visually inspected the complete page: readable text, education present, no clipping or overlap. Automated regression checks also verify education remains in one-page output and omitted optional contacts do not produce a fake profile link. Visual inspection is not candidate approval.
- Skill frontmatter passed the local skill validator. Only broadly supported frontmatter fields are used; environment requirements are in the body for older validator compatibility.

GitHub Actions is configured for Python 3.10 and 3.12 on Ubuntu with ReportLab/Poppler. Results beyond the local environment must be confirmed from the workflow, not inferred from its configuration. Native Codex and Claude Code invocation and macOS/WSL operation have not yet been exercised.

No candidate records, original application packages, browser state or prior private Git history are part of the public repository. No production workspace is migrated by this release. The library still relies on the agent for factual interpretation, live source research, meaningful artifact review and external-action authorization.
