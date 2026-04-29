"""
Generate Time Series Statistics from Exported Indices
======================================================
This script reads the exported indices TIF files and generates:
1. Field_X_dates.json - List of dates for each field
2. Field_X_timeseries.json - Complete statistics for each index per date

Based on: Python_Helpers/satellites_optimized.py (statistics calculation)
"""

import os
import json
import numpy as np
import rasterio
from pathlib import Path
from datetime import datetime


def calculate_statistics(data):
    """
    Calculate comprehensive statistics for a raster array.
    Excludes NaN and infinite values from calculations.
    
    Based on: Python_Helpers/satellites_optimized.py safe_mean() pattern
    
    Args:
        data: numpy array of raster values
        
    Returns:
        dict: Statistics including mean, min, max, std, percentiles, count, dimensions
    """
    # Filter out NaN and infinite values
    valid_data = data[np.isfinite(data)]
    
    if len(valid_data) == 0:
        return {
            "mean": 0,
            "min": 0,
            "max": 0,
            "std": 0,
            "p25": 0,
            "p50": 0,
            "p75": 0,
            "count": 0,
            "width": data.shape[1],
            "height": data.shape[0]
        }
    
    # Calculate statistics
    stats = {
        "mean": round(float(np.mean(valid_data)), 4),
        "min": round(float(np.min(valid_data)), 4),
        "max": round(float(np.max(valid_data)), 4),
        "std": round(float(np.std(valid_data)), 4),
        "p25": round(float(np.percentile(valid_data, 25)), 4),
        "p50": round(float(np.percentile(valid_data, 50)), 4),  # median
        "p75": round(float(np.percentile(valid_data, 75)), 4),
        "count": int(len(valid_data)),
        "width": int(data.shape[1]),
        "height": int(data.shape[0])
    }
    
    return stats


def process_field_timeseries(field_name, field_path, exports_base):
    """
    Process all dates for a single field and generate time series statistics.
    
    Args:
        field_name: Name of the field (e.g., "Field_10")
        field_path: Path to the field's export folder
        exports_base: Base exports directory path
        
    Returns:
        tuple: (dates_list, timeseries_data)
    """
    print(f"\n{'='*60}")
    print(f"Processing {field_name}")
    print(f"{'='*60}")
    
    # Get all date folders
    date_folders = sorted([d for d in os.listdir(field_path) 
                          if os.path.isdir(os.path.join(field_path, d))])
    
    print(f"Found {len(date_folders)} dates")
    
    # List of indices to process (from calculate_indices.py)
    indices = ["NDVI", "SAVI", "FC", "GCI", "RECI", "MSAVI"]
    
    dates_list = []
    timeseries_entries = []
    
    for date_folder in date_folders:
        date_path = os.path.join(field_path, date_folder)
        
        # Check if all indices exist
        indices_data = {}
        all_exist = True
        
        for index_name in indices:
            tif_path = os.path.join(date_path, f"{index_name}.tif")
            
            if not os.path.exists(tif_path):
                print(f"  MISSING {index_name} for {date_folder}")
                all_exist = False
                break
            
            try:
                # Read the TIF file and calculate statistics
                with rasterio.open(tif_path) as src:
                    data = src.read(1)  # Read first band
                    stats = calculate_statistics(data)
                    indices_data[index_name] = stats
                    
            except Exception as e:
                print(f"  ERROR reading {index_name} for {date_folder}: {e}")
                all_exist = False
                break
        
        if all_exist:
            dates_list.append(date_folder)
            timeseries_entries.append({
                "date": date_folder,
                "indices": indices_data
            })
            print(f"  OK {date_folder} - {len(indices)} indices processed")
    
    # Create the complete time series structure
    timeseries_data = [{
        "fieldName": field_name,
        "timeSeries": timeseries_entries
    }]
    
    print(f"\nOK {field_name}: {len(dates_list)} dates successfully processed")
    
    return dates_list, timeseries_data


def generate_all_timeseries(exports_dir="exports"):
    """
    Generate time series JSON files for all fields in the exports directory.
    
    Args:
        exports_dir: Path to the exports directory (relative to script location)
    """
    script_dir = Path(__file__).parent.parent
    exports_path = script_dir / exports_dir
    
    if not exports_path.exists():
        print(f"ERROR: Exports directory not found: {exports_path}")
        return
    
    print(f"\n{'='*60}")
    print(f"GENERATING TIME SERIES STATISTICS")
    print(f"{'='*60}")
    print(f"Exports directory: {exports_path}")
    
    # Get all field folders
    field_folders = sorted([f for f in os.listdir(exports_path) 
                           if os.path.isdir(os.path.join(exports_path, f))])
    
    print(f"Found {len(field_folders)} fields: {', '.join(field_folders)}")
    
    summary = {
        "total_fields": len(field_folders),
        "fields_processed": 0,
        "total_dates": 0,
        "fields": []
    }
    
    for field_name in field_folders:
        field_path = os.path.join(exports_path, field_name)
        
        try:
            # Process the field
            dates_list, timeseries_data = process_field_timeseries(
                field_name, field_path, exports_path
            )
            
            # Save dates JSON
            dates_file = exports_path / f"{field_name}_dates.json"
            with open(dates_file, 'w') as f:
                json.dump(dates_list, f, indent=2)
            print(f"  -> Saved: {dates_file.name}")
            
            # Save timeseries JSON
            timeseries_file = exports_path / f"{field_name}_timeseries.json"
            with open(timeseries_file, 'w') as f:
                json.dump(timeseries_data, f, indent=2)
            print(f"  -> Saved: {timeseries_file.name}")
            
            # Update summary
            summary["fields_processed"] += 1
            summary["total_dates"] += len(dates_list)
            summary["fields"].append({
                "field": field_name,
                "dates_count": len(dates_list),
                "date_range": {
                    "start": dates_list[0] if dates_list else None,
                    "end": dates_list[-1] if dates_list else None
                }
            })
            
        except Exception as e:
            print(f"  ERROR processing {field_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Save summary
    summary_file = exports_path / "timeseries_generation_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"TIME SERIES GENERATION COMPLETE")
    print(f"{'='*60}")
    print(f"Fields processed: {summary['fields_processed']}/{summary['total_fields']}")
    print(f"Total dates: {summary['total_dates']}")
    print(f"Summary saved: {summary_file.name}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    generate_all_timeseries()
