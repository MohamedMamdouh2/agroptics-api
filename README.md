# Agroptics API v1.1.0

A high-performance, modular FastAPI-based REST API for satellite imagery processing and FAO-56 Soil Water Balance (SWB) calculations. Designed for seamless integration with agricultural management platforms.

## 🌟 Key Features
- **Modular Index Calculation**: Supports NDVI, SAVI, FC, GCI, RECI, and MSAVI.
- **Automated Pipeline**: Transition from raw GeoTIFFs to time-series statistics and irrigation requirements in one workflow.
- **Background Tasking**: Non-blocking processing for large datasets.
- **Local & URL Sources**: Support for local field folders and external JSON-formatted satellite data.
- **Dual Processing Paths**: 
    - **Local**: Processes high-resolution Planet 8-band imagery from the project root or `Input/` directory.
    - **URL**: Fetches and processes external satellite data responses or GeoTIFF URLs.

## 🚀 Installation & Setup

1. **Environment Setup**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Directory Structure**:
   The project follows this structure:
   ```text
   AgropticsAPI2/
   ├── api_server.py          # FastAPI server entry point
   ├── Processing/            # Core processing modules
   │   ├── run_all.py         # Master pipeline script
   │   ├── calculate_indices.py
   │   ├── generate_timeseries.py
   │   └── calculate_water_balance.py
   ├── exports/               # Generated GeoTIFFs and JSON reports
   ├── api_uploads/           # Temporary storage for local uploads
   ├── api_downloads/         # Temporary storage for URL downloads
   ├── requirements.txt
   └── .env.example
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

| Endpoint | Method | Params | Description |
|----------|--------|---------|-------------|
| `/api/submit-job` | `POST` | `field_name` or `source_url` | Registers a processing job |
| `/api/process-job/{id}`| `POST` | - | Starts background processing for the job |
| `/api/status/{id}` | `GET` | - | Returns progress (0-100%) and final results path |
| `/api/jobs` | `GET` | - | Lists recent job history |

## 🧪 Testing the API (Example)

### 1. Local Field Processing
If you have a folder named `Field_10` in the root:
```bash
curl -X POST "http://localhost:8000/api/submit-job?field_name=Field_10"
```

### 2. URL-based Processing
```bash
curl -X POST "http://localhost:8000/api/submit-job?source_url=https://example.com/data.tif"
```

## 🛠 Backend Integration Notes

- **Database**: Uses a lightweight `api_database.db` (SQLite) for job tracking.
- **Callback System**: For `url` jobs, the system automatically packages results as a ZIP and POSTs them back to the original `source_url` (if supported).
- **Extensibility**: 
    - To add new indices, modify `Processing/calculate_indices.py`.
    - To change SWB parameters, update `Processing/cropParameters_updated.json`.
- **Error Handling**: Detailed error messages are captured in the job status if a stage fails.

---
**Agroptics Engineering Team** | *Propelling Precision Agriculture*

