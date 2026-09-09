<h1 align="center">DreamLayer Eval: Open-Source Benchmarking for Image and Video Diffusion Models</h1>
<p align="center">
  <strong>Automate prompts, seeds, metrics, and reproducible run logging.</strong><br>
  Built for AI researchers, labs, and developers to evaluate image and video diffusion models faster and compare results consistently.
</p>

<p align="center">
  <b>⭐ Star the repo for updates ⭐</b> 
</p>

<p align="center">
  <b>Product Vision:</b>
  <a href="https://huggingface.co/blog/ytmack7/benchmarking-diffusion-models">AI Research</a>
</p>


![DreamLayer-UI](https://github.com/user-attachments/assets/d2cb7e4c-0194-4413-ac03-998bbb25c903)

---

> **DreamLayer Eval and DreamLayer AI are two different things.** DreamLayer Eval (this repository) is the open-source benchmarking project. [DreamLayer AI](https://dreamlayer.io/) is the image generation and editing platform from the same team, used in the browser and through an [API, CLI, and MCP server](https://dreamlayer.io/agent). Project page: [dreamlayer.io/opensource](https://dreamlayer.io/opensource).

## What is DreamLayer Eval?

DreamLayer Eval is an open-source benchmarking and evaluation platform for image generation models and video generation models. It automates prompts, seeds, metrics, configs, and reproducible run logging so researchers and developers can compare model quality faster and more consistently. It runs locally with a React frontend, Flask-based services, SQLite run storage, and ComfyUI integration for image workflows.

Compare model outputs across prompts, seeds, configs, and metrics with reproducible run logging.

## Who is this for?
DreamLayer Eval is built for:
- **AI researchers** comparing diffusion models across prompts, seeds, and metrics
- **ML Engineers** evaluating image and video generation quality
- **Labs and teams** building internal benchmarking workflows for generative models
- **Open-source model creators** testing checkpoints, LoRAs, and workflows
- **Developers** integrating custom metrics and evaluation pipelines

## What can DreamLayer benchmark?
DreamLayer can benchmark:
- Image generation model outputs
- Video generation model outputs
- Prompt-to-image alignment
- Image quality and aesthetic quality
- Object-level prompt adherence
- Temporal video consistency
- Reference-based image and video similarity metrics

> **Status:** ✨ **Now live**

---

## Quick Start

### ⭐️ Run with Cursor (Smooth Setup with a Few Clicks)

Easiest way to run DreamLayer 😃

1. **Download this repo**
2. **Open the folder in [Cursor](https://www.cursor.so/)** (an AI-native code editor)
3. Type `run it` or press the **"Run"** button — then follow the guided steps

Cursor will:

- Walk you through each setup step
- Install Python and Node dependencies
- Create a virtual environment
- Start the backend and frontend
- Output a **localhost:8080** link you can open in your browser

⏱️ Takes about 5-10 minutes. No terminal needed. Just click, run, and you’re in. 🚀

> On macOS, PyTorch setup may take a few retries. Just keep pressing **Run** when prompted. Cursor will guide you through it.

### Installation

**linux:**

```bash
./install_linux_dependencies.sh
```

**macOS:**

```bash
./install_mac_dependencies.sh
```

**Windows (PowerShell):**

```powershell
# If needed, allow script execution for this session:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\install_windows_dependencies.ps1
```

### Start Application

**linux:**

```bash
./start_dream_layer.sh
```

**macOS:**

```bash
./start_dream_layer.sh
```

**Windows:**

```bash
start_dream_layer.bat
```

### Env Variables

**install_dependencies_linux**
DLVENV_PATH // preferred path to python virtual env. default is /tmp/dlvenv

**start_dream_layer**
DREAMLAYER_COMFYUI_CPU_MODE // if no nvidia drivers available run using CPU only. default is false

### Access

- **Frontend:** http://localhost:8080
- **ComfyUI:** http://localhost:8188

### Installing Models ⭐️

DreamLayer ships without weights to keep the download small. You have two ways to add models:

### a) Closed-source API models

DreamLayer can also call external APIs (OpenAI DALL·E, Flux, Ideogram).

To enable them:

Edit your `.env` file in the repository root (`./.env`):

```bash
OPENAI_API_KEY=sk-...
BFL_API_KEY=flux-...
IDEOGRAM_API_KEY=id-...
STABILITY_API_KEY=sk-...
```

Once a key is present, the model becomes visible in the dropdown.
No key = feature stays hidden.

### b) Open-source checkpoints (offline)

**Step 1:** Download .safetensors or .ckpt files from:

- Hugging Face
- Civitai
- Your own training runs

**Step 2:** Place the models in the appropriate folders (auto-created on first run):

- Checkpoints/ → # full checkpoints (.safetensors)
- Lora/ → # LoRA & LoCon files
- ControlNet/ → # ControlNet models
- VAE/ → # optional VAEs

**Step 3:** Click Settings ▸ Refresh Model List in the UI — the models appear in dropdowns.

> Tip: Use symbolic links if your checkpoints live on another drive.

_The installation scripts will automatically install all dependencies and set up the environment._

### Optional: Download Evaluation Datasets

For FID scoring, download the CIFAR-10 reference dataset:

```bash
python scripts/fetch_datasets.py
```

> **Note:** The YOLO model (`yolov8n.pt`, ~6MB) for object detection metrics auto-downloads on first use.

---

## Why DreamLayer Eval?                                                                                                                              
                                                                                                                                                     
  | 🔍 Feature | 🚀 How it's better |                                                                                                                
  | --- | --- |
  | **Automated Benchmarking** | One run sweeps N prompts by M seeds by K samplers. Metrics compute live during generation, so a 1 to 2 week manual benchmark finishes in 3 to 5 hours per model. |                                                                               
  | **Reproducibility by Default** | Every run persists to SQLite with prompt, negative prompt, seed, sampler, steps, CFG, model hash, LoRA stack, ControlNet config, and all computed metrics. Replay any run by `run_id`. |                                                                         
  | **Image and Video Metrics, Built In** | Image: CLIPScore (ViT-L/14), FID, LAION aesthetic, color harmony, sharpness, YOLOv8 composition F1. Video: FVD (I3D), SSIM, PSNR, LPIPS, temporal flickering, subject and background consistency (DINO), motion smoothness. Custom metrics pluggable. |                    
  | **Multi-Modal Today** | Image and video evaluation are available out of the box. Audio benchmarking is on the roadmap. See the Metrics section below for the exact call graph and storage schema. |                                                                                         
  | **Reference-Free and Reference-Based** | Works without a ground-truth image or video for CLIPScore, aesthetics, YOLO composition, temporal flickering, and DINO consistency. Add a reference video to unlock SSIM, PSNR, LPIPS. FID operates on a reference set. |                            
  | **Cached, Incremental, Comparable** | Metrics persist per run in a dedicated SQLite table and return instantly on re-fetch. Batch backfill endpoints recompute missing metrics across the full history. Compare any two runs side by side via the comparison API. |                           
  | **Researcher-Friendly Exports** | Run locally on your own GPU (CUDA, MPS, or CPU fallback). Export to CSV per run or a ZIP report bundle with images, metadata, and metrics for leaderboard submission or paper appendices. |

---

## Metrics 

DreamLayer supports a working set of common image and video evaluation metrics, including CLIPScore, FID, aesthetic scoring, LPIPS, SSIM, PSNR, composition precision/recall/F1, temporal flickering, subject consistency, background consistency, and motion smoothness. These metrics run either automatically during generation or on demand per run, are exposed through live HTTP routes, and persist to SQLite for reproducible benchmarking and comparison.

### Image metrics
- CLIPScore: prompt-to-image alignment using cosine similarity between CLIP text and image embeddings. Higher is better (0 to 1). No reference needed. Backbone: CLIP ViT-L/14.
- FID (Fréchet Inception Distance): distribution distance between generated images and a reference image set. CIFAR-10 ships as the default reference. Lower is better. Reference required. Backbone: Inception-V3.
- LAION Aesthetic Score: learned aesthetic quality prediction from CLIP embeddings. Higher is better (0 to 10). No reference needed. Backbone: LAION linear predictor on CLIP ViT-L/14.
- Color Harmony, Saturation Balance, Value Contrast: HSV-space color theory analysis using k-means clustering. Higher is better (0 to 1). No reference needed. Backbone: OpenCV.
- Technical Quality: sharpness, noise level, and artifact detection per image. Higher is better (0 to 1). No reference needed. Backbone: Laplacian variance plus heuristics.
- Composition Precision, Recall, F1: object-level prompt adherence, comparing detected objects against a prompt-derived object list. Higher is better (0 to 1). No reference needed. Backbone: YOLOv8n.

### Video metrics
- FVD (Fréchet Video Distance): distribution distance between two sets of videos in I3D feature space. Lower is better. Reference required.
- Video SSIM: per-frame structural similarity, reported as mean and standard deviation across frames. Higher is better (0 to 1). Reference required.
- Video PSNR: per-frame peak signal-to-noise ratio, reported as mean and standard deviation. Higher is better (dB). Reference required.
- Video LPIPS: per-frame learned perceptual similarity between generated and reference frames. Lower is better. Reference required. Backbone: LPIPS with AlexNet.
- Temporal Flickering: frame-to-frame stability using mean absolute error between consecutive frames. Higher is better (0 to 1). No reference needed.
- Subject Consistency: how stable the main subject’s appearance is across frames. Higher is better (0 to 1). No reference needed. Backbone: DINO feature similarity.
- Background Consistency: how stable the background is across frames. Higher is better (0 to 1). No reference needed. Backbone: DINO feature similarity.
- Motion Smoothness: smoothness of optical flow between consecutive frames. Higher is better (0 to 1). No reference needed. Backbone: OpenCV optical flow.
- Per-Frame Aesthetic: LAION aesthetic score applied to each frame, reported as a mean. Higher is better (0 to 10). No reference needed. Backbone: LAION predictor on CLIP ViT-L/14.

_Temporal Flickering, Subject Consistency, Background Consistency, and Motion Smoothness are adapted from [VBench](https://github.com/Vchitect/VBench) (CVPR 2024)._

### When metrics compute
- Live during image generation: CLIPScore, LAION aesthetic, color metrics, technical quality, and YOLO composition. Results are written to the metrics table as soon as the image is saved.
- On demand for images: FID. Requires the CIFAR-10 reference stats (run `python scripts/fetch_datasets.py` once), then a POST /api/runs/calculate-metrics call, or the batch backfill script for historical runs.
- On demand for video: all video metrics. Trigger per video with POST /api/calculate-video-metrics, or batch across all unscored videos with POST /api/calculate-all-video-metrics. Results are cached to the video_metrics table and return instantly on re-fetch.

### Storage and export
Metrics persist across three dedicated SQLite tables:
- metrics: image scalar metrics and aesthetic sub-scores
- composition_metrics: YOLO precision, recall, F1, detected objects, missing objects
- video_metrics: FVD, SSIM, PSNR, LPIPS, plus a JSON blob of per-frame arrays and VBench-style quality metrics

You can export any run or slice of runs to CSV through the report bundle endpoint, or download a ZIP containing images, prompts, configs, and every computed metric for leaderboard submissions or paper appendices.

---

## Requirements

- Python 3.8+
- Node.js 16+
- 8GB+ RAM recommended

---

## Get Involved Today

- **Star** this repository.
- **Share** the screenshot on X ⁄ Twitter with `#DreamLayerAI` to spread the word.

All contributions code, docs, art, tutorials—are welcome!

### Contributing

- Create a PR and follow the evidence requirements in the template.
- See [CHANGELOG Guidelines](docs/CHANGELOG_GUIDELINES.md) for detailed contribution process.

---

## License

DreamLayer Eval is released under the GPL-3.0 license. See [LICENSE](LICENSE).  
All trademarks and closed-source models referenced belong to their respective owners.

## 🧪 Testing

DreamLayer Eval includes a comprehensive test suite covering all functionality including ClipScore integration, database operations, and API endpoints.

### Quick Start Testing

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run all tests
python tests/run_all_tests.py

# Run specific test categories
python tests/run_all_tests.py unit          # Unit tests only
python tests/run_all_tests.py integration  # Integration tests only
python tests/run_all_tests.py api          # API endpoint tests
python tests/run_all_tests.py clipscore    # ClipScore functionality tests

# Run with verbose output
python tests/run_all_tests.py all -v
```

### Test Categories

| Test File | Coverage | Description |
|-----------|----------|-------------|
| `test_txt2img_server.py` | Text-to-Image API | Tests txt2img generation and database integration |
| `test_img2img_server.py` | Image-to-Image API | Tests img2img generation and database integration |
| `test_run_registry.py` | Run Registry API | Tests database-first API with ClipScore retrieval |
| `test_report_bundle.py` | Report Generation | Tests Mac-compatible report bundle creation |
| `test_clip_score.py` | ClipScore Integration | Tests CLIP model calculation and database storage |
| `test_database_integration.py` | Database Operations | Tests 3-table schema and database operations |

### Test Features

- ✅ **Unit Tests** - Individual component testing
- ✅ **Integration Tests** - End-to-end workflow testing  
- ✅ **API Tests** - HTTP endpoint testing with Flask test client
- ✅ **Database Tests** - SQLite operations with temporary test databases
- ✅ **Mock Testing** - External dependency mocking (ComfyUI, CLIP model)
- ✅ **Error Handling** - Edge cases and error condition testing
- ✅ **Mac Compatibility** - ZIP file generation testing

### Running Individual Tests

```bash
# Run specific test file
python -m pytest tests/test_clip_score.py -v

# Run specific test method
python -m pytest tests/test_clip_score.py::TestClipScore::test_clip_score_calculation_with_mock -v

# Run with coverage report
python -m pytest tests/ --cov=dream_layer_backend --cov-report=html
```

### Test Requirements

The test suite requires these additional dependencies:
- `pytest` - Test framework
- `pytest-cov` - Coverage reporting
- `pytest-mock` - Mocking utilities
- `requests-mock` - HTTP request mocking

Install with: `pip install -r tests/requirements.txt`

## FAQ

### Does DreamLayer Eval support CLIPScore, FID, LPIPS, SSIM, and PSNR?
Yes. All five are fully implemented and persisted to SQLite. CLIPScore computes live during image generation. FID runs on demand against a reference image set. Video SSIM, Video PSNR, and Video LPIPS run on demand against a reference video. Batch backfill endpoints recompute missing metrics across the full run history.

### How is DreamLayer Eval different from ComfyUI?
ComfyUI is a node-based generation interface. DreamLayer Eval is a benchmarking workbench built on top of ComfyUI for image workflows, paired with dedicated Flask services for run logging, metric computation, comparison APIs, and CSV or ZIP exports. ComfyUI handles "make this image." DreamLayer Eval handles "benchmark these models across these prompts and seeds, log everything, and let me compare results."

### How is DreamLayer Eval different from Automatic1111, InvokeAI, or Forge?
Automatic1111, InvokeAI, and Forge are excellent generation UIs. DreamLayer Eval is also a great generation UIs, but it adds benchmarking infrastructure on top: persistent SQLite logging with full prompt, seed, sampler, and config metadata; built-in image and video quality metrics; side-by-side run comparison; batch metric backfills; and CSV or ZIP exports for leaderboard submission. None of those generation UIs ship with end-to-end evaluation tooling.

### How is DreamLayer Eval different from VBench, EvalCrafter, and other diffusion evaluation frameworks?
VBench, EvalCrafter, HEIM, and similar evaluation frameworks are standardized benchmark suites: they define fixed prompts, tasks, and scoring methods so you can report comparable benchmark results. DreamLayer Eval is benchmarking infrastructure: you bring your own prompts, models, and configs, then run generation, scoring, run logging, and comparison workflows in one place. The two are complementary. DreamLayer Eval’s evaluation stack also draws on HELM-style benchmarking concepts and includes video quality metrics inspired by VBench, such as temporal flickering, subject consistency, background consistency, and motion smoothness.

### Can I benchmark Stable Diffusion, Flux, DALL·E, Gemini, Runway, Luma, Ideogram, and Stability AI models with DreamLayer Eval?
Yes. DreamLayer Eval can benchmark both local open-source models and supported API-based models. For local workflows, that includes models like Stable Diffusion 1.5, SDXL, Flux, and custom checkpoints. For API-based workflows, DreamLayer Eval supports models shown in the UI such as Luma Labs Photon, Black Forest Labs Flux Pro, OpenAI DALL·E 3, Google Gemini Nano Banana, Runway Gen 4, Ideogram V3, and Stability AI SD Turbo. Add local model files to the Checkpoints/, Lora/, ControlNet/, and VAE/ folders, or add API keys to .env, and supported models appear in the UI for benchmarking.

### Can DreamLayer Eval benchmark text-to-video models like Sora, Runway, Luma, or Veo3?
Yes for Luma AI, Runway ML, and Google's Veo3. DreamLayer Eval integrates with their video APIs out of the box via the `txt2vid_server` — just add the API key to `.env`. Sora support depends on OpenAI exposing a public video generation API. For local open-source video models that run through ComfyUI, drop the checkpoint into the appropriate folder and refresh the model list.

### Can I benchmark outputs across prompts, seeds, and configs?
Yes, this is a core use case. Every run persists to SQLite with the full prompt, negative prompt, seed, sampler, steps, CFG, model hash, LoRA stack, ControlNet config, and all computed metrics. You can replay any run by `run_id`, sweep across multiple seeds or samplers in one batch, and compare any two runs side by side via the comparison API.

### How does DreamLayer Eval calculate CLIPScore?
DreamLayer Eval computes CLIPScore as the cosine similarity between CLIP text and image embeddings using the `openai/clip-vit-large-patch14` backbone. The score lands in the 0 to 1 range, where higher values indicate stronger prompt-to-image alignment. No reference image is needed. CLIPScore computes live during image generation and writes directly to the `metrics` table, surfaced via the run registry API and included in CSV exports.

### How does DreamLayer Eval calculate FID, and which reference dataset does it use?
DreamLayer Eval calculates FID using `torchmetrics.image.fid.FrechetInceptionDistance` with Inception-V3 features at 2048 dimensions. The default reference set is CIFAR-10, which you fetch once with `python scripts/fetch_datasets.py`. Lower FID indicates a closer distributional match to the reference. FID is on-demand: trigger per run via `POST /api/runs/calculate-metrics`, or batch-backfill across historical runs.

### Can I add my own custom metrics?
Yes. The metric pipeline is modular. Each metric is implemented as a standalone calculator in `dream_layer_backend_utils/`, registered with the database layer, and surfaced through the existing `metrics`, `composition_metrics`, or `video_metrics` tables. Add your computation in the same pattern as the existing calculators and register it with the database queries module to flow through the registry, comparison API, CSV export, and ZIP report bundle.

### Does DreamLayer Eval support LoRAs, ControlNets, and custom VAEs?
Yes. Drop `.safetensors` files into the auto-created `Lora/`, `ControlNet/`, and `VAE/` folders, then refresh the model list in Settings. The full stack of active LoRAs (with weights), ControlNet config, and VAE choice persists with every run, so you can replay an exact LoRA and ControlNet combination by `run_id` or compare results across LoRA variants in a single batch.

### Can I sweep across multiple seeds, samplers, and CFG values in one batch?
Yes. A single benchmark run sweeps N prompts across M seeds across K samplers, and you can vary CFG, steps, and resolution per cell. Every cell becomes a row in the `runs` table with its own `run_id` and metrics. The comparison API lets you slice the resulting matrix any way you need: by sampler, by CFG value, by seed, or any combination.

### Does DreamLayer Eval run on Mac?
Yes, on both Intel and Apple Silicon Macs. The install script `./install_mac_dependencies.sh` handles PyTorch and dependency setup on either architecture. On Apple Silicon (M1, M2, M3), DreamLayer Eval uses the MPS (Metal Performance Shaders) backend automatically for GPU-accelerated metric computation. On Intel Macs or when MPS is unavailable, DreamLayer Eval falls back to CPU, which works for every metric but runs slower.

### What is a "run" in DreamLayer Eval, and what gets logged?
A run is one image or video generation event tied to a unique `run_id`. DreamLayer Eval logs the prompt, negative prompt, seed, sampler, steps, CFG, model hash, LoRA stack, ControlNet config, VAE, batch size, generation type (txt2img, img2img, txt2vid, img2vid), the workflow JSON, the output filename, and every metric computed for that output. Runs persist to SQLite indefinitely and can be replayed, exported, or compared at any time.

### How do I reproduce a previous run?
Every run is assigned a `run_id` that links to its full configuration in SQLite: prompt, negative prompt, seed, sampler, steps, CFG, model hash, LoRA stack, and ControlNet config. Replay by `run_id` from the run registry to regenerate the exact image with the exact metrics, or fork a run by changing one parameter (such as the sampler or seed) for a controlled comparison.

### Does DreamLayer Eval send my prompts or images to any server?
No. DreamLayer Eval runs locally on your machine, and prompts, generated images, configs, and metrics stay in your local filesystem and SQLite database by default. The only exception is when you choose to use an API-based model such as DALL·E, Flux, Ideogram, Stability AI, Runway, Luma, or Gemini, in which case the relevant request data is sent to that provider for generation. DreamLayer Eval does not perform telemetry, analytics, or background uploads on its own.

### Can I integrate DreamLayer Eval into a CI/CD pipeline for regression testing?
Yes. Every Flask service exposes HTTP endpoints (txt2img, img2img, video metrics, run registry, report bundle) that you can call from a CI job. A typical pattern: trigger a fixed prompt set against a candidate model, fetch CLIPScore and aesthetic metrics from the run registry, compare against a baseline `run_id` from the previous release, and fail the build if any metric regresses beyond a defined threshold.

### How long does a benchmark run take?
Benchmark runtime depends on the model, hardware, batch size, and selected metrics. In one representative image benchmark, DreamLayer Eval processed 200 prompts in 45 minutes per model on an Intel MacBook Pro across API-based models including Photon, Flux Pro, DALL·E 3, Nano Banana, Runway Gen 4, Ideogram V3, and Stability SD Turbo. Using the same prompts, seeds, and configs across runs, DreamLayer Eval handled generation, scoring, and output aggregation automatically. Larger batches and heavier metrics increase total runtime, but DreamLayer Eval still makes reproducible benchmarking much faster than running the workflow manually.

-----

## ⭐ Founding Supporters

We’re grateful to our earliest supporters who starred the repo and supported us from the start 🚀

<table>
  <tr>
    <td valign="top">@NyayadhishViraj: https://github.com/NyayadhishViraj</td>
    <td valign="top">@yash120394: https://github.com/yash120394</td>
    <td valign="top">@amyzliu: https://github.com/amyzliu</td>
  </tr>
  <tr>
    <td valign="top">@joshiVishrut: https://github.com/joshiVishrut</td>
    <td valign="top">@shreyaspapi: https://github.com/shreyaspapi</td>
    <td valign="top">@vj72: https://github.com/vj72</td>
  </tr>
  <tr>
    <td valign="top">@yashpkm: https://github.com/yashpkm</td>
    <td valign="top">@sauravraiguru: https://github.com/sauravraiguru</td>
    <td valign="top">@krishpat3366: https://github.com/krishpat3366</td>
  </tr>
  <tr>
    <td valign="top">@prmdk: https://github.com/prmdk</td>
    <td valign="top">@pkydev: https://github.com/pkydev</td>
    <td valign="top">@calahoti: https://github.com/calahoti</td>
  </tr>
  <tr>
    <td valign="top">@evangelinensy: https://github.com/evangelinensy</td>
    <td valign="top">@swift9909: https://github.com/swift9909</td>
    <td valign="top">@amit-chhabra-infinitusai: https://github.com/amit-chhabra-infinitusai</td>
  </tr>
  <tr>
    <td valign="top">@chhabraamit: https://github.com/chhabraamit</td>
    <td valign="top">@miraalk: https://github.com/miraalk</td>
    <td valign="top">@BB-2603: https://github.com/BB-2603</td>
  </tr>
  <tr>
    <td valign="top">@brianod: https://github.com/brianod</td>
    <td valign="top">@ParasVc98: https://github.com/ParasVc98</td>
    <td valign="top">@janetxrm: https://github.com/janetxrm</td>
  </tr>
  <tr>
    <td valign="top">@uAreElle: https://github.com/uAreElle</td>
    <td valign="top">@dk1223: https://github.com/dk1223</td>
    <td valign="top">@mathurah: https://github.com/mathurah</td>
  </tr>
  <tr>
    <td valign="top">@rajgopal123: https://github.com/rajgopal123</td>
    <td valign="top">@Akhil9325: https://github.com/Akhil9325</td>
    <td valign="top">@JeseKi: https://github.com/JeseKi</td>
  </tr>
  <tr>
    <td valign="top">@Ggia71: https://github.com/Ggia71</td>
    <td valign="top">@olivermontes: https://github.com/olivermontes</td>
    <td valign="top">@pksrawal: https://github.com/pksrawal</td>
  </tr>
  <tr>
    <td valign="top">@haroldkabiling: https://github.com/haroldkabiling</td>
    <td valign="top">@rajat4064g: https://github.com/rajat4064g</td>
    <td valign="top">@geeknik: https://github.com/geeknik</td>
  </tr>
  <tr>
    <td valign="top">@Jovy550: https://github.com/Jovy550</td>
    <td valign="top">@sru-cyber: https://github.com/sru-cyber</td>
    <td valign="top">@animeshmitra21: https://github.com/animeshmitra21</td>
  </tr>
  <tr>
    <td valign="top">@johannyu: https://github.com/johannyu</td>
    <td valign="top">@arnob-sengupta: https://github.com/arnob-sengupta</td>
    <td valign="top">@florrdv: https://github.com/florrdv</td>
  </tr>
  <tr>
    <td valign="top">@michelle-chiu: https://github.com/michelle-chiu</td>
    <td valign="top">@minseungseon: https://github.com/minseungseon</td>
    <td valign="top">@shraddha55: https://github.com/shraddha55</td>
  </tr>
  <tr>
    <td valign="top">@GozieN: https://github.com/GozieN</td>
    <td valign="top">@heypeppercrunch: https://github.com/heypeppercrunch</td>
    <td valign="top">@SWAYAMK44: https://github.com/SWAYAMK44</td>
  </tr>
  <tr>
    <td valign="top">@IC-Induja: https://github.com/IC-Induja</td>
    <td valign="top">@toluolubode: https://github.com/toluolubode</td>
    <td valign="top">@aliceli-rr: https://github.com/aliceli-rr</td>
  </tr>
  <tr>
    <td valign="top">@MadhuBajaj15: https://github.com/MadhuBajaj15</td>
    <td valign="top">@RupaliLahoti: https://github.com/RupaliLahoti</td>
    <td valign="top">@Pravoli: https://github.com/Pravoli</td>
  </tr>
  <tr>
    <td valign="top">@lhepchabz: https://github.com/lhepchabz</td>
    <td valign="top">@ahad-s: https://github.com/ahad-s</td>
    <td valign="top">@MarcXMe: https://github.com/MarcXMe</td>
  </tr>
  <tr>
    <td valign="top">@shivang710: https://github.com/shivang710</td>
    <td valign="top">@umairinam76: https://github.com/umairinam76</td>
    <td valign="top">@mhmmdihza: https://github.com/mhmmdihza</td>
  </tr>
  <tr>
    <td valign="top">@Cod-cypher: https://github.com/Cod-cypher</td>
    <td valign="top">@Intechlligent1: https://github.com/Intechlligent1</td>
    <td valign="top">@ramadimasatria: https://github.com/ramadimasatria</td>
  </tr>
  <tr>
    <td valign="top">@rajasami156: https://github.com/rajasami156</td>
    <td valign="top">@UmerBaig123: https://github.com/UmerBaig123</td>
    <td valign="top">@MrRStarkey: https://github.com/MrRStarkey</td>
  </tr>
  <tr>
    <td valign="top">@kxhelilaj: https://github.com/kxhelilaj</td>
    <td valign="top">@saadsh15: https://github.com/saadsh15</td>
    <td valign="top">@serdarzuli: https://github.com/serdarzuli</td>
  </tr>
  <tr>
    <td valign="top">@kevinstubbs: https://github.com/kevinstubbs</td>
    <td valign="top">@jakedent: https://github.com/jakedent</td>
    <td valign="top">@iknoorrawal: https://github.com/iknoorrawal</td>
  </tr>
  <tr>
    <td valign="top">@chaowss: https://github.com/chaowss</td>
    <td valign="top">@MGJillaniMughal: https://github.com/MGJillaniMughal</td>
    <td valign="top">@najeebulhassan: https://github.com/najeebulhassan</td>
  </tr>
  <tr>
    <td valign="top">@Mr-MeerMoazzam: https://github.com/Mr-MeerMoazzam</td>
    <td valign="top">@Whitecoolman: https://github.com/Whitecoolman</td>
    <td valign="top">@ChaymaBrk: https://github.com/ChaymaBrk</td>
  </tr>
  <tr>
    <td valign="top">@Wasif-Maqsood: https://github.com/Wasif-Maqsood</td>
    <td valign="top">@Sofstica-Najeeb-Khan: https://github.com/Sofstica-Najeeb-Khan</td>
    <td valign="top">@TahirHameed74: https://github.com/TahirHameed74</td>
  </tr>
  <tr>
    <td valign="top">@micheal0034: https://github.com/micheal0034</td>
    <td valign="top">@Obaid005: https://github.com/Obaid005</td>
    <td valign="top">@Najeeb-Idrees: https://github.com/Najeeb-Idrees</td>
  </tr>
  <tr>
    <td valign="top">@cciliayang: https://github.com/cciliayang</td>
    <td valign="top">@jenniferchen11: https://github.com/jenniferchen11</td>
    <td valign="top">@abuzarmushtaq: https://github.com/abuzarmushtaq</td>
  </tr>
  <tr>
    <td valign="top">@jihad1973: https://github.com/jihad1973</td>
    <td valign="top">@Ponvishnu: https://github.com/Ponvishnu</td>
    <td valign="top">@darkhorse00512: https://github.com/darkhorse00512</td>
  </tr>
  <tr>
    <td valign="top">@birendra027: https://github.com/birendra027</td>
    <td valign="top">@Haziq046: https://github.com/Haziq046</td>
    <td valign="top">@kaivalyagandhi: https://github.com/kaivalyagandhi</td>
  </tr>
  <tr>
    <td valign="top">@avikonduru: https://github.com/avikonduru</td>
    <td valign="top">@sexylasagna: https://github.com/sexylasagna</td>
    <td valign="top">@nk183: https://github.com/nk183</td>
  </tr>
  <tr>
    <td valign="top">@AliMurtaza096: https://github.com/AliMurtaza096</td>
    <td valign="top">@nokid7: https://github.com/nokid7</td>
    <td valign="top">@NjbSyd: https://github.com/NjbSyd</td>
  </tr>
  <tr>
    <td valign="top">@aslirajesh: https://github.com/aslirajesh</td>
    <td valign="top">@cs96ai: https://github.com/cs96ai</td>
    <td valign="top">@ethansbenjamin: https://github.com/ethansbenjamin</td>
  </tr>
  <tr>
    <td valign="top">@alonso130r: https://github.com/alonso130r</td>
    <td valign="top">@Najeebahmed11: https://github.com/Najeebahmed11</td>
    <td valign="top">@surequinn: https://github.com/surequinn</td>
  </tr>
  <tr>
    <td valign="top">@crispychili: https://github.com/crispychili</td>
    <td valign="top">@scchang-catherine: https://github.com/scchang-catherine</td>
    <td valign="top">@alimurtaza-idrak: https://github.com/alimurtaza-idrak</td>
  </tr>
  <tr>
    <td valign="top">@karanbalaji: https://github.com/karanbalaji</td>
    <td valign="top">@Husnain306: https://github.com/Husnain306</td>
    <td valign="top">@upadhyaykshiti: https://github.com/upadhyaykshiti</td>
  </tr>
  <tr>
    <td valign="top">@YoussefZayed: https://github.com/YoussefZayed</td>
    <td valign="top">@Kblack0610: https://github.com/Kblack0610</td>
    <td valign="top">@yousheng44: https://github.com/yousheng44</td>
  </tr>
  <tr>
    <td valign="top">@harrishanlogan: https://github.com/harrishanlogan</td>
    <td valign="top">@kfj001: https://github.com/kfj001</td>
    <td valign="top">@mananomartinez: https://github.com/mananomartinez</td>
  </tr>
  <tr>
    <td valign="top">@pr0mila: https://github.com/pr0mila</td>
    <td valign="top">@anshit-chaudhari: https://github.com/anshit-chaudhari</td>
    <td valign="top">@srinijammula: https://github.com/srinijammula</td>
  </tr>
  <tr>
    <td valign="top">@Austincain1006: https://github.com/Austincain1006</td>
    <td valign="top">@VThejas: https://github.com/VThejas</td>
    <td valign="top">@garvitalwar: https://github.com/garvitalwar</td>
  </tr>
  <tr>
    <td valign="top">@Gao-Yang-cpu: https://github.com/Gao-Yang-cpu</td>
    <td valign="top">@swisherrr: https://github.com/swisherrr</td>
    <td valign="top">@Malavya-Raval: https://github.com/Malavya-Raval</td>
  </tr>
  <tr>
    <td valign="top">@TedDBear: https://github.com/TedDBear</td>
    <td valign="top">@aniahb101: https://github.com/aniahb101</td>
    <td valign="top">@NisargKotak: https://github.com/NisargKotak</td>
  </tr>
  <tr>
    <td valign="top">@pratik-31: https://github.com/pratik-31</td>
    <td valign="top">@ivankitanovski: https://github.com/ivankitanovski</td>
    <td valign="top">@aliya-khalil21: https://github.com/aliya-khalil21</td>
  </tr>
  <tr>
    <td valign="top">@Shubham91999: https://github.com/Shubham91999</td>
    <td valign="top">@Kohink: https://github.com/Kohink</td>
    <td valign="top">@ajinkya-rasane: https://github.com/ajinkya-rasane</td>
  </tr>
  <tr>
    <td valign="top">@TLSZS0418: https://github.com/TLSZS0418</td>
    <td valign="top">@fan70m: https://github.com/fan70m</td>
    <td valign="top">@az-rye: https://github.com/az-rye</td>
  </tr>
  <tr>
    <td valign="top">@akshay-SE-Maldev: https://github.com/akshay-SE-Maldev</td>
    <td valign="top">@Mickey9315: https://github.com/Mickey9315</td>
    <td valign="top">@juiceomilk: https://github.com/juiceomilk</td>
  </tr>
  <tr>
    <td valign="top">@madhavramini: https://github.com/madhavramini</td>
    <td valign="top">@AviralYO: https://github.com/AviralYO</td>
    <td valign="top">@devanshi-ptk: https://github.com/devanshi-ptk</td>
  </tr>
  <tr>
    <td valign="top">@srimur: https://github.com/srimur</td>
    <td valign="top">@shivamkhare95: https://github.com/shivamkhare95</td>
    <td valign="top">@Mgiri1234: https://github.com/Mgiri1234</td>
  </tr>
  <tr>
    <td valign="top">@shreyyyansh: https://github.com/shreyyyansh</td>
    <td valign="top">@Kreed22: https://github.com/Kreed22</td>
    <td valign="top">@nidhikhatri18: https://github.com/nidhikhatri18</td>
  </tr>
  <tr>
    <td valign="top">@divyaprakash0426: https://github.com/divyaprakash0426</td>
    <td valign="top">@himangi05: https://github.com/himangi05</td>
    <td valign="top">@carynn101: https://github.com/carynn101</td>
  </tr>
  <tr>
    <td valign="top">@TeamBuilderApp: https://github.com/TeamBuilderApp</td>
    <td valign="top">@NainAbdi: https://github.com/NainAbdi</td>
    <td valign="top">@Nishkarsh1606: https://github.com/Nishkarsh1606</td>
  </tr>
  <tr>
    <td valign="top">@bendemonium: https://github.com/bendemonium</td>
    <td valign="top">@tonyshi1111: https://github.com/tonyshi1111</td>
    <td valign="top">@Naranja-Sagged: https://github.com/Naranja-Sagged</td>
  </tr>
  <tr>
    <td valign="top">@Jairo-Morelli: https://github.com/Jairo-Morelli</td>
    <td valign="top">@Mickey105: https://github.com/Mickey105</td>
    <td valign="top">@alfsiezar: https://github.com/alfsiezar</td>
  </tr>
  <tr>
    <td valign="top">@abdulrehan1729: https://github.com/abdulrehan1729</td>
    <td valign="top">@ISubomi: https://github.com/ISubomi</td>
    <td valign="top">@BhavanaPolakala: https://github.com/BhavanaPolakala</td>
  </tr>
  <tr>
    <td valign="top">@jack-makers: https://github.com/jack-makers</td>
    <td valign="top">@pavansurya09: https://github.com/pavansurya09</td>
    <td valign="top">@PrithhviSunil: https://github.com/PrithhviSunil</td>
  </tr>
  <tr>
    <td valign="top">@shriakhilc: https://github.com/shriakhilc</td>
    <td valign="top">@Ankith1999: https://github.com/Ankith1999</td>
    <td valign="top">@Emenlentino: https://github.com/Emenlentino</td>
  </tr>
  <tr>
    <td valign="top">@zaynnqureshi17: https://github.com/zaynnqureshi17</td>
    <td valign="top">@Ashish-3000: https://github.com/Ashish-3000</td>
    <td valign="top">@wavegate: https://github.com/wavegate</td>
  </tr>
  <tr>
    <td valign="top">@richexplorer: https://github.com/richexplorer</td>
    <td valign="top">@keeansarani: https://github.com/keeansarani</td>
    <td valign="top">@Mustafaahmed00: https://github.com/Mustafaahmed00</td>
  </tr>
  <tr>
    <td valign="top">@almzayyen: https://github.com/almzayyen</td>
    <td valign="top">@derickmr: https://github.com/derickmr</td>
    <td valign="top">@gastondana627: https://github.com/gastondana627</td>
  </tr>
</table>


