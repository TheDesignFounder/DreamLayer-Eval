# Report Bundler 

Hi! I'm Rachana.

This is my submission for DreamLayer's Open Source Challenge. (Task #5 - Report Bundle)

Why this Option?
As someone who’s worked on intelligent data pipelines and NLP automation tools, this challenge was a fun way to apply my real world experience into a compact, useful OSS tool.

This task generates a reproducible `report.zip` containing:
- Metadata (`results.csv`)
- Generation config (`config.json`)
- Final grid images
- Schema validation + README

---

## CSV Columns

| Column        | Description                                               |
|---------------|-----------------------------------------------------------|
| image_path    | Relative path to the grid image                           |
| sampler       | Sampling algorithm used                                   |
| steps         | Number of inference steps                                 |
| cfg           | Classifier-Free Guidance scale                            |
| preset        | Style or visual preset used                               |
| seed          | Random seed for deterministic generation                  |
| width         | Grid width in pixels (added for visual clarity)           |
| height        | Grid height in pixels (added for visual clarity)          |
| grid_label    | Custom label for the image (used in overlay or UX tags)   |
| notes         | Any human-readable notes about generation intent          |



The output is deterministic, simple to trace, and easy to integrate into DreamLayer workflows.


## How to Run

```bash
cd report_bundler
python bundler.py
