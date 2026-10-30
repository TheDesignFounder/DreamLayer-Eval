# Research records, bundles and compatibility

The research package uses semantic version **1.1.0**. Its exported record schema
and bundle manifest schema remain **1**. SQLite migration version is **2**.
These are separate version axes; evaluator descriptors retain their own versions.

## Frozen schema 1

- [Record JSON Schema](../research/schemas/record-v1.json): common record envelope,
  kind-specific required fields, statuses, scopes and score/missingness rules.
- [Bundle manifest JSON Schema](../research/schemas/bundle-v1.json): schema version,
  experiment ID and SHA-256 for every archived file.

Both use JSON Schema draft 2020-12 and are shipped inside the Python package.
Records contain `schema_version`, stable string `id`, `kind`, nullable
`experiment_id`, UTC `created_at` and kind-specific payload. Extra fields are
allowed so schema-1 records can gain optional provenance without rewriting old
evidence. JSON objects are dynamically extensible in the Python API; public
functions carry type hints and docstrings, while runtime contracts enforce
semantic validity. A `py.typed` marker exposes those annotations to callers.

| Kind | Meaning |
|---|---|
| experiment, prompt, trial | Frozen configuration, reviewed task/criteria, planned model/repeat unit |
| attempt, asset | Generation/import history and content-addressed source/derived media |
| result | Scoped evaluator/version/settings observation with explicit status and nullable score |
| judge_call, judge_reconciliation | Request/response provenance, budgets, ordering, delivery state and operator recovery |
| assignment, annotation | Blinded task presentation, independent rater labels or explicit adjudication |
| analysis | Frozen analysis input/options and output |
| historical_ranking, legacy | Imported historical evidence and explicitly unverified legacy measurements |

Canonical JSON uses sorted keys, compact separators, UTF-8 and no NaN/Infinity.
Content/configuration hashes use SHA-256. Dataset membership is order-independent
and rejects repeated bytes as distinct samples. Zero is a valid score; failure
requires null and a reason. Positive infinite aligned PSNR is encoded with a null
score and the explicit `positive_infinity` marker.

A bundle contains `records.jsonl`, `results.csv`, `provenance.json`, `manifest.json`
and optional `media/` members. Provenance records package/code/dependency versions.
Reference-only assets use `sha256:` locators and require a hash-to-file mapping
at import. Media paths are locators, not identities. Bundles preserve immutable
payloads, so study configurations/comments must be reviewed for private paths or
sensitive content before distribution; arbitrary user payloads are not anonymized
by a manifest. Credential-like fields are redacted at record creation/export.

Schema validation is necessary but not sufficient. Import also rejects unsafe
archive paths, duplicate members/IDs, hash or config mismatches, cross-experiment
references, orphan references, and archives over the configured uncompressed size
limit. It restores caches/claims without issuing provider calls. Schema-1 bundles
from package 1.0.0 remain supported; the immutable legacy fixture tests this path.

## Migration and version policy

1. Never change a schema-1 required field's meaning or remove it. Add optional
   provenance compatibly in a minor release. Breaking record/bundle changes need
   a new schema version, an explicit importer/migration, fixtures and a major
   package release. Unknown schema versions are rejected, never guessed.
2. Evaluator behavior/identity changes require an evaluator descriptor version
   change. Plain resume preserves old versions and warns. Explicit upgrades append
   superseding records. `--rerun-failed` may use the available version only when
   every matched current result for that unit failed or was unavailable.
3. Ambiguous legacy configuration matches preserve affected units and warn,
   including under explicit retry/upgrade. Preserve source provenance or create
   a separate experiment; do not attach old scores to a guessed configuration.
4. SQLite migrations are additive and idempotent. Migration 1 backs up a pre-research
   database and retains legacy values with validity metadata. Migration 2 adds
   expression indexes for protocol, unit and reference lookups; it does not rewrite
   record JSON, IDs or hashes. Back up a study database before changing package
   versions. Copying a live SQLite file is not a safe backup procedure; use SQLite's
   backup API or stop its writers first.

Original historical-database migration remains unverified. Tests exercise
reconstructed schemas, backup/idempotence and unchanged payload hashes across the
index migration. Successful fixture migration is not a substitute for validating
an actual study backup.
