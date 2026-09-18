# test_debug_reproduce.py
import pytest
from fastapi.testclient import TestClient
from main import app, process_image, jobs_path_exists
from PIL import Image, ImageDraw
import shutil
import json
from pathlib import Path

client = TestClient(app)

@pytest.fixture
def setup_job(tmp_path):
    JOBS_DIR = Path("jobs")
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    LAST_JOB_FILE = JOBS_DIR / "last.json"

    input_image = tmp_path / "input.png"
    output_image = tmp_path / "output.png"

    # Create input image (blue square)
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(input_image)

    # Simulate original job: grayscale
    output_bytes = process_image(input_image)
    with open(output_image, "wb") as f:
        f.write(output_bytes)

    # Save last job record
    LAST_JOB_FILE.write_text(json.dumps({
        "input_path": str(input_image),
        "output_path": str(output_image),
    }))

    # Mutate output image to cause mismatch
    mutated_img = Image.open(output_image).convert("RGB")
    draw = ImageDraw.Draw(mutated_img)
    draw.rectangle([10, 10, 30, 30], fill="red")
    mutated_img.save(output_image)

    yield

    shutil.rmtree(JOBS_DIR, ignore_errors=True)

def test_reproduce_detects_mismatch(setup_job):
    response = client.get("/debug/reproduce")
    if not jobs_path_exists:
        assert response.status_code == 404
        assert response.json()["error"] == "No last job or file found"
    else:
        assert response.status_code == 200
        assert response.json()["match"] is False
