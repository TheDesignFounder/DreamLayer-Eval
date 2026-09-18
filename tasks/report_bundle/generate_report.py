import os
import json
import csv
import zipfile
from PIL import Image
import torch
import clip
import lpips

RESULTS_FILE = 'results.csv'
CONFIG_FILE = 'config.json'
GRIDS_DIR = 'grids'
README_FILE = 'README.txt'
OUTPUT_ZIP = 'report.zip'

# Load models (once)
device = "cuda" if torch.cuda.is_available() else "cpu"
clip_model, preprocess = clip.load("ViT-B/32", device=device)
lpips_model = lpips.LPIPS(net='alex').to(device)

def compute_scores(prompt, image_path, reference_image_path=None):
    """
    compute clip_score between prompt and image_path,
    compute lpips between image_path and reference_image_path if provided,
    otherwise lpips = 0 (placeholder).
    """
    # open image
    img = Image.open(image_path).convert("RGB")
    image_tensor = preprocess(img).unsqueeze(0).to(device)
    text = clip.tokenize([prompt]).to(device)

    with torch.no_grad():
        image_features = clip_model.encode_image(image_tensor)
        text_features = clip_model.encode_text(text)
        clip_score = torch.cosine_similarity(image_features, text_features).item()

    lpips_score = None
    if reference_image_path and os.path.exists(reference_image_path):
        ref_img = Image.open(reference_image_path).convert("RGB")
        # lpips expects tensors in range [-1,1] as float with shape [1,3,H,W]
        # use lpips helper if available or convert
        from torchvision import transforms
        to_tensor = transforms.ToTensor()
        a = to_tensor(img).unsqueeze(0).mul(2).sub(1).to(device)   # map [0,1] -> [-1,1]
        b = to_tensor(ref_img).unsqueeze(0).mul(2).sub(1).to(device)
        with torch.no_grad():
            lpips_score = float(lpips_model(a, b).item())
    else:
        lpips_score = 0.0  # placeholder if no reference provided

    return round(clip_score, 6), round(lpips_score, 6)


def add_scores_to_csv(results_file):
    """
    Read results.csv, expect columns at least: id, prompt, image_path
    Optional column: reference_image_path (for lpips)
    Writes back clip_score, lpips_score, and adds run_id column.
    """
    rows = []
    with open(results_file, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        fieldnames = list(reader.fieldnames)
        if 'clip_score' not in fieldnames:
            fieldnames.append('clip_score')
        if 'lpips_score' not in fieldnames:
            fieldnames.append('lpips_score')
        if 'run_id' not in fieldnames:
            fieldnames.append('run_id')

        for row in reader:
            img_path = row.get('image_path')
            prompt = row.get('prompt', '')  # لو موجود
            ref_path = row.get('reference_image_path')  # لو موجود
            if not img_path or not os.path.exists(img_path):
                raise FileNotFoundError(f"Image file not found: {img_path}")

            clip_s, lpips_s = compute_scores(prompt, img_path, reference_image_path=ref_path)
            row['clip_score'] = clip_s
            row['lpips_score'] = lpips_s
            # إنشاء run_id من id (مثلاً run_1, run_2, ...)
            row['run_id'] = f"run_{row.get('id', '')}"
            rows.append(row)

    with open(results_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


    with open(results_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def generate_config_from_frontend(config_file, settings_dict):
    """
    settings_dict expected format:
    { "run_id1": { "prompt": "...", "seed": 123, "sampler": "ddim", ... }, ... }
    This function writes config.json from given settings (coming from frontend).
    """
    with open(config_file, 'w', encoding='utf-8') as f:
        json.dump(settings_dict, f, indent=4, ensure_ascii=False)


def create_report_zip(output_zip=OUTPUT_ZIP):
    with zipfile.ZipFile(output_zip, 'w') as zf:
        zf.write(RESULTS_FILE)
        zf.write(CONFIG_FILE)
        zf.write(README_FILE)
        for image_file in os.listdir(GRIDS_DIR):
            full_path = os.path.join(GRIDS_DIR, image_file)
            if os.path.isfile(full_path):
                zf.write(full_path, arcname=os.path.join('grids', image_file))


def run_report(settings_from_frontend):
    """
    Main entrypoint used by the API.
    settings_from_frontend: dict (see generate_config_from_frontend)
    """
    # validations
    if not os.path.exists(RESULTS_FILE):
        raise FileNotFoundError(f"{RESULTS_FILE} not found")
    if not os.path.isdir(GRIDS_DIR):
        raise FileNotFoundError(f"{GRIDS_DIR} not found")
    if not os.path.exists(README_FILE):
        raise FileNotFoundError(f"{README_FILE} not found")

    # 1. compute scores and update CSV
    add_scores_to_csv(RESULTS_FILE)

    # 2. write config.json from frontend settings
    generate_config_from_frontend(CONFIG_FILE, settings_from_frontend)

    # 3. create zip
    create_report_zip()
    return os.path.abspath(OUTPUT_ZIP)  
