# Fictional end-to-end demonstration

Run from the source checkout. All example facts, job checks and source identities are synthetic. Do not use these files as a real candidate profile or imply the example.com job is live.

```bash
python3 -m careerflow --root /tmp/careerflow-demo init --profile examples/fictional-profile.json
python3 -m careerflow --root /tmp/careerflow-demo import examples/jobs.jsonl
python3 -m careerflow --root /tmp/careerflow-demo screen-batch examples/decisions.jsonl
python3 -m careerflow --root /tmp/careerflow-demo shortlist example-co-r001
python3 -m careerflow --root /tmp/careerflow-demo draft example-co-r001
cp examples/content.json /tmp/careerflow-demo/applications/example-co-r001/content.json
python3 -m careerflow --root /tmp/careerflow-demo build example-co-r001
python3 -m careerflow --root /tmp/careerflow-demo dashboard
python3 -m careerflow --root /tmp/careerflow-demo validate
```

Use a different empty temporary root if the demo already exists: init refuses overwrite. Build returns the immutable output directory. Render its PDF using `pdftoppm -png <file.pdf> /tmp/careerflow-review` and inspect every page. No review or submission approval is granted by this example. Open `/tmp/careerflow-demo/APPLICATIONS.html` in a browser to explore the local dashboard.

For learning, create a real exercise artifact inside the demo workspace, then use `training-add` and `training-update` as described in the [training guide](../skills/job-application-workflow/references/interviews-training.md). Do not mark training complete merely because you read instructions.
