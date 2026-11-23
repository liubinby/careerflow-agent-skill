# Interviews, debriefs and self-training

Commands below follow [workspace](workspace.md). Preparation records never imply application submission, an interview invitation, completed study, or professional experience.

## Prepare for an actual role

Reuse the posting, final resume, scoped claims and existing stories. Ask for interview date, available preparation time and recruiter-confirmed format only when not already known. If format is unknown, label an adjustable plan as a recommendation. Separate:

- Refresh: demonstrated skills needing fluent explanation or practice.
- Develop: missing or shallow areas requiring learning; state realistic short-term limits.
- Demonstrate: real projects, decisions, debugging, collaboration and defensible outcomes.

Choose a small priority matrix: topic, role relevance, exercise, observable completion criterion. Tailor to the candidate's profession. For software roles, balance coding, design, debugging and project stories; for other professions use appropriate work samples, case studies or domain exercises. Algorithm practice is useful when the format calls for it; do not prescribe it universally or claim a list predicts employer questions.

Verify learning resources through current primary sources when web access exists; save verification date and version/access dependencies. Without browsing, label links unverified. Prefer achievable exercises with a concrete artifact and a local/mock option where appropriate; a simulation is not hardware or production experience. Do not provision paid resources or alter host/network settings just because a plan mentions a lab.

Store preparation/debrief prose as workspace Markdown, e.g. `interviews/<job-id>-prep.md`. Link it using the notes option:

```bash
careerflow interview-add --job JOB_ID --date '2026-12-01T14:00:00-08:00' --source 'Candidate-reported invitation' --notes interviews/JOB_ID-prep.md
careerflow interview-update INTERVIEW_ID --status completed --note 'Candidate reported interview completed' --notes interviews/JOB_ID-debrief.md
```

The linked job can be at intake: a recruiter conversation is valid without a tracked application. This does not advance pipeline stage or invent a submission. Dates require a UTC offset to avoid ambiguous local times. Paths are relative to the workspace and must exist inside it.

## Accumulate interview experience

Capture timing, format, reported questions, candidate's answer, interviewer follow-ups, coding corrections, and candidate self-assessment. Keep these separate from the agent's recommended answer and future practice prompts. Do not present reconstruction as a transcript or score yourself as the interviewer. Distinguish individual feedback from generalized company interview claims.

Use the debrief to improve project narratives and choose a few practical follow-ups. New details about actual past work go through profile intake/accept with provenance and scope; hypothetical answers do not become career claims. Preserve earlier notes and completed practice.

## Track training with evidence

Reuse one topic across relevant jobs rather than duplicate a curriculum per requisition. Record an observable goal and an achievable exercise with constraints, output and review method. Let the candidate attempt it, evaluate against the goal, explain errors and schedule a focused retry if needed. Avoid measuring readiness by time spent or problem count alone.

```bash
careerflow training-add --topic 'Relevant topic' --goal 'Observable completion criterion' --source 'Agreed study plan' --job JOB_ID
careerflow training-update TRAINING_ID --status in_progress --note 'Exercise started'
careerflow training-update TRAINING_ID --status completed --evidence training/artifacts/result.md --note 'Result and validation against the goal'
careerflow learning-list --kind training --limit 20
```

Job links are optional. `completed` requires an existing artifact and a result note; the agent still evaluates its quality. The engine does not certify competence from file existence. Keep detailed lab instructions, attempts, feedback and resource links in Markdown. Statuses are planned, in_progress, completed and paused. Interview statuses are scheduled, completed and cancelled. Updating either preserves history and does not modify professional claims.

Weekly review should adjust priorities from evidence, role deadlines and candidate availability. Preserve completed work and explain readiness limits. Do not build a public training site or schedule reminders unless requested.
