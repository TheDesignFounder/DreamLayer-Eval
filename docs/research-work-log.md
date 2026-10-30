# Research implementation work log

Assignment: `handoff.md`, read 2026-10-29. Historical assets are read-only.

Baseline: sibling `DreamLayer-Eval-baseline-2026-10-29.tar.gz`, 822 source files,
SHA-256 `2c4d95244877441f0214a2a653d6bed221e1237b751ef78918f5258f321f812a`.
The archive has no Git metadata. No applicable AGENTS.md was found.
Baseline excludes credentials, weights, databases and environment directories.

Architecture decisions:
- A shared, lightweight `research` Python package, SQLite research tables, Flask
  blueprint and CLI serve the existing React app and legacy compatibility routes.
- Research records are immutable; attempts, scores and adjudications append records.
  Legacy metric values remain preserved with validity metadata.
- Core operation never downloads ML weights or calls providers implicitly.
- Real video decoding uses PyAV (FFmpeg), preserving decoded PTS and aspect ratio.
- Standard FID uses pinned pytorch-fid with explicit image sets and provenance.
- VQAScore is the optional published baseline; provider judges use explicit models.

Progress (update as work completes):
- [x] Read assignment, audit, inventory summary; map active metric paths.
- [x] Recoverable baseline; isolated Python 3.11 environment; npm lockfile install.
- [x] Baseline checks and failures recorded.
- [x] Schema/migrations, identity, import and export.
- [x] Metric corrections, video decoding and published evaluator integration.
- [x] Judge protocols, budgets, resumable execution and generation adapters.
- [x] Human review, historical recovery and statistical analysis.
- [x] API/CLI/UI integration and examples.
- [x] Real-media/model checks, browser workflow, clean replay and final regression.
- [x] Documentation and explicit external limitations.


Final implementation record (2026-10-29 Toronto):
- Added shared research contracts/store/migrations, CLI/API, frozen experiments,
  media identity, bounded PTS sampling, typed statuses, provider claims, execution,
  generation bindings, independent human review, paired/grouped analysis and ZIP replay.
- Corrected all inspected active FID/composition/CLIP/video compatibility paths;
  retired the unsafe contest ranking. Original legacy values remain recoverable.
- Added the React workspace/review screens, readable analysis tables, metric definitions,
  file/bundle import/export and browser automation; repaired baseline frontend errors.
- Checked-in programmatic CC0 fixtures and versioned image/video/selection/generation
  examples; pinned clean core and full legacy-test environments separately from ML.
- Actual validations: 111 tests in both clean and optional-ML environments; 2 browser
  workflows; typecheck/lint/build; 2048D real Inception smoke; exact clean and browser
  bundle replays; all 3 offline templates; full read-only historical recovery.
- Task-specific references are tested through metrics, judges, human review and export.
- Final evidence and exact external limitations: docs/research-validation.md.
  VQAScore inference is externally blocked by Intel PyTorch wheels; live providers,
  optional other neural weights and non-Intel/non-CPU platforms remain unverified.
- No paid research campaign, publish/deploy/push or external messaging was performed.

Important implementation choices:
- Fail closed on unknown paid-call delivery; retain claims through export/import.
- Cache every result/version as immutable provenance; do not replace failures with zero.
- Keep raw historical workbook records and unresolved identities outside source control.
- Bootstrap whole prompt/template groups; separate summaries by model, category and split.
- Explicitly mark synthetic responses/ratings and fixture defects; no scientific claims.
- Use original full video for human review and bounded timestamped frames for judges.

Baseline failures and iterative fixes are documented in docs/research-validation.md.
The final docs link stable final logs; earlier diagnostic logs remain for traceability.
The local API and Vite server remain available on 127.0.0.1:5055 / :8080.
