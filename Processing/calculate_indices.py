"""
Modular Vegetation Indices Calculator
Extracted from Agroptics satellites.py and satellites_optimized.py

Calculates 6 vegetation indices from Planet 8-band imagery:
- NDVI (Normalized Difference Vegetation Index)
- SAVI (Soil Adjusted Vegetation Index)
- FC (Fractional Cover)
- GCI (Green Chlorophyll Index)
- RECI (Red Edge Chlorophyll Index)
- MSAVI (Modified Soil Adjusted Vegetation Index)

All formulas are exact copies from the original Agroptics codebase.
"""

import os
import numpy as np
import rasterio
from rasterio.transform import from_bounds
import json
from pathlib import Path


# ============================================================================
# VEGETATION INDICES CALCULATION FUNCTIONS
# Exact formulas from Python_Helpers/satellites_optimized.py lines 51-79
# ============================================================================

def calculate_ndvi(red, nir):
    """
    Calculate NDVI (Normalized Difference Vegetation Index)
    
    Formula: (NIR - Red) / (NIR + Red)
    Source: satellites_optimized.py lines 51-54
    
    Args:
        red: Red band array (normalized 0-1)
        nir: NIR band array (normalized 0-1)
    
    Returns:
        NDVI array (range: -1 to 1)
    """
    return (nir - red) / (nir + red + 1e-10)


def calculate_savi(red, nir, L=0.5):
    """
    Calculate SAVI (Soil Adjusted Vegetation Index)
    
    Formula: ((NIR - Red) / (NIR + Red + L)) × (1 + L)
    L = 0.5 (soil brightness correction factor)
    Source: satellites_optimized.py lines 56-59
    
    Args:
        red: Red band array (normalized 0-1)
        nir: NIR band array (normalized 0-1)
        L: Soil brightness correction factor (default 0.5)
    
    Returns:
        SAVI array
    """
    return ((nir - red) / (nir + red + L)) * (1 + L)


def calculate_fc(ndvi):
    """
    Calculate FC (Fractional Cover / Vegetation Cover)
    
    Formula: NDVI < 0.15 ? 0 : 1.26 × NDVI - 0.18
    Source: satellites_optimized.py lines 61-64
    
    Args:
        ndvi: NDVI array
    
    Returns:
        FC array (range: 0 to ~1)
    """
    return np.where(ndvi < 0.15, 0, 1.26 * ndvi - 0.18)


def calculate_gci(nir, green):
    """
    Calculate GCI (Green Chlorophyll Index)
    
    Formula: (NIR / Green) - 1
    Source: satellites_optimized.py lines 66-69
    
    Args:
        nir: NIR band array (normalized 0-1)
        green: Green band array (normalized 0-1)
    
    Returns:
        GCI array
    """
    return (nir / (green + 1e-10)) - 1


def calculate_reci(nir, rededge):
    """
    Calculate RECI (Red Edge Chlorophyll Index)
    
    Formula: (NIR / RedEdge) - 1
    Source: satellites_optimized.py lines 71-74
    
    Args:
        nir: NIR band array (normalized 0-1)
        rededge: Red Edge band array (normalized 0-1)
    
    Returns:
        RECI array
    """
    return (nir / (rededge + 1e-10)) - 1


def calculate_msavi(red, nir):
    """
    Calculate MSAVI (Modified Soil Adjusted Vegetation Index)
    
    Formula: (2 × NIR + 1 - sqrt((2 × NIR + 1)² - 8 × (NIR - Red))) / 2
    Source: satellites_optimized.py lines 76-79
    
    Args:
        red: Red band array (normalized 0-1)
        nir: NIR band array (normalized 0-1)
    
    Returns:
        MSAVI array
    """
    return (2 * nir + 1 - np.sqrt((2 * nir + 1) ** 2 - 8 * (nir - red))) / 2


# ============================================================================
# IMAGE PROCESSING AND EXPORT
# Based on satellites_optimized.py process_image_locally() and export logic
# ============================================================================

def load_planet_image(image_path):
    """
    Load Planet 8-band image and extract required bands
    
    Planet 8-band SuperDove band order (from satellites_optimized.py):
    - Band 1 (index 0): Coastal Blue
    - Band 2 (index 1): Blue
    - Band 3 (index 2): Green I
    - Band 4 (index 3): Green
    - Band 5 (index 4): Yellow
    - Band 6 (index 5): Red
    - Band 7 (index 6): Red Edge
    - Band 8 (index 7): NIR
    
    Args:
        image_path: Path to Planet GeoTIFF file
    
    Returns:
        dict with band arrays and metadata
    """
    with rasterio.open(image_path) as src:
        # Read all bands
        bands = src.read().astype(float)
        
        # Handle nodata values (convert to NaN)
        if src.nodata is not None:
            bands[bands == src.nodata] = np.nan
        else:
            bands[bands == 0] = np.nan
        
        # Planet Surface Reflectance scale factor
        scale_factor = 10000.0
        
        num_bands = bands.shape[0]
        
        if num_bands >= 8:
            # 8-Band SuperDove mapping (from satellites_optimized.py lines 280-290)
            blue = bands[1] / scale_factor      # Index 1: Blue
            green = bands[3] / scale_factor     # Index 3: Green
            red = bands[5] / scale_factor       # Index 5: Red
            rededge = bands[6] / scale_factor   # Index 6: Red Edge
            nir = bands[7] / scale_factor       # Index 7: NIR
        elif num_bands >= 4:
            # 4-Band mapping (fallback)
            blue = bands[0] / scale_factor
            green = bands[1] / scale_factor
            red = bands[2] / scale_factor
            nir = bands[3] / scale_factor
            rededge = nir  # No red edge in 4-band
        else:
            raise ValueError(f"Expected at least 4 bands, got {num_bands}")
        
        # Store metadata for export
        metadata = {
            'profile': src.profile.copy(),
            'transform': src.transform,
            'crs': src.crs,
            'width': src.width,
            'height': src.height
        }
        
        return {
            'blue': blue,
            'green': green,
            'red': red,
            'rededge': rededge,
            'nir': nir,
            'metadata': metadata
        }


def calculate_all_indices(bands_dict):
    """
    Calculate all 6 vegetation indices from band dictionary
    
    Args:
        bands_dict: Dictionary with 'red', 'green', 'nir', 'rededge' keys
    
    Returns:
        Dictionary with all calculated indices
    """
    red = bands_dict['red']
    green = bands_dict['green']
    nir = bands_dict['nir']
    rededge = bands_dict['rededge']
    
    # Calculate NDVI first (needed for FC)
    ndvi = calculate_ndvi(red, nir)
    
    # Calculate all indices
    indices = {
        'NDVI': ndvi,
        'SAVI': calculate_savi(red, nir),
        'FC': calculate_fc(ndvi),
        'GCI': calculate_gci(nir, green),
        'RECI': calculate_reci(nir, rededge),
        'MSAVI': calculate_msavi(red, nir)
    }
    
    return indices


def export_index_geotiff(index_array, output_path, metadata):
    """
    Export a single index as GeoTIFF
    
    Args:
        index_array: 2D numpy array with index values
        output_path: Output file path
        metadata: Metadata dict from load_planet_image()
    """
    # Update profile for single-band float32 output
    profile = metadata['profile'].copy()
    profile.update({
        'count': 1,
        'dtype': 'float32',
        'nodata': np.nan,
        'compress': 'lzw'
    })
    
    # Create output directory if needed
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Write GeoTIFF
    with rasterio.open(output_path, 'w', **profile) as dst:
        dst.write(index_array.astype('float32'), 1)


def process_image_folder(image_folder_path, field_name):
    """
    Process a single image folder and export all indices
    
    Args:
        image_folder_path: Path to folder containing Planet image
        field_name: Name of the field (e.g., 'Field_10')
    
    Returns:
        dict with processing results
    """
    image_folder = Path(image_folder_path)
    date_folder_name = image_folder.name  # e.g., '20250329_180511_67_2516'
    
    # Extract date from folder name (YYYYMMDD format)
    date_str = date_folder_name.split('_')[0]  # '20250329'
    formatted_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"  # '2025-03-29'
    
    # Find the AnalyticMS image file
    image_files = list(image_folder.glob('*_3B_AnalyticMS_SR_8b_*.tif'))
    
    if not image_files:
        print(f"[WARNING] No AnalyticMS image found in {image_folder.name}")
        return None
    
    image_path = image_files[0]
    print(f"Processing: {image_folder.name}")
    
    try:
        # Load image and extract bands
        bands_data = load_planet_image(str(image_path))
        
        # Calculate all indices
        indices = calculate_all_indices(bands_data)
        
        # Create export folder structure: exports/{field_name}/{date}/
        # image_folder.parent is the Field folder (e.g., Field_10)
        field_folder = image_folder.parent
        export_base = field_folder.parent.parent / 'exports' / field_folder.name / formatted_date
        export_base.mkdir(parents=True, exist_ok=True)
        
        # Export each index as GeoTIFF
        for index_name, index_array in indices.items():
            output_path = export_base / f"{index_name}.tif"
            export_index_geotiff(index_array, str(output_path), bands_data['metadata'])
            print(f"   [OK] {index_name}.tif")
        
        return {
            'date': formatted_date,
            'folder': image_folder.name,
            'status': 'success',
            'indices_exported': list(indices.keys())
        }
        
    except Exception as e:
        print(f"   [ERROR] Error: {e}")
        return {
            'date': formatted_date,
            'folder': image_folder.name,
            'status': 'error',
            'error': str(e)
        }


def process_field(field_path):
    """
    Process all images in a field folder
    
    Args:
        field_path: Path to field folder (e.g., 'Field_10')
    
    Returns:
        Summary statistics
    """
    field_folder = Path(field_path)
    field_name = field_folder.name
    
    print(f"\n{'='*60}")
    print(f"Processing {field_name}")
    print(f"{'='*60}\n")
    
    # Get all date folders (exclude exports and geojson)
    date_folders = [f for f in field_folder.iterdir() 
                   if f.is_dir() and f.name != 'exports']
    
    print(f"Found {len(date_folders)} image folders\n")
    
    results = []
    for date_folder in sorted(date_folders):
        result = process_image_folder(date_folder, field_name)
        if result:
            results.append(result)
    
    # Summary
    success_count = sum(1 for r in results if r['status'] == 'success')
    error_count = sum(1 for r in results if r['status'] == 'error')
    
    print(f"\n{'='*60}")
    print(f"Successfully processed: {success_count}/{len(results)}")
    print(f"Errors: {error_count}/{len(results)}")
    print(f"{'='*60}\n")
    
    return {
        'field': field_name,
        'total': len(results),
        'success': success_count,
        'errors': error_count,
        'results': results
    }


# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Get field path from command line or use default
    if len(sys.argv) > 1:
        field_path = sys.argv[1]
    else:
        # Default: process Field_10
        script_dir = Path(__file__).parent
        field_path = script_dir / 'Field_10'
    
    if not Path(field_path).exists():
        print(f"[ERROR] Error: Field path does not exist: {field_path}")
        sys.exit(1)
    
    # Process the field
    summary = process_field(field_path)
    
    # Save summary to JSON in exports/{field_name}/
    field_folder = Path(field_path)
    summary_path = field_folder.parent / 'exports' / field_folder.name / 'processing_summary.json'
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"Summary saved to: {summary_path}")
