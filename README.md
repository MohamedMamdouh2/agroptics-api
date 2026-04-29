# Agroptics API v1.1.0

A high-performance, modular FastAPI-based REST API for satellite imagery processing and FAO-56 Soil Water Balance (SWB) calculations. Designed for seamless integration with agricultural management platforms.

## 🌟 Key Features
- **Modular Index Calculation**: Supports NDVI, SAVI, FC, GCI, RECI, and MSAVI.
- **Automated Pipeline**: Transition from raw GeoTIFFs to time-series statistics and irrigation requirements in one workflow.
- **Background Tasking**: Non-blocking processing for large datasets.
- **Local & URL Sources**: Support for local field folders and external JSON-formatted satellite data.
- **Dual Processing Paths**: 
    - **Local**: Processes high-resolution Planet 8-band imagery from the `Input/` directory.
    - **URL**: Fetches and processes external satellite data responses.

## 🚀 Installation & Setup

1. **Environment Setup**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Directory Structure**:
   Ensure the following structure is maintained:
   ```text
   AgropticsAPI2/
   ├── Input/                 # Put raw field folders here
   │   └── Field_Test/        # Example field
   │       └── 20250329.../   # Date folder with .tif files
   ├── exports/               # All generated results go here
   ├── Processing/            # Core processing modules
   │   ├── calculate_indices.py
   │   ├── generate_timeseries.py
   │   ├── calculate_water_balance.py
   │   └── Run.py             # Master pipeline logic
   ├── api_server.py          # FastAPI server
   └── requirements.txt
   ```

3. **Running the Server**:
   ```bash
   python api_server.py
   ```
   The server will start at [http://localhost:8000](http://localhost:8000).

## 🔌 API Documentation

### Interactive Docs
Once the server is running, visit:
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Redoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Core Endpoints

| Endpoint | Method | Payload | Description |
|----------|--------|---------|-------------|
| `/api/submit-job` | `POST` | `field_name` | Registers a job for a folder in `Input/` |
| `/api/process-job/{id}`| `POST` | - | Starts background processing for the job |
| `/api/status/{id}` | `GET` | - | Returns progress (0-100%) and final results path |
| `/api/jobs` | `GET` | - | Lists recent job history |

## 🧪 Testing the API (Example)

You can test the API using the provided `Field_Test` data:

1. **Submit Job**:
   ```bash
   curl -X POST "http://localhost:8000/api/submit-job?field_name=Field_Test"
   ```
   *Response*: `{"job_id": "...", "status": "pending"}`

2. **Start Processing**:
   ```bash
   curl -X POST "http://localhost:8000/api/process-job/<JOB_ID>"
   ```

3. **Check Results**:
   ```bash
   curl "http://localhost:8000/api/status/<JOB_ID>"
   ```

## 🛠 Backend Integration Notes

- **Database**: Uses a lightweight `api_database.db` (SQLite) for job tracking.
- **Encoding**: Output logs are sanitized for Windows/Linux cross-compatibility (ASCII-friendly).
- **Extensibility**: 
    - To add new indices, modify `Processing/calculate_indices.py`.
    - To change SWB parameters, update `Processing/cropParameters_updated.json` and `field_config.json`.
- **Error Handling**: Detailed error messages are captured in the job status if a stage fails.

---
**Agroptics Engineering Team** | *Propelling Precision Agriculture*
