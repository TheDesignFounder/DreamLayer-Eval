from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from generate_report import run_report

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def read_root():
    html_content = """
    <html>
        <head>
            <title>DreamLayer Report API</title>
        </head>
        <body>
            <h1>Welcome to DreamLayer Report API</h1>
            <p>Use the <code>/generate_report</code> POST endpoint to generate reports.</p>
        </body>
    </html>
    """
    return html_content

@app.post("/generate_report")
async def generate_report_endpoint(frontend_settings: dict = Body(...)):
    try:
        zip_path = run_report(frontend_settings)
        if not os.path.exists(zip_path):
            raise HTTPException(status_code=500, detail=f"{zip_path} not found after generation.")
        return FileResponse(zip_path, filename="report.zip", media_type="application/zip")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
