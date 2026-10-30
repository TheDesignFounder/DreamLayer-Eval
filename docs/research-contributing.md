# Research contributor workflow

Use Python 3.11 or 3.12 on Linux/macOS and Node 22. Windows execution is unsupported
because experiments use POSIX locks; WSL2 is an alternative. Keep model weights,
credentials, private media, databases and raw test outputs out of the public tree.
The `research` wheel contains the core API/CLI; the React workbench and legacy
generation application are run from the source checkout.

## Install and check

```bash
python3.11 -m venv .venv-research
.venv-research/bin/python -m pip install -r requirements-research-legacy.lock.txt -r requirements-research-dev.txt
.venv-research/bin/python -m pip install --no-deps -e .
.venv-research/bin/python scripts/research_test_hygiene.py .venv-research/bin/python .research/checks/run-1
.venv-research/bin/python -m ruff check research tests/research scripts/research_*.py
.venv-research/bin/python -m ruff format --check research tests/research scripts/research_*.py
.venv-research/bin/python scripts/research_public_api_check.py
.venv-research/bin/python scripts/research_public_hygiene.py
.venv-research/bin/python -m build
```

Check the built wheel from an isolated environment, so source imports cannot hide
missing package files:

```bash
python3.11 -m venv .venv-wheel
.venv-wheel/bin/python -m pip install dist/dreamlayer_research-1.1.0-py3-none-any.whl
.venv-wheel/bin/python -I scripts/research_wheel_check.py --directory .research/wheel-new
```

Ruff applies to `research/`, its tests and `scripts/research_*.py`; vendored ComfyUI
and the legacy application have separate conventions. Run `ruff format research tests/research scripts/research_*.py` and
`ruff check research tests/research scripts/research_*.py --fix` before submitting. Optional pre-commit hooks use the same
pinned Ruff version. Public package functions need meaningful docstrings and
parameter/return annotations. The signature check enforces coverage; it is not a
claim of full static type checking for dynamically extensible record payloads.

Tests isolate runtime files and block unexpected HTTP. New behavioral tests should
assert observable semantics, preserve old bundle compatibility and distinguish
actual inference from injected transports. Install the dev requirements for the
scikit-learn and JSON Schema cross-checks. Do not modify historical fixtures to
make a changed implementation pass.

## Browser and portable checks

```bash
cd dream_layer_frontend
npm ci
npm run typecheck
npm run lint
npm run build
npx playwright install chromium
cd ..
.venv-research/bin/python scripts/research_browser_check.py
```

The launcher requires free ports 5057/8082, starts isolated Flask/Vite servers and
stops only its own processes. It requires a fresh `.research/ci-browser-servers`
directory; archive an old run before repeating. Playwright writes to a new dated
directory in `.research/validation/browser-runs/`; `DLE_VALIDATION_DIR` may name
another fresh directory. Existing directories are rejected to preserve evidence.

The GitHub workflow runs the full offline suite on Linux/macOS with both Python
versions, frontend static checks and actual Playwright on Linux. A separate native
Windows job asserts the explicit unsupported-platform message. CI artifacts retain
raw logs briefly; public documentation contains summary JSON only. A configured
workflow is not an executed hosted result: require green checks on the actual PR.

Additional reproducible commands (each output directory must be new):

```bash
python scripts/research_ambiguity_check.py --directory .research/ambiguity-new
python scripts/research_scale_check.py --directory .research/scale-new --trials 2000
python scripts/research_model_smoke.py --directory .research/models-new --allow-download
python scripts/research_comfy_smoke.py --directory .research/comfy-new
```

The model smoke needs the optional ML environment plus `ultralytics==8.3.0`.
It downloads the explicitly pinned public CLIP/YOLO checkpoints and runs CPU
inference on generated shapes. The ComfyUI smoke requires an already running local
instance on 8188 and submits an `EmptyImage` → `SaveImage` graph. It verifies the
real adapter and local server without a diffusion checkpoint or paid node.
Do not run these in default offline CI. Provider and model-based
ComfyUI smokes require independently configured credentials, model access, workflow
and spending limits; they are not implied by passing offline checks.

For an explicitly authorized paid provider smoke, preview the fixed 12-call plan
(four pointwise and two pairwise calls per provider):

```bash
python scripts/research_live_smoke.py --provider both --cap-usd 5
```

Configure `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` in the process environment or an
ignored, permission-restricted `.research/live-smoke.env` file (`python-dotenv` is
included in the legacy development environment). Then execute once in a fresh
directory:

```bash
python scripts/research_live_smoke.py --execute --provider both --cap-usd 5 --directory .research/live-new
```

The guard allows only the two provider endpoints, priced model snapshots and small
fixed inputs. It reserves an estimated upper cost before each request, limits output
tokens, disables retries/redirects and stops after an HTTP or transport failure.
It records usage, estimated cost, order mapping, resume and fresh-database replay.
Unknown delivery retains its reservation. The cap applies to this invocation;
account for earlier runs before authorizing another. This is a conservative token
reservation, not a provider-enforced billing limit. Check the frozen prices against
the linked official pages before executing at a later date. Default CI tests only
the guard and adapters with explicit offline HTTP fixtures.

## Evidence and compatibility

Publish small portable JSON summaries in `docs/validation/`, with commands,
dependency/model versions, hashes, results and limitations. Keep raw logs, HTML,
screenshots, private source data and machine-specific paths in ignored local
storage or CI artifacts. Earlier local evidence is archived without changing its
bytes; public summaries distinguish historical checks from new executions.

Read the [schema policy](research-schema.md) before changing records, caches or
bundle formats, and [methods](research-methods.md) before changing estimators.
Record user-visible behavior and compatibility changes in the changelog.

### Reproduce published smoke summaries

The live summary generator reads a saved smoke directory and blocks all HTTP. It
rechecks record schemas, response usage/costs, pair ordering, fixture expectations,
and fresh-database replay. It requires the core and development dependencies, not
provider credentials. Keep the original run directory intact. For the published
2026-10-30 run, use its recorded verification timestamp to reproduce identical bytes:

```bash
python scripts/research_live_summary.py .research/public-readiness/live-smoke-real-20261030 --verified-at 2026-10-30T07:44:52.673244+00:00 --output .research/reproduced-live-summary.json
```

Omit `--verified-at` for a new verification timestamp. The command needs the original
runner's `result.json`, `spending-reservations.json`, `study.sqlite3`, `experiment.zip`
and four fixture PNGs. The summary's credential-handling statement describes the
historical run; regeneration does not load keys or repeat the original credential scan.

In the optional Torch environment, reproduce preprocessing parity against the
legacy source function without loading I3D weights:

```bash
python scripts/research_fvd_preprocessing_check.py --output .research/reproduced-fvd-preprocessing.json
python scripts/research_fvd_preprocessing_check.py --extended --output .research/fvd-five-shapes.json
```

The default three shapes reproduce `docs/validation/fvd-preprocessing.json` exactly;
`--extended` also checks odd dimensions and a one-frame input. Both generators require
a new output file and refuse to overwrite existing evidence. Neither makes paid calls.
