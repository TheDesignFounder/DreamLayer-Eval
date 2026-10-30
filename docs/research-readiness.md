# Research readiness

See [validation](research-validation.md), [statistical methods](research-methods.md)
and the [schema/migration policy](research-schema.md).

The validated scope is the local import/evaluate/review/analyze/export workflow.
Real pretrained Inception extraction and CLIP/YOLO smoke inference were exercised on CPU.
A real local ComfyUI procedural image graph exercised the generation adapter, but
model-based generation, VQAScore inference and optional video neural metrics are not
validated on this machine. Both provider judge adapters passed a bounded real image
smoke with pinned models, pointwise/pairwise calls and exact replay. Live video,
retry and reconciliation failure paths remain unverified. See [actual evidence](research-validation.md).

## Architecture and contracts

`research/` is shared by `python -m research`, a Flask blueprint at `/api/research`,
and the existing React application (`/research` and `/research/review`). The main
legacy image API also registers the blueprint. The lightweight standalone API
runs independently of the legacy generation services and optional ML packages.
SQLite stores immutable JSON records in research tables, plus transactional job,
cache and request-claim tables. No external database is required.

Schema version 1 has experiment, prompt, trial, attempt, asset, result, judge_call,
assignment, annotation, analysis, judge_reconciliation, historical_ranking and legacy records. Configuration is frozen and
SHA-256 hashed. File paths locate content; SHA-256 identifies it. Same-name/different
bytes are separate assets; repeated bytes are reported and excluded from distinct
set membership. Parent/derived assets must share independent group and split.
Prompt families cannot cross train/development/test/exploratory splits. Imported
runs default to exploratory; retrospective work is not preregistered by implication.

Results record evaluator/version, image/video/criterion/pair/dataset scope,
membership/reference/preprocessing identity, weights, units/direction, raw details,
time and status. Statuses are `success`, `not_applicable`, `insufficient_data`,
`unavailable_dependency`, `failed_evaluation`, `abstention`, `invalid_legacy_result`.
Unsuccessful scores are null with reasons; successful zero is retained. JSON NaN
and Infinity are rejected. Identical aligned videos use null score with
`special_value: positive_infinity`. Provider cost is null when unknown, never $0.

Migration makes a SQLite backup before adding research tables to an existing DB,
snapshots original legacy rows with validity metadata, and is idempotent. Original
FID cells are retained; compatibility reads expose them as `legacy_fid_score` and
return null for standard per-output FID. New results never overwrite old records.
Old composition/quality summaries are unvalidated custom measurements.

## Evaluators

| ID | Scope / reference | Interpretation / availability |
|---|---|---|
| pixel_luminance | image / none | Mean sRGB intensity [0,1]; descriptive, not quality; core |
| clip_cosine | image / none | CLIP cosine [−1,1]; explicit model revision, 77-token truncation recorded; optional torch/transformers/weights |
| object_criteria | criterion / none | Local YOLO closed-vocabulary count/presence; researcher-editable criteria, optional extras rule; explicit weights required |
| vqascore | image / none | Published upstream VQAScore [0,1], `VQAScore(images=..., texts=...)`; optional dedicated environment |
| adjacent_pixel_stability | video / none | Custom 1−adjacent RGB MAE/255; full clip or explicit contiguous window, ≤4,096 pairs; frozen clips score 1 by definition |
| aligned_psnr | video / aligned video | Sampled pooled pixel MSE, dB; explicit `exact_pts_pixels`; equal duration/PTS/resolution |
| fid | dataset / image set | pytorch-fid 0.3.0, 2,048D pretrained Inception, two explicit distinct sets |
| fvd | dataset / video set | Explicit hash-verified local I3D TorchScript; named custom preprocessing variant, no upstream benchmark parity claim |

Legacy color/technical and video flow/whole-frame helpers are compatibility
features with custom names. They are not a standard benchmark registry extension.
No score combines these scales into overall quality. Audio is metadata only.
No audio or audiovisual quality evaluator is implemented.

Video inspection uses PyAV/FFmpeg decoded presentation timestamps. Sampling keeps
one frame at a time during inspection and up to the configured 256 selected frames,
at most 2,048 pixels per side. It preserves aspect ratio and records RGB/orientation
transforms. Uniform sampling spans the whole clip; windows use consecutive source
observations. Sparse observations can miss brief events; this is an explicit
protocol limitation, not a solved detection problem. ffprobe is required for
rotation metadata. Browser playback depends on codec support; original evidence
remains available for a compatible player. Test fixtures use VP9/WebM.

## Judges, execution and humans

OpenAI Responses and Anthropic Messages adapters send actual PNG image inputs and
timestamped frames, optionally task-specific references (`references[].prompt_ids`). They require explicit model IDs. The
saved evidence identifies exactly what each call saw. Sparse, dense and uncertain
second-pass modes have total per-assessment call/frame/token-reservation budgets.
Token reservations are deliberately conservative upper bounds based on bytes;
provider usage is saved separately. Budgets include references and all passes.
Bounded automatic retries cover 429/529 rejections and connection-establishment timeouts.
Ambiguous delivery retains the claim and requires explicit reconciliation or an
audited retry that accepts possible duplicate delivery. See `retry-judge` and
`reconcile-judge` in the quickstart. Increasing a budget
can resume a direct protocol without repeating completed rounds. A changed frozen
experiment config creates a new experiment and may intentionally create new calls.
Synthetic responses are labeled; adversarial text fixtures do not prove prompt
injection resistance in real models.

Trial execution uses stable order, ≤8 workers, process/thread exclusion, a configurable
global interval between trial starts, durable progress and cancellation. This is not
a provider-wide requests-per-minute quota controller. A multi-pass trial may make
multiple requests. Generation supports local ComfyUI API workflows with explicit
parameter bindings; submission records distinguish requested/submitted/supported,
unsupported and unverified settings. Provider-accepted values remain empty unless
proven. A job ID resumes polling; a timeout does not automatically resubmit work.
Local cancellation cannot revoke a provider's already queued generation.

Blinded review hides provider/model/filename presentation and image metadata,
randomizes saved assignments, plays full video, and preserves rater ID, rubric,
criterion labels, intervals, comments, optional ordinal aesthetics and references.
Two raters retain independent labels. Adjudication appends a separate record and
the adjudicated analysis overlays affected units while preserving other raw labels.
Historical duplicate rater units select the latest record with an explicit warning.
Practice/attention examples can be marked by source prompt or asset IDs through
`assign`'s API `practice` list and are **not silently excluded** from analysis.
This is a trusted local researcher tool, not a secured multiuser crowdsourcing site.
Researchers who access the database can recover identity mappings.

## Analysis and export

Analysis separates scopes and evaluator versions/settings, reports denominators,
missingness, group-bootstrap uncertainty, raw/adjudicated rater agreement and
provider latency/error/cost. Analyze also joins experiment metrics, judges and humans
by asset identity, rubric, criterion and rater. `analysis-input` exports reviewed
inputs for advanced statistics without manual JSONL joins. Advanced CLI operations include paired model
differences, tied Spearman/Kendall, nominal Cohen kappa, explicit false-acceptance
and false-discovery denominators, development-only threshold fitting and best-of-N
selection with shared nested candidate pools, seeded ties and random baseline.
Bootstrap units are independent prompt/template groups, retaining repeats within
groups; the estimand is an observation-weighted mean. Single-group intervals,
constant correlations and no-label estimates are null. No mixed/rater random-effects
model is claimed. Selected model sets do not justify inference to every model.

Bundles include JSONL records, null/status-preserving CSV, frozen workflows/settings,
raw/parsed outputs, labels and analysis records, code/dependency provenance, a hash
manifest, and optional media. Import validates archive paths, membership/hashes,
size, duplicates and references. Reference-only bundles require a SHA-to-file lookup.
Analysis can rerun without any model or provider calls. Private archives and local
state are excluded from version control. Do not distribute a bundle containing
private study data without reviewing its contents.

VQAScore code is pinned to upstream commit
`6ecb74f92028f42c7e64546d3a71e98c8c73068f` (Apache-2.0); checkpoint licenses vary.
Its actual upstream callable is wired into evaluation, but installation is blocked
on Intel macOS by upstream `torch>=2.7.0`; available wheels stop at 2.2.2. Provision
and validate it in a compatible separate environment before treating it as verified.
FID upstream is Apache-2.0. Optional detector/model licenses must be reviewed for
one's chosen weights. No implicit ML weight download occurs in core execution.
