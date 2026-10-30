# Configurations, schema 1

Run commands from the repository root. These reference small programmatic CC0 media
under `tests/fixtures/research`; they do not choose a research thesis.

- `image-comparison.json`: image evaluators, including explicit unavailable optional weights.
- `video-sampling.json`: sparse/dense/two-pass observation on real decoded fixtures. The judge is **synthetic**, so its verdicts say nothing about model performance.
- `selection-experiment.json`: fixed imported candidate pool with explicit repeats/test split.
- `selection-candidates.json`: analytically inspectable synthetic advanced-analysis input.
- `generation.json`: replace workflow path, node/input bindings and identity from an actual ComfyUI API workflow. Calls are disabled until explicitly enabled in config.
- `live-openai.json` and `live-anthropic.json`: place the object in an
  experiment's `judges` list after checking the pinned model and dated USD rates
  against the linked official source. These are paid inference configurations;
  the pinned models passed the [bounded image smoke](../../docs/research-validation.md),
  which does not validate a full study or other protocols. API keys come from
  environment variables, never JSON. Both examples bound calls and output tokens
  and disable automatic retries for the initial smoke. To test pairwise judgments,
  use `mode: pairwise` with two models/candidates and keep the total study budget
  explicit. Token/call budgets are not a guaranteed provider billing cap; use an
  independently approved spending limit and provider account controls.
- `rubric.json`, `practice.json`: human instructions and practice source prompt IDs.

Frozen configurations do not accept in-place edits. Create a new experiment for a
new model, rubric, metric version, split or preprocessing. A changed experiment can
make new provider calls. Budgets are per assessment, including references and both
passes; `plan` reports an upper bound for experiment calls and unknown cost.

ComfyUI API workflows are the configurable generation catalog: node class identifies
the integration, its input schema identifies supported inputs, and `identity`
records provider/model/endpoint separately from the user-facing model label.
Do not assume a workflow's seed/steps field is enforced by a proprietary endpoint.
The current legacy Stability entry is Ultra, matching `StabilityStableImageUltraNode`.
No claim is made that every current image/video model is supported.
