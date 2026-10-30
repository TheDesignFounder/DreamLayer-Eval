# Research quickstart

See [validation](research-validation.md), [methods](research-methods.md), and
[contributor checks](research-contributing.md) for evidence and reproducible commands.

Use Python 3.11 or 3.12 on Linux/macOS; native Windows execution is unsupported.
The checked core lock was installed on Intel macOS 13.1. Node/npm
versions and commands are recorded in [validation](research-validation.md).
Install `ffmpeg`/`ffprobe` separately; FFmpeg 7.1.1 was used for rotation regression.
Core video decoding uses PyAV's bundled FFmpeg. Other platforms remain untested.

## Clean offline setup

From the repository root (quote its path if it contains spaces):

```bash
python3.11 -m venv .venv-research
.venv-research/bin/python -m pip install -r requirements-research.lock.txt
.venv-research/bin/python -m research demo
```

The command creates `.research/fixtures`, imports five planned trials, executes
lightweight metrics and explicitly synthetic judges, then prints the experiment ID
and analysis. Expected counts: five planned, four successful imports, one corrupt
input failure, three successful metric values, and zero human annotations initially.
Image luminance includes valid zero; one-frame temporal stability is insufficient.
VQAScore is unavailable in the core environment. FID lacks a deliberate reference
set. These are meaningful statuses rather than demo failures to suppress.

No credentials, provider calls, optional weight downloads or ComfyUI are needed.
Core logic can be tested with:

```bash
.venv-research/bin/python -m pytest tests/research/test_core.py -q
```

## Local application

```bash
.venv-research/bin/python -m research serve --port 5055
```

In another terminal:

```bash
cd dream_layer_frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 8080
```

Open **http://127.0.0.1:8080/research**. Choose the demo or upload image/video files.
The editor preserves uploaded content identity. Set each asset's prompt, model label
and repeat; click **Preview criteria**, then review/edit them before freezing.
Preview criteria → Create → Dry run → Run/resume.
Inspect status/reason, prompt/media, criteria/provenance and metric definitions.
Cancel stops further scheduling; already submitted provider work may continue.

Create independent assignments with different pseudonymous rater IDs, open blinded
review, inspect complete video/reference evidence and save criteria/uncertainty,
optional aesthetics and failure intervals. The saved assignment list resumes after
reload. Analysis shows missingness, uncertainty, agreement and provider costs when
known. Export includes media by default; Reload bundle verifies its hashes.

## CLI experiments, labeling and replay

```bash
.venv-research/bin/python -m research create examples/research-v1/image-comparison.json
.venv-research/bin/python -m research create examples/research-v1/video-sampling.json
.venv-research/bin/python -m research create examples/research-v1/selection-experiment.json
```

For subsequent commands replace `EXPERIMENT_ID` with the returned ID:

```bash
.venv-research/bin/python -m research plan EXPERIMENT_ID
.venv-research/bin/python -m research run EXPERIMENT_ID --limit 1
.venv-research/bin/python -m research run EXPERIMENT_ID
.venv-research/bin/python -m research analyze EXPERIMENT_ID
.venv-research/bin/python -m research assign EXPERIMENT_ID rater-a examples/research-v1/rubric.json --seed 11
.venv-research/bin/python -m research assign EXPERIMENT_ID rater-b examples/research-v1/rubric.json --seed 12
.venv-research/bin/python -m research labels-export EXPERIMENT_ID .research/labels.jsonl
.venv-research/bin/python -m research export EXPERIMENT_ID .research/experiment.zip
.venv-research/bin/python -m research --db .research/replayed.sqlite3 import .research/experiment.zip
.venv-research/bin/python -m research --db .research/replayed.sqlite3 analyze EXPERIMENT_ID
```

Assignments support `--mode pairwise` for tasks with exactly two candidates,
and `--practice examples/research-v1/practice.json` to mark practice prompts.
`annotate ASSIGNMENT_ID annotation.json` accepts `rater_id`, criterion `labels`,
`intervals`, `comment`, `aesthetic_rating`, `source_references`, and optional
`adjudicates: [original_annotation_id]`. Adjudication appends, never overwrites.
`labels-import` accepts exported JSONL or `--format csv`; assignments must already
exist (restore their bundle first). Invalid/duplicate/orphan annotations fail.

`export --references-only` leaves content-addressed references. Import then requires
`--media-lookup lookup.json`, mapping each SHA-256 to an existing file. Original
filenames are provenance, not file identities. Keep private media in `.research/`.

A saved analysis can be reproduced without re-executing generation/evaluation.
A normal resume retains recorded evaluator versions; use `--upgrade-evaluators`
for explicit reevaluation with supersession. The dry-run and run report version
differences. An upgrade that returns `unavailable_dependency` or `failed_evaluation`
cannot replace a successful prior result. Execution reports a failed job with an
explanation; the affected result and cache remain unchanged. Provision the evaluator
environment or weights, then repeat the explicit upgrade. Completed work on other
units remains saved. Dependency preflight alone cannot detect every loading failure.
`--rerun-failed` alone can use the available evaluator version when
every matched current result for that unit/configuration failed or was unavailable;
it appends a superseding attempt and preserves successful neighboring results.
For legacy duplicate metric IDs, frozen settings and recorded weight information
identify the configuration. If provenance cannot distinguish the configurations,
the affected units remain unchanged with an explicit warning, even with retry or
upgrade flags. This prevents an ambiguous match from silently replacing evidence.
The validation script in `scripts/research_replay_check.py` asserts exact analysis
and cache preservation on a fresh database:

```bash
.venv-research/bin/python scripts/research_replay_check.py .research/research.sqlite3 EXPERIMENT_ID .research/replay-check
```

## Analysis inputs and commands

Use `comparison-rows` and `analysis-input` to export experiment-backed JSON rows
with explicit filters and human-label provenance. Save with `--experiment-id EXPERIMENT_ID --output analysis.json` to
include input values/hash, options and output in the experiment bundle.

```bash
.venv-research/bin/python -m research statistics binary examples/research-v1/binary-decisions.json
.venv-research/bin/python -m research statistics selection examples/research-v1/selection-candidates.json --options '{"selectors":{"proxy":"higher"},"n_values":[1,2,4],"seed":42}'
```

Other operations and inputs:

| Operation | Input and `--options` |
|---|---|
| correlations | `{"x":[...],"y":[...]}`; matching arrays, nulls excluded |
| paired | rows with prompt_id, repeat_index, group_id, model, score; options model_a, model_b, seed |
| bootstrap | rows with group_id and value; options seed, iterations, optional strata field |
| agreement | pairs of nominal rater labels; null means missing |
| threshold | train/development rows with split, score, human; options thresholds array, direction; test labels rejected |

Binary rates print their denominators and coverage. Selection uses identical nested
pools for all selectors and random baseline, retaining missing candidates/scores and
seeded tie handling. Held-out human labels are accessed only after selection. These
operations are not evidence of Goodhart effects or production prevalence.

## Optional neural and live execution

For the validated Intel CPU Inception environment:

```bash
.venv-research/bin/python -m pip install -r requirements-research-ml-intel.txt
.venv-research/bin/python -m research ml-smoke --allow-download
```

The explicit flag permits downloading the public 91 MB Inception checkpoint. Later
runs use its verified checksum. The command uses synthetic images and real neural
features; the tiny sample cannot establish model quality. FID experiments need
explicit generated/reference sets, not per-image scores. Add reference objects
`{"path":"/deliberately/chosen/image.png"}` to config `references` with provenance. An optional `prompt_ids: ["p1", "p2"]` restricts a reference to those tasks for per-asset evaluators, judges and human assignments; omission shares it across tasks. Dataset metrics use the full explicit reference set.

CLIP requires an explicit pinned revision/local model; YOLO requires provisioned
local weights. FVD requires a compatible I3D TorchScript file and checksum. No
unverified checkpoint download is implicit. For VQAScore use a separate compatible
Linux/Apple Silicon environment and `requirements-research-vqa.txt`; its upstream
PyTorch>=2.7 has no Intel Mac wheel. Set `weights_ready: true` only after provisioning,
or explicitly allow its upstream downloads. Its `clip-flant5-xl` checkpoint is
large and its own license/hardware requirements apply. Real inference is unverified.

Live judges need an authorized explicit model/config and `OPENAI_API_KEY` or
`ANTHROPIC_API_KEY` in the environment. The demo never reads them to make calls.
Do a bounded smoke before any study. Configure versioned token prices for usage-based
cost estimates; confirmed billing stays unknown unless supplied by a response.
Adapter request formats follow [OpenAI image inputs](https://developers.openai.com/api/docs/guides/images-vision)
and [Anthropic vision](https://platform.claude.com/docs/en/build-with-claude/vision).
The [contributor workflow](research-contributing.md) includes a separate paid-smoke
runner with a total cost reservation and no automatic retries. Provider examples
in `examples/research-v1/live-openai.json` and `live-anthropic.json` include dated
prices; verify their rates and model access before using them.

Normal resume never repeats a recorded judge request. After inspecting a failed
request, use `retry-judge REQUEST_RECORD_ID --note "reason for another attempt"`
to authorize an additional bounded call, then `run EXPERIMENT_ID`. Unknown delivery
first requires `reconcile-judge REQUEST_RECORD_ID not_delivered --note "evidence"`,
or an explicit `--allow-unknown-delivery` retry acknowledging possible duplicate
provider work. Reconciliation also supports `abandon` or `completed --response
response.json`; use those only when supported by provider evidence. These actions
append audit records and preserve the original request/response.

Generation uses `examples/research-v1/generation.json`: replace workflow path,
actual identity and bindings, then enable `allow_provider_calls` deliberately. Run
local ComfyUI yourself. The research executor preserves request/job IDs and actual
returned metadata. `retry-generation TRIAL_ID` is an explicit new attempt for
reconciled failures; do not use it blindly after an unknown-delivery timeout.

## Historical recovery and full validation

```bash
.venv-research/bin/python -m research recover /path/to/Downloads .research/recovery --limit 5
.venv-research/bin/python -m research recover /path/to/Downloads .research/recovery-full
```

Source spreadsheets/media are read-only. Recovery outputs inventories, all raw rows,
source/tab/row provenance, supported hash+prompt links and conflicts/unresolved
records. Filenames alone never establish identity. Test 1 rankings remain one
unblinded exploratory author; ties/comments are preserved without invented scores.

For the complete legacy + research tests install `requirements-research-legacy.lock.txt`
and `requirements-research-dev.txt` in the core environment, then run
`python tests/run_all_tests.py`. HTTP is blocked
in the default pytest suite; synthetic transports are explicit. The manual legacy
provider diagnostic has a main guard and does not execute during collection.

Frontend validation (servers above running, default demo generated first):

```bash
cd dream_layer_frontend
npm run typecheck
npm run lint
npm run build
npx playwright install chromium
npm test
```

Browser tests use actual Flask/Vite/media/database and synthetic judges, save a
screenshot and exported fixture bundle in a fresh dated directory under
`.research/validation/browser-runs/` (existing directories are rejected). They do not prove
live provider correctness. Portable summaries and remaining limits are recorded in
[validation](research-validation.md).
