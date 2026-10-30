# DreamLayer Eval

A local workbench for reproducible image and video evaluation, with an existing
ComfyUI generation interface. Research workflows are available at `/research`.

Create versioned experiments, import media, inspect metric failures, run configurable
image/frame judges, collect blinded human labels, compare paired observations and
export portable experiment bundles. No particular research question or model ranking
is assumed.

**Platform scope:** the research executor requires POSIX file locking. Use Python
3.11 or 3.12 on Linux/macOS; native Windows execution is unsupported (use WSL2).
Local validation is on Intel macOS. Linux/macOS CI is configured; hosted results
must be checked on the pull request before claiming those platforms passed.

| Capability | Validation status |
|---|---|
| Offline import, metrics, synthetic judges, blinded review, analysis and replay | Tested locally, including real browser workflows |
| CLIP and YOLO | Real CPU inference and offline repeats on synthetic fixture images; revision/weight hashes recorded |
| Inception FID extractor | Previously exercised with real pretrained features; small synthetic inputs do not establish statistical quality |
| Live OpenAI/Anthropic judges | 12 real image judgments passed across the two pinned snapshots, including pointwise/pairwise, cached resume and exact replay; paid failure/retry paths remain unverified |
| ComfyUI | Local procedural image workflow verified through the real server; diffusion/model-based generation remains **unverified** |
| VQAScore, DINO, LPIPS and I3D inference | **Unverified** in this environment |
| Original historical database migration | **Unverified**; only reconstructed-schema fixtures have been exercised |

Start with the [research quickstart](docs/research-quickstart.md). See
[readiness and limitations](docs/research-readiness.md),
[metric corrections](docs/metric-corrections.md), and
[actual validation results](docs/research-validation.md).

```bash
python3.11 -m venv .venv-research
.venv-research/bin/python -m pip install -r requirements-research.lock.txt
.venv-research/bin/python -m research demo
.venv-research/bin/python -m research serve --port 5055
```

In another terminal:

```bash
cd dream_layer_frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 8080
```

Open **http://127.0.0.1:8080/research**. Install FFmpeg/ffprobe separately for video
orientation inspection. Core import, labeling, statistics and the offline fixture
demo do not need neural weights, credentials or ComfyUI. Python 3.11 and 3.12 on Intel
macOS have been validated locally; optional ML environments are separate. The research
package is version **1.1.0**, with record/bundle schema **1**; see the
[compatibility policy](docs/research-schema.md).

The demo includes deliberately corrupt media and a one-frame clip, so it produces
explicit failure/insufficient-data records. These are fixture expectations, not
findings about generation models. Its judge responses are synthetic and labeled.

## Measurement semantics

- FID and I3D Fréchet distance compare **explicit sets**, never individual outputs.
  There is no default CIFAR reference. Historical per-image FID values remain
  legacy/invalid for standard FID and cannot support corrected model rankings.
- CLIP cosine ranges from −1 to 1; it is not the scaled published CLIPScore.
  Closed-vocabulary object criteria cover presence/count, not full prompt fidelity.
- Adjacent pixel stability and whole-frame/flow heuristics are custom measures,
  not VBench implementations, subject/background isolation or overall video quality.
- Errors and unavailable evaluations have null scores and explicit statuses.
  A successful zero remains zero. No overall quality score combines unrelated scales.
- OpenAI and Anthropic adapters use explicit configured models with images and
  timestamped frames. A bounded image smoke passed for the snapshots recorded in
  [live validation](docs/validation/live-smoke.json); video and paid failure/retry
  paths were not exercised. VQAScore's
  pinned dependency requires a newer PyTorch than this Intel Mac supports.
- Human judgments are independent reference assessments. Blinding hides explicit
  model/filename labels but cannot conceal recognizable style or content.

## Existing generation interface

The original interface remains at `/`. Its multiple services and ComfyUI require
the broader dependencies described in [installation](docs/installation.md).
The existing `start_dream_layer.sh` / `start_dream_layer.bat` scripts start those
services. The lightweight research server does not start them.

For controlled research generation, bind an exported ComfyUI API workflow using the
[versioned templates](examples/research-v1/README.md). Provider enforcement of seed,
steps and other settings is unknown unless returned by the provider. Matching seed
integers across providers do not imply matched randomness. Imported historical
model labels are preserved rather than inferred from current endpoint mappings.

Run the offline regression suite with `python tests/run_all_tests.py` in the
validation environment. Frontend checks are `npm run typecheck`, `npm run lint`,
`npm run build`, and `npm test`; browser tests require the local services and demo
fixtures. Exact commands and environment distinctions are in the quickstart.

For contributors, [research development](docs/research-contributing.md) documents
the CI matrix, formatter/linter, package build, reproducible smoke scripts and
public artifact policy. [Statistical methods](docs/research-methods.md) states the
estimands and assumptions behind reported numbers.
