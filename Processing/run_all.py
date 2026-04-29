"""
Master Script - Run All Processing Steps Sequentially
======================================================
This script runs the complete processing pipeline:
1. Calculate vegetation indices from satellite imagery
2. Generate time series statistics
3. Calculate water balance parameters

Usage:
    python run_all.py [field_path]
    
Example:
    python run_all.py Field_10
"""

import sys
import time
from pathlib import Path
from Processing.calculate_indices import process_field, load_planet_image, calculate_all_indices, export_index_geotiff
from Processing.generate_timeseries import generate_all_timeseries
from Processing.calculate_water_balance import process_all_fields


def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def run_full_pipeline(target_field=None):
    """
    Run the complete processing pipeline.
    
    Args:
        target_field: Path or name of the field to process. If None, uses default.
        
    Returns:
        bool: True if successful, False otherwise
    """
    start_time = time.time()
    
    print_header("COMPLETE PROCESSING PIPELINE")
    print("This script will run:")
    print("  1. Calculate Indices (vegetation indices from satellite imagery)")
    print("  2. Generate Time Series (statistics from indices)")
    print("  3. Calculate Water Balance (FAO-56 water balance model)")
    print()
    
    # Get field path
    script_dir = Path(__file__).parent
    if target_field:
        field_path = target_field
    else:
        # Default: process Field_10
        field_path = script_dir / 'Field_10'
        
    is_url = str(field_path).startswith('http://') or str(field_path).startswith('https://')
    
    if is_url:
        field_name = "url_field"
        print(f"Processing URL: {field_path}")
    else:
        # Check if it's a path or just a name
        if Path(field_path).exists():
            field_name = Path(field_path).name
        else:
            # Maybe it's just a field name and indices already exist?
            field_name = str(field_path)
            export_dir = script_dir.parent / "exports" / field_name
            print(f"Checking for existing indices in: {export_dir}")
            indices_exist = False
            if export_dir.exists():
                print(f"Export directory exists: {export_dir}")
                for date_folder in export_dir.iterdir():
                    print(f"Checking date folder: {date_folder}")
                    if date_folder.is_dir() and (date_folder / "NDVI.tif").exists():
                        print(f"Found NDVI.tif in {date_folder}")
                        indices_exist = True
                        break
            else:
                print(f"Export directory does NOT exist: {export_dir}")
            
            if not indices_exist:
                print(f"ERROR: Field path does not exist and no existing indices found for: {field_path}")
                return False
        
        print(f"Processing field: {field_name}")
        print(f"Field path/name: {field_path}")
    
    # ========================================================================
    # STEP 1: Calculate Vegetation Indices
    # ========================================================================
    # Check if indices already exist (e.g. from API manual calculation)
    export_dir = script_dir.parent / "exports" / field_name
    existing_indices = False
    if export_dir.exists():
        # Check if any date subfolder has indices
        for date_folder in export_dir.iterdir():
            if date_folder.is_dir() and (date_folder / "NDVI.tif").exists():
                existing_indices = True
                break
    
    print_header("STEP 1/3: CALCULATING VEGETATION INDICES")
    step1_start = time.time()
    
    try:
        if existing_indices:
            print(f"Indices already exist in {export_dir}. Skipping Step 1.")
            summary = {'success': 1, 'total': 1, 'errors': 0}
        elif is_url:
            import requests, os
            from datetime import datetime
            
            print(f"Downloading from {field_path}...")
            response = requests.get(str(field_path), stream=True)
            if response.status_code != 200:
                raise ValueError(f"Failed to download: {response.status_code}")
                
            script_dir = Path(__file__).parent
            temp_dir = script_dir / "temp_downloads"
            temp_dir.mkdir(exist_ok=True)
            filename = str(field_path).split('/')[-1]
            temp_path = temp_dir / filename
            
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)
            
            # Extract date from filename if possible
            date_str = filename.split('_')[0] if '_' in filename else datetime.now().strftime('%Y%m%d')
            formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}" if len(date_str) >= 8 else date_str
            
            print("Calculating indices...")
            bands_data = load_planet_image(str(temp_path))
            indices = calculate_all_indices(bands_data)
            
            export_base = script_dir.parent / "exports" / field_name / formatted_date
            export_base.mkdir(parents=True, exist_ok=True)
            for name, array in indices.items():
                export_index_geotiff(array, str(export_base / f"{name}.tif"), bands_data['metadata'])
                print(f"   [OK] {name}.tif")
                
            summary = {'success': 1, 'total': 1, 'errors': 0}
        else:
            summary = process_field(field_path)
            
        step1_time = time.time() - step1_start
        
        print(f"\n[OK] Step 1 completed in {step1_time:.1f} seconds")
        print(f"  - Images processed: {summary['success']}/{summary['total']}")
        print(f"  - Errors: {summary['errors']}")
        
    except Exception as e:
        print(f"\n[FAILED] Step 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ========================================================================
    # STEP 2: Generate Time Series Statistics
    # ========================================================================
    print_header("STEP 2/3: GENERATING TIME SERIES STATISTICS")
    step2_start = time.time()
    
    try:
        generate_all_timeseries(exports_dir="exports")
        step2_time = time.time() - step2_start
        
        print(f"\n[OK] Step 2 completed in {step2_time:.1f} seconds")
        
    except Exception as e:
        print(f"\n[FAILED] Step 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ========================================================================
    # STEP 3: Calculate Water Balance
    # ========================================================================
    print_header("STEP 3/3: CALCULATING WATER BALANCE")
    step3_start = time.time()
    
    try:
        process_all_fields(exports_dir="exports")
        step3_time = time.time() - step3_start
        
        print(f"\n[OK] Step 3 completed in {step3_time:.1f} seconds")
        
    except Exception as e:
        print(f"\n[FAILED] Step 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # ========================================================================
    # FINAL SUMMARY
    # ========================================================================
    total_time = time.time() - start_time
    
    print_header("PROCESSING COMPLETE!")
    print(f"Field: {field_name}")
    print(f"\nTiming Summary:")
    print(f"  Step 1 (Indices):      {step1_time:.1f}s")
    print(f"  Step 2 (Time Series):  {step2_time:.1f}s")
    print(f"  Step 3 (Water Balance): {step3_time:.1f}s")
    print(f"  {'-'*40}")
    print(f"  Total Time:            {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print(f"\nOutput Files:")
    print(f"  - exports/{field_name}/[dates]/[indices].tif")
    print(f"  - exports/{field_name}_dates.json")
    print(f"  - exports/{field_name}_timeseries.json")
    print(f"  - exports/{field_name}_water_balance.json")
    print(f"  - exports/processing_summary.json")
    print(f"  - exports/timeseries_generation_summary.json")
    print(f"  - exports/water_balance_summary.json")
    print(f"\n{'='*70}\n")
    
    return True


def main():
    """Run the complete processing pipeline from CLI"""
    # Get field path from command line or use default
    field_arg = sys.argv[1] if len(sys.argv) > 1 else None
    
    if not run_full_pipeline(field_arg):
        sys.exit(1)


if __name__ == "__main__":
    main()
