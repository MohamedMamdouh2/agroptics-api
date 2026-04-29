"""
Agroptics API Server (Simplified)
================================
RESTful API for processing satellite imagery and water balance calculations.
Focus: Ease of use, no authentication, local execution.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import requests
import sqlite3
import numpy as np
import json
import uuid
import shutil
import os
from datetime import datetime
from pathlib import Path
from enum import Enum
from typing import Optional
from dotenv import load_dotenv
import logging

# Import processing functions
from Processing.run_all import run_full_pipeline
from Processing.calculate_indices import calculate_all_indices, export_index_geotiff, process_field, load_planet_image

# Load environment
load_dotenv()

# Paths
BASE_PATH = Path(__file__).parent
DATABASE_PATH = BASE_PATH / "api_database.db"
UPLOADS_PATH = BASE_PATH / "api_uploads"
DOWNLOADS_PATH = BASE_PATH / "api_downloads"
EXPORTS_PATH = BASE_PATH / "exports"

for p in [UPLOADS_PATH, DOWNLOADS_PATH, EXPORTS_PATH]:
    p.mkdir(exist_ok=True)

# Logger
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("agroptics_api")

app = FastAPI(title="Agroptics API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            field_name TEXT NOT NULL,
            source_type TEXT,
            source_url TEXT,
            status TEXT,
            progress INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            output_path TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# ============================================================================
# BACKGROUND WORKER
# ============================================================================

def background_process_job(job_id: str, field_name: str, source_type: str, source_url: str):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    try:
        if source_type == 'url':
            download_dir = DOWNLOADS_PATH / job_id
            download_dir.mkdir(parents=True, exist_ok=True)
            
            cursor.execute('UPDATE jobs SET progress = 20 WHERE job_id = ?', (job_id,))
            conn.commit()
            
            if source_url.lower().endswith('.tif') or source_url.lower().endswith('.tiff'):
                # Handle direct GeoTIFF URL
                logger.info(f"Downloading TIF from: {source_url}")
                tif_path = download_dir / "input.tif"
                response = requests.get(source_url, timeout=60, stream=True)
                if response.status_code != 200:
                    raise ValueError(f"Failed to fetch TIF: {response.status_code}")
                
                with open(tif_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                # Extract date from filename if possible (YYYYMMDD format at start)
                filename = os.path.basename(source_url)
                date_str = filename.split('_')[0] if '_' in filename else datetime.now().strftime('%Y%m%d')
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}" if len(date_str) == 8 else date_str
                
                # Load and process
                bands_data = load_planet_image(str(tif_path))
                indices = calculate_all_indices(bands_data)
                metadata = bands_data['metadata']
            else:
                # Handle JSON satellite data response
                response = requests.get(source_url, timeout=30)
                if response.status_code != 200:
                    raise ValueError(f"Failed to fetch JSON: {response.status_code}")
                
                satellite_data = response.json()
                date_str = satellite_data.get('date', datetime.now().strftime('%Y%m%d'))
                formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}" if len(date_str) == 8 else date_str
                
                bands = satellite_data.get('bands', {})
                bands_dict = {
                    'red': np.array(bands.get('red')),
                    'nir': np.array(bands.get('nir')),
                    'green': np.array(bands.get('green', bands.get('nir'))),
                    'rededge': np.array(bands.get('rededge', bands.get('nir')))
                }
                
                indices = calculate_all_indices(bands_dict)
                metadata = satellite_data.get('metadata', {
                    'profile': {'driver': 'GTiff', 'height': bands_dict['red'].shape[0], 'width': bands_dict['red'].shape[1], 
                                'count': 1, 'dtype': 'float32', 'crs': 'EPSG:4326', 'transform': [0.00003, 0, 0, 0, -0.00003, 0]}
                })
            
            export_base = EXPORTS_PATH / field_name / formatted_date
            export_base.mkdir(parents=True, exist_ok=True)
            for name, array in indices.items():
                export_index_geotiff(array, str(export_base / f"{name}.tif"), metadata)
            
        else:
            # Local Source - Check root and Inputs folder
            processing_path = BASE_PATH / field_name
            if not processing_path.exists():
                processing_path = BASE_PATH / "Input" / field_name
            
            if not processing_path.exists():
                raise ValueError(f"Local field '{field_name}' not found in root or Inputs/ folder")
                
            cursor.execute('UPDATE jobs SET progress = 40 WHERE job_id = ?', (job_id,))
            conn.commit()
            process_field(processing_path)
        
        cursor.execute('UPDATE jobs SET progress = 50 WHERE job_id = ?', (job_id,))
        conn.commit()
        
        if run_full_pipeline(target_field=field_name):
            final_output_path = EXPORTS_PATH / field_name
            cursor.execute('''
                UPDATE jobs SET status = ?, progress = 100, completed_at = CURRENT_TIMESTAMP, output_path = ?
                WHERE job_id = ?
            ''', (JobStatus.completed, str(final_output_path), job_id))
            conn.commit()
            
            # CALLBACK: If URL source, zip and send results back to the SAME URL
            if source_type == 'url' and source_url:
                try:
                    logger.info(f"Preparing results for callback to: {source_url}")
                    zip_pkg_dir = DOWNLOADS_PATH / f"pkg_{job_id}"
                    zip_pkg_dir.mkdir(parents=True, exist_ok=True)
                    
                    # 1. Copy GeoTIFFs
                    if final_output_path.exists():
                        shutil.copytree(final_output_path, zip_pkg_dir / field_name, dirs_exist_ok=True)
                    
                    # 2. Copy JSON Reports
                    for suffix in ["_dates.json", "_timeseries.json", "_water_balance.json"]:
                        json_file = EXPORTS_PATH / f"{field_name}{suffix}"
                        if json_file.exists():
                            shutil.copy2(json_file, zip_pkg_dir / json_file.name)
                    
                    # 3. Create Zip
                    zip_path = DOWNLOADS_PATH / f"results_{job_id}"
                    zip_file = shutil.make_archive(str(zip_path), 'zip', zip_pkg_dir)
                    
                    # 4. POST back to the same URL
                    with open(zip_file, 'rb') as f:
                        resp = requests.post(
                            source_url, 
                            files={'file': (f"{field_name}_results.zip", f, 'application/zip')},
                            timeout=60
                        )
                        logger.info(f"Callback response: {resp.status_code}")
                    
                    # Cleanup
                    if os.path.exists(zip_file): os.remove(zip_file)
                    shutil.rmtree(zip_pkg_dir)
                    
                except Exception as cb_err:
                    logger.error(f"Callback failed: {cb_err}")
        else:
            raise ValueError("Pipeline execution failed")
            
    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        cursor.execute('UPDATE jobs SET status = ?, error_message = ? WHERE job_id = ?', (JobStatus.failed, str(e), job_id))
    
    conn.commit()
    conn.close()

# ============================================================================
# ENDPOINTS
# ============================================================================

@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}

@app.post("/api/submit-job")
def submit_job(field_name: Optional[str] = None, source_url: Optional[str] = None):
    if not field_name and not source_url:
        raise HTTPException(400, "Provide field_name or source_url")
    
    job_id = str(uuid.uuid4())
    stype = "url" if source_url else "local"
    fname = field_name or f"url_{uuid.uuid4().hex[:8]}"
    
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO jobs (job_id, field_name, source_type, source_url, status)
        VALUES (?, ?, ?, ?, ?)
    ''', (job_id, fname, stype, source_url, JobStatus.pending))
    conn.commit()
    conn.close()
    
    return {"job_id": job_id, "status": JobStatus.pending}

@app.post("/api/process-job/{job_id}")
def process_job(job_id: str, background_tasks: BackgroundTasks):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT job_id, field_name, source_type, source_url, status FROM jobs WHERE job_id = ?', (job_id,))
    job = cursor.fetchone()
    
    if not job or job[4] != JobStatus.pending:
        conn.close()
        raise HTTPException(400, "Job not found or already processing")
    
    cursor.execute('UPDATE jobs SET status = ?, progress = 5 WHERE job_id = ?', (JobStatus.processing, job_id))
    conn.commit()
    conn.close()
    
    background_tasks.add_task(background_process_job, job[0], job[1], job[2], job[3])
    return {"message": "Processing started", "job_id": job_id}

@app.get("/api/status/{job_id}")
def get_status(job_id: str):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM jobs WHERE job_id = ?', (job_id,))
    job = cursor.fetchone()
    conn.close()
    
    if not job: raise HTTPException(404, "Job not found")
    
    return {
        "job_id": job[0], "field_name": job[1], "status": job[4], 
        "progress": job[5], "error": job[8], "output": job[9]
    }

@app.get("/api/jobs")
def list_jobs():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT job_id, field_name, status, progress FROM jobs ORDER BY created_at DESC LIMIT 50')
    jobs = cursor.fetchall()
    conn.close()
    return [{"job_id": j[0], "field_name": j[1], "status": j[2], "progress": j[3]} for j in jobs]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
