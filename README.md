# Careerflow Agent Skill

A portable AI agent skill for building a factual career profile, finding suitable jobs, tailoring resumes, recording applications, preparing interviews, and guiding self-directed learning.

Bring your own agent: Codex, Claude Code, or another assistant that can read Agent Skills and run local Python. No model API key or paid service is required by this project. Your agent's normal usage costs still apply. **The software never submits applications or sends messages.**

## What it does

- Keeps reusable career claims with provenance, revisions and employer/project scope.
- Deduplicates and screens jobs before spending time on tailored packages.
- Builds resumes and optional letters from selected evidence; freezes the exact reviewed submission.
- Records interview preparation/debriefs and training progress with evidence artifacts.
- Gives another agent a bounded, persistent workspace to continue without rereading everything.

Designed for different professions, not only software engineers. The included project-coordinator example is entirely fictional. This is **alpha software (0.2.0)**; see [design and limitations](docs/design.md).

## Start a training session

From the source checkout, run:

```bash
./run_self_training.sh
# The familiar spelling is also supported:
./run_self_trainging.sh
```

This initializes or resumes `~/careerflow-workspace`, opens **http://127.0.0.1:8872/** and returns your terminal. Set `CAREERFLOW_WORKSPACE` or pass `--root /path/to/private-workspace` to choose another location. Use `--no-browser` to print the URL, or `--foreground` to stop with Ctrl-C. Re-running reuses the same workspace server; it will not replace another app on that port.

In the browser, request a topic or leave it blank for an agent suggestion. Copy the displayed prompt into Codex/Claude Code with the skill installed. The agent reads your request and context, writes a lesson, then you refresh the browser to practice. Save a draft, submit an attempt, ask the agent to review it, then complete or retry. Lessons, drafts, artifacts and feedback share the same private workspace across agents. The web server does not call a model or execute exercise code.

Standalone skill users can run its entrypoint with `--root WORKSPACE training-web`. CLI users can use `careerflow --root WORKSPACE training-request --topic 'Your topic' --minutes 30`; `training-pending` shows queued work. See the [training session guide](skills/job-application-workflow/references/training-sessions.md) for generation/review schemas and resume commands.

## Install the skill

Requires Python 3.10+ on Linux, macOS or WSL. Clone the source and build the standalone bundle:

```bash
git clone https://github.com/liubinby/careerflow-agent-skill.git
cd careerflow-agent-skill
python3 scripts/package_skill.py
```

Install **one** copy in your agent's skill directory. These commands refuse to overwrite an existing skill:

```bash
# Codex CLI: personal skill
python3 scripts/install_skill.py --bundle dist/job-application-workflow.zip \
  --destination ~/.agents/skills/job-application-workflow

# Claude Code: personal skill
python3 scripts/install_skill.py --bundle dist/job-application-workflow.zip \
  --destination ~/.claude/skills/job-application-workflow
```

Restart your agent if needed, then ask it to use `job-application-workflow` to set up or continue your career workspace. Codex users may invoke `$job-application-workflow`; Claude Code users may invoke `/job-application-workflow`. For project-local installation, use `.agents/skills/` or `.claude/skills/` in that project. Other hosts can read the installed `SKILL.md` explicitly. **Install the generated bundle, not a copy of the bare source skill directory**, which does not include the runtime.

The format follows the [Agent Skills specification](https://agentskills.io/specification). Discovery locations are described in the [Codex skills documentation](https://developers.openai.com/codex/skills/) and [Claude Code skills documentation](https://code.claude.com/docs/en/skills). Native client invocation has not yet been independently tested; bundled-script compatibility is covered by tests.

## Create your private workspace

Keep personal data outside this public checkout. From your installed skill, use the full script path and an explicit root (substitute your installation path):

```bash
python3 ~/.agents/skills/job-application-workflow/scripts/manage_applications.py \
  --root ~/career-workspace init
python3 ~/.agents/skills/job-application-workflow/scripts/manage_applications.py \
  --root ~/career-workspace doctor
```

`init` creates an empty profile, shared layout and private-data ignore rules. It does not insert fictional experience. Ask your agent to read your resume/source evidence and guide initial intake, confirm preferences, then shortlist suitable jobs. The [workspace guide](skills/job-application-workflow/references/workspace.md) documents the schema and incremental commands.

You can also use the engine without installing an agent skill:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/careerflow --root ~/career-workspace init
.venv/bin/careerflow --root ~/career-workspace --help
```

No third-party dependencies are required for metadata, profile, interview or training commands. For PDFs, install the optional renderer and Poppler:

```bash
.venv/bin/python -m pip install '.[pdf]'
# Ubuntu/Debian: sudo apt-get install poppler-utils
# macOS: brew install poppler
```

For the standalone skill, install ReportLab in the Python environment used by its wrapper. Run `doctor` to check requirements. Every final PDF still needs actual page-image inspection and candidate review; text checks do not replace them.

## Workflow

```text
Evidence → versioned profile claims
Jobs → deduplicate → screen → shortlist → tailor → build → review
Actual submission → frozen record → interviews → debrief → targeted practice
```

Detailed references:

- [Workspace, profile and recovery](skills/job-application-workflow/references/workspace.md)
- [Applications, review and submission records](skills/job-application-workflow/references/applications.md)
- [Interviews and training](skills/job-application-workflow/references/interviews-training.md)
- [Interactive training sessions and local web app](skills/job-application-workflow/references/training-sessions.md)
- [Fictional demonstration](docs/demo.md)
- [Architecture and limits](docs/design.md)

## Privacy and control

Candidate records stay in the chosen workspace; the CLI makes no network or model calls. An agent may send content to its own model or connected tools under its host settings, so local storage does **not** imply offline model processing. Review your agent's data handling before sharing sensitive information. The workspace is not encrypted by this software.

Keep backups private. Generated checkpoints contain personal job/source data; they are not safe for public GitHub. Back up profiles, source evidence, learning notes and built/submitted artifacts together. A job checkpoint alone is not a full backup. Preparation never authorizes application submission, recruiter messages or acceptance of legal agreements.

## Develop

```bash
python3 -m pip install '.[pdf]'
python3 -m unittest discover -s tests -v
python3 scripts/package_skill.py
```

Tests use synthetic candidates and temporary workspaces. See [contributing](CONTRIBUTING.md). Report reproducible issues with fictional/minimized data; never attach someone else's resume, credentials or private employer information.

## License

[MIT](LICENSE), copyright 2026 Bin Liu. The license covers project code, instructions and fictional examples. User career records and third-party job descriptions are not licensed by this repository. Dependency licenses remain separate.
