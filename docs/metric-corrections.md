# Metric corrections (research schema 1)

The pre-change source is preserved in the sibling baseline archive named in
[the work log](research-work-log.md). The raw historical media and spreadsheets
were not modified. No corrected historical ranking is claimed.

| Confirmed defect | Current behavior | Historical consequence |
|---|---|---|
| Pixel-derived statistics labeled Inception; single-image identity covariance; averaged per-image FID | Pinned pytorch-fid 0.3.0, verified pretrained checkpoint, explicit distinct sets, ≥2 samples each, float64 covariance, exact preprocessing provenance | Stored per-output FID remains raw legacy/invalid, excluded from standard summaries; original reference cache was not recovered |
| Arbitrary automatic CIFAR reference | Deliberate reference membership; incompatible/unknown feature caches rejected | The historical cache's contents are unknown; this does not prove which reference every historical row used |
| Unspecified plural interpreted as exactly one; fire hydrant split/negated | Inspectable presence/minimum/exact/range criteria; compound classes; extras ignored unless explicitly forbidden/exhaustive | Old detector F1 is not prompt correctness; old values remain legacy/custom |
| CLIP failure→0; dropped zero/negative observations | Null failure, retained zero/negative cosine, explicit revision/token count/truncation in research results | Historical averages may have selection/missingness bias |
| Prefix video sampling and too-few-frame perfect scores | Real decoded PTS, whole-clip uniform/window sampling; bounded memory; explicit insufficient data | Old temporal numbers are not validated whole-video measurements |
| Whole-frame DINO labeled subject/background; flow magnitude changes labeled smoothness | Names state whole-frame similarity / flow-magnitude stability; no VBench parity claim | Cannot infer object isolation, natural motion, or overall quality |
| Silent reference truncation/resizing; capped infinite PSNR | Explicit exact alignment assertion, matching PTS/duration/dimensions; identical pixels encode null + positive_infinity | Semantic similarity alone does not justify pixel metrics |
| Aesthetic clipping and fabricated neutral technical scores | Raw predictor output; failed components null; custom heuristics labeled; arbitrary composite disabled | These proxies do not establish aesthetic preference or task success |
| Report default/error values→0; unstable workflow hash | Nullable values/status/reason, finite JSON validation, SHA-256 workflow hashes | Missing historical ratings are not zeros |
| “SD Turbo” label routed to Stability Ultra | Current exposed entry is Stability Ultra; endpoint/workflow and user label are distinct | Historical model identity remains unverified without original endpoint evidence |
| Obsolete contest code downloaded CIFAR and used FID=100 on errors | Contest ranking explicitly disabled; tests assert this refusal | Published combined scores are not reconstructed or validated |

The archived donut example has 47 detected donuts; “a man preparing donuts” does
not specify exactly one donut. The current interpretation requires presence,
with action compliance unsupported by this detector. “A dog sniffs the base of a
fire hydrant” explicitly requests both a dog and a fire hydrant; both presence
criteria can pass, while **sniffing** remains unsupported. These interpretation
regressions use recorded counts/semantics, not a claim that a newly run detector
verified every visual detail.

FID cache identity includes membership, weights checksum, extractor version,
preprocessing, dimension and device. The actual smoke used upstream ImagePathDataset
RGB/ToTensor [0,1], upstream bilinear 299 resize and normalization to [−1,1].
Mixed image sizes use batches of one because upstream stacks before resize.
This verifies the path; it does not assert a constructor normalization bug.
Small-set covariance is mathematically defined with ≥2 distinct samples but highly
biased/unstable. A 2,048-dimensional three-sample self-distance may have tiny
negative numerical error; the public result clamps only numerical negative distance
to zero. Distinct bytes are not necessarily independent generations.

Sources: [pytorch-fid implementation](https://github.com/mseitzer/pytorch-fid),
[TorchMetrics FID definition](https://lightning.ai/docs/torchmetrics/stable/image/frechet_inception_distance.html),
[VBench upstream](https://github.com/Vchitect/VBench), and
[VQAScore upstream](https://github.com/linzhiqiu/t2v_metrics).
