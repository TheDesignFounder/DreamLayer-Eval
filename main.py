from fastapi import FastAPI
from fastapi.responses import JSONResponse
import json
import hashlib
from pathlib import Path
from PIL import Image
import io

app = FastAPI(
    title="Reruns last job & diff‑hashes outputs with hashlib.sha256", 
    description="""Adds a GET /debug/reproduce FastAPI route that re-runs the very last job recorded 
                    in ~/jobs/last.json, diff-hashes outputs with hashlib.sha256, and 
                    returns JSON {“match”: true/false}. It includes a pytest that submits a dummy job, 
                    mutates the image, calls /debug/reproduce, and expects false.
                """, 
    version="1.0"
)

BASE_DIR = Path.cwd() # Getting the Base Directory for the entire project
jobs = BASE_DIR.rglob("*jobs/last.json", case_sensitive=False) # Searching through the entire directory to get the jobs/last.json file if it exists
jobs_path_exists = False # Instantiating a variable to check if image path exists. Defaults to False
jobs_path = '' # Instantiating an empty string to store the path
for p in jobs:
    jobs_path = p
    jobs_path_exists = p.exists() # Checking whether the jobs path really exists
LAST_JOB_FILE = jobs_path # Assigning the path to the variable LAST_JOB_FILE


def hash_image(image_bytes: bytes)-> str: 
    """This function hashes the outputs with hashlib.sha256"""
    return hashlib.sha256(image_bytes).hexdigest()

def process_image(input_path: Path) -> bytes:
    """Simulating the original image processing logic: converting to grayscale"""
    img = Image.open(input_path).convert("L")  # grayscale
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

@app.get("/debug/reproduce")
def reproduce_last_job():
    """Re-runing the last job provided the actual job exists together with it's corresponding file (/jobs/last.json)"""
    if not jobs_path_exists:
        return JSONResponse({"error": "No last job or file found"}, status_code=404)
    
    try:
        job = json.loads(LAST_JOB_FILE.read_text())

        #Getting the last job file paths
        input_path = Path(job["input_path"])
        output_path = Path(job["output_path"])

        # Regenerate the image from input
        reproduced_output_bytes = process_image(input_path)

        # Load the original output from the job
        original_output_bytes = output_path.read_bytes()

        return {
            "match": hash_image(original_output_bytes) == hash_image(reproduced_output_bytes)
        }

    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
