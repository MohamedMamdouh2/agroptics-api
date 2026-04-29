"""
Calculate Water Balance Parameters (FAO-56 Model)
==================================================
This script calculates all water balance parameters for each field based on:
- Indices time series (NDVI, SAVI, FC, etc.)
- Crop parameters (from cropParameters_updated.json)
- Field configuration (planting date, irrigation schedule, etc.)
- Weather data (ETr, precipitation)

Based on: Python_Helpers/swb.py, Python_Helpers/processing.py

Output: For each field, generates water balance time series with:
0. Date
1. ETo (Reference ET - short crop)
2. ETr (Reference ET - tall crop/alfalfa) 
3. Kcb (Basal Crop Coefficient - multiple methods)
4. ETc (Crop ET - multiple methods)
5. AWC (Available Water Content)
6. TAW (Total Available Water)
7. Dr (Root Zone Depletion)
8. fDr (Fraction of Depletion)
9. ETAW (ET Since Last Irrigation)
10. AppliedIrrig (Applied Irrigation Depth)
11. Interpolated (0=observed, 1=interpolated)
12. Predicted (0=historical, 1=forecast)
"""

import os
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path


def load_crop_parameters(crop_type, region, planting_month, soil_type):
    """
    Load crop and soil parameters from cropParameters_updated.json
    
    Based on: Python_Helpers/processing.py lines 180-210
    """
    script_dir = Path(__file__).parent
    crop_params_file = script_dir / "cropParameters_updated.json"
    
    with open(crop_params_file, 'r') as f:
        crop_params = json.load(f)
    
    try:
        crop_data = crop_params[crop_type][region][planting_month]
        soil_data = crop_data["soilParameters"][soil_type]
        
        params = {
            # Crop parameters
            "Kcbini": crop_data["Kcbini"],
            "Kcbmid": crop_data["Kcbmid"],
            "Kcbend": crop_data["Kcbend"],
            "Lini": crop_data["Lini"],
            "Ldev": crop_data["Ldev"],
            "Lmid": crop_data["Lmid"],
            "Lend": crop_data["Lend"],
            "hini": crop_data["hini"],
            "hmax": crop_data["hmax"],
            "Zrmax": crop_data["Zrmax"],
            "pbase": crop_data["pbase"],
            
            # Soil parameters
            "thetaFC": soil_data["thetaFC"],
            "thetaWP": soil_data["thetaWP"],
            "theta0": soil_data["theta0"],
            "Zrini": soil_data["Zrini"],
            "Ze": soil_data["Ze"],
            "REW": soil_data["REW"]
        }
        
        return params
        
    except KeyError as e:
        raise ValueError(f"Crop parameters not found: {crop_type}/{region}/{planting_month}/{soil_type} - {e}")


def calculate_kcb_andy(ndvi):
    """
    Calculate Kcb using Andy's method
    Based on: Python_Helpers/satellites.py line 162-163
    Formula: 0.176 + 1.325*NDVI - 1.466*NDVI² + 1.146*NDVI³
    """
    return 0.176 + 1.325 * ndvi - 1.466 * (ndvi ** 2) + 1.146 * (ndvi ** 3)


def calculate_kcb_ndvi(ndvi):
    """
    Calculate Kcb using NDVI method
    Based on: Python_Helpers/satellites.py line 165-166
    Formula: 1.181*NDVI - 0.026
    """
    return 1.181 * ndvi - 0.026


def calculate_kcb_savi(savi):
    """
    Calculate Kcb using SAVI method
    Based on: Python_Helpers/satellites.py line 168-169
    Formula: 1.416*SAVI + 0.017
    """
    return 1.416 * savi + 0.017


def calculate_kcb_fc(fc):
    """
    Calculate Kcb using Fractional Cover method
    Based on: Python_Helpers/satellites.py line 170
    Formula: 1.10*FC + 0.17
    """
    return 1.10 * fc + 0.17


def calculate_kcb_ensemble(kcb_andy, kcb_ndvi, kcb_fc):
    """
    Calculate Kcb using ensemble (mean of Andy, NDVI, FC)
    Based on: Python_Helpers/satellites.py lines 172-175
    """
    return np.mean([kcb_andy, kcb_ndvi, kcb_fc])


def calculate_kcb_fao56(days_since_planting, crop_params):
    """
    Calculate Kcb using FAO-56 growth stages
    Based on: Python_Helpers/swb.py lines 428-451
    
    Growth stages:
    - Initial: 0 to Lini
    - Development: Lini to (Lini + Ldev)
    - Mid-season: (Lini + Ldev) to (Lini + Ldev + Lmid)
    - Late-season: (Lini + Ldev + Lmid) to (Lini + Ldev + Lmid + Lend)
    """
    s1 = crop_params["Lini"]
    s2 = s1 + crop_params["Ldev"]
    s3 = s2 + crop_params["Lmid"]
    s4 = s3 + crop_params["Lend"]
    
    if 0 <= days_since_planting <= s1:
        # Initial stage
        return crop_params["Kcbini"]
    
    elif s1 < days_since_planting <= s2:
        # Development stage - linear increase
        return crop_params["Kcbini"] + (crop_params["Kcbmid"] - crop_params["Kcbini"]) * (days_since_planting - s1) / (s2 - s1)
    
    elif s2 < days_since_planting <= s3:
        # Mid-season stage
        return crop_params["Kcbmid"]
    
    elif s3 < days_since_planting <= s4:
        # Late-season stage - linear decrease
        return crop_params["Kcbmid"] + (crop_params["Kcbend"] - crop_params["Kcbmid"]) * (days_since_planting - s3) / (s4 - s3)
    
    else:
        # After harvest
        return crop_params["Kcbend"]


def calculate_root_depth(days_since_planting, kcb_fao56, crop_params):
    """
    Calculate root depth (Zr) based on crop growth
    Based on: Python_Helpers/swb.py lines 467-475
    Formula: Zrini + (Zrmax - Zrini) * (Kcb - Kcbini) / (Kcbmid - Kcbini)
    """
    if crop_params["Kcbmid"] == crop_params["Kcbini"]:
        return crop_params["Zrini"]
    
    zr = crop_params["Zrini"] + (crop_params["Zrmax"] - crop_params["Zrini"]) * \
         (kcb_fao56 - crop_params["Kcbini"]) / (crop_params["Kcbmid"] - crop_params["Kcbini"])
    
    return max(crop_params["Zrini"], min(zr, crop_params["Zrmax"]))


def calculate_taw(zr, crop_params):
    """
    Calculate Total Available Water (TAW)
    Based on: FAO-56 Equation
    Formula: TAW = 1000 * (θFC - θWP) * Zr
    Units: mm
    """
    return 1000 * (crop_params["thetaFC"] - crop_params["thetaWP"]) * zr


def calculate_awc(taw, mad):
    """
    Calculate Available Water Content (AWC)
    Based on: Python_Helpers/swb.py line 136
    Formula: AWC = TAW * MAD
    """
    return taw * mad


def simple_water_balance(field_name, field_config, timeseries_data, crop_params):
    """
    Calculate simplified water balance for a field
    
    This is a simplified version that calculates the key parameters.
    For full FAO-56 model, would need pyfao56 library integration.
    
    Based on: Python_Helpers/swb.py and Python_Helpers/processing.py
    """
    print(f"\n{'='*60}")
    print(f"Calculating Water Balance for {field_name}")
    print(f"{'='*60}")
    
    # Parse dates
    planting_date = datetime.strptime(field_config["plantingDate"], "%Y-%m-%d")
    first_irrig_date = datetime.strptime(field_config["firstIrrigDate"], "%Y-%m-%d")
    
    # Get time series
    ts = timeseries_data[0]["timeSeries"]
    
    results = []
    cumulative_etc = 0.0
    last_irrig_date = None
    
    for entry in ts:
        date_str = entry["date"]
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        days_since_planting = (date_obj - planting_date).days
        
        # Get indices
        indices = entry["indices"]
        ndvi_mean = indices["NDVI"]["mean"]
        savi_mean = indices["SAVI"]["mean"]
        fc_mean = indices["FC"]["mean"]
        
        # Calculate Kcb using multiple methods
        kcb_andy = calculate_kcb_andy(ndvi_mean)
        kcb_ndvi = calculate_kcb_ndvi(ndvi_mean)
        kcb_savi = calculate_kcb_savi(savi_mean)
        kcb_fc = calculate_kcb_fc(fc_mean)
        kcb_ensemble = calculate_kcb_ensemble(kcb_andy, kcb_ndvi, kcb_fc)
        kcb_fao56 = calculate_kcb_fao56(days_since_planting, crop_params)
        
        # Clip Kcb values to reasonable range
        kcb_andy = max(0, min(1.3, kcb_andy))
        kcb_ndvi = max(0, min(1.3, kcb_ndvi))
        kcb_savi = max(0, min(1.3, kcb_savi))
        kcb_fc = max(0, min(1.3, kcb_fc))
        kcb_ensemble = max(0, min(1.3, kcb_ensemble))
        
        # For this simplified version, use default ETr value
        # In full implementation, this would come from weather data
        etr = 5.0  # mm/day (typical value)
        eto = 3.5  # mm/day (typical value)
        
        # Calculate ETc for each method
        etc_andy = etr * kcb_andy
        etc_ndvi = etr * kcb_ndvi
        etc_savi = etr * kcb_savi
        etc_fc = etr * kcb_fc
        etc_ensemble = etr * kcb_ensemble
        etc_fao56 = etr * kcb_fao56
        
        # Calculate root depth and TAW
        zr = calculate_root_depth(days_since_planting, kcb_fao56, crop_params)
        taw = calculate_taw(zr, crop_params)
        awc = calculate_awc(taw, field_config["mad"])
        
        # Simplified depletion calculation
        # In full FAO-56, this would include precipitation, runoff, deep percolation, etc.
        cumulative_etc += etc_ensemble
        
        # Check if irrigation is needed (simplified logic)
        applied_irrig = 0.0
        if date_obj >= first_irrig_date:
            # Simple threshold-based irrigation
            if cumulative_etc >= awc:
                applied_irrig = field_config["irrigDepth"]
                cumulative_etc = 0.0
                last_irrig_date = date_obj
        
        # Calculate ETAW (ET since last irrigation)
        etaw = cumulative_etc
        
        # Simplified Dr and fDr
        dr = cumulative_etc
        fdr = dr / taw if taw > 0 else 0
        fdr = max(0, min(1, fdr))
        
        # Flags
        interpolated = 0  # All from satellite observations
        predicted = 0  # All historical data
        
        # Store results
        result = {
            "Date": date_str,
            "ETo": round(eto, 3),
            "ETr": round(etr, 3),
            "Kcb_Andy": round(kcb_andy, 3),
            "Kcb_NDVI": round(kcb_ndvi, 3),
            "Kcb_SAVI": round(kcb_savi, 3),
            "Kcb_FC": round(kcb_fc, 3),
            "Kcb_Ensemble": round(kcb_ensemble, 3),
            "Kcb_FAO56": round(kcb_fao56, 3),
            "ETc_Andy": round(etc_andy, 3),
            "ETc_NDVI": round(etc_ndvi, 3),
            "ETc_SAVI": round(etc_savi, 3),
            "ETc_FC": round(etc_fc, 3),
            "ETc_Ensemble": round(etc_ensemble, 3),
            "ETc_FAO56": round(etc_fao56, 3),
            "AWC": round(awc, 3),
            "TAW": round(taw, 3),
            "Dr": round(dr, 3),
            "fDr": round(fdr, 3),
            "ETAW": round(etaw, 3),
            "AppliedIrrig": round(applied_irrig, 3),
            "Interpolated": interpolated,
            "Predicted": predicted,
            "DaysSincePlanting": days_since_planting,
            "RootDepth_m": round(zr, 3)
        }
        
        results.append(result)
    
    print(f"  OK Processed {len(results)} dates")
    print(f"  OK Date range: {results[0]['Date']} to {results[-1]['Date']}")
    print(f"  OK Days since planting: {results[0]['DaysSincePlanting']} to {results[-1]['DaysSincePlanting']}")
    
    return results


def process_all_fields(exports_dir="exports"):
    """
    Process water balance for all fields
    """
    script_dir = Path(__file__).parent.parent
    exports_path = script_dir / exports_dir
    
    # Load field configuration
    config_file = Path(__file__).parent / "field_config.json"
    with open(config_file, 'r') as f:
        field_configs = json.load(f)
    
    # Find all timeseries files in exports
    all_ts_files = list(exports_path.glob("*_timeseries.json"))
    all_fields = sorted([f.name.replace("_timeseries.json", "") for f in all_ts_files])
    
    print(f"\n{'='*60}")
    print(f"WATER BALANCE CALCULATION")
    print(f"{'='*60}")
    print(f"Exports directory: {exports_path}")
    print(f"Detected fields: {', '.join(all_fields)}")
    
    summary = {
        "total_fields": len(all_fields),
        "fields_processed": 0,
        "fields": []
    }
    
    for field_name in all_fields:
        try:
            # Get config or use default
            field_config = field_configs.get(field_name)
            if not field_config:
                print(f"\n[INFO] No config for {field_name}, using default Maize/April/Loam")
                field_config = {
                    "cropType": "Maize",
                    "region": "Central Valley",
                    "plantingMonth": "April",
                    "soilType": "Loam",
                    "plantingDate": "2025-04-01",
                    "firstIrrigDate": "2025-04-15",
                    "mad": 0.5,
                    "irrigDepth": 50.0
                }

            print(f"\n{'='*60}")
            print(f"Processing {field_name}")
            print(f"  Crop: {field_config['cropType']}")
            print(f"  Planting: {field_config['plantingDate']}")
            print(f"  First Irrigation: {field_config['firstIrrigDate']}")
            print(f"{'='*60}")
            
            # Load time series data
            timeseries_file = exports_path / f"{field_name}_timeseries.json"
            with open(timeseries_file, 'r') as f:
                timeseries_data = json.load(f)
            
            # Load crop parameters
            crop_params = load_crop_parameters(
                field_config["cropType"],
                field_config["region"],
                field_config["plantingMonth"],
                field_config["soilType"]
            )
            
            print(f"  Crop Parameters Loaded:")
            print(f"    Kcbini: {crop_params['Kcbini']}, Kcbmid: {crop_params['Kcbmid']}, Kcbend: {crop_params['Kcbend']}")
            print(f"    Growth stages: Lini={crop_params['Lini']}, Ldev={crop_params['Ldev']}, Lmid={crop_params['Lmid']}, Lend={crop_params['Lend']}")
            
            # Calculate water balance
            wb_results = simple_water_balance(field_name, field_config, timeseries_data, crop_params)
            
            # Save results
            output_file = exports_path / f"{field_name}_water_balance.json"
            with open(output_file, 'w') as f:
                json.dump(wb_results, f, indent=2)
            
            print(f"  -> Saved: {output_file.name}")
            
            # Update summary
            summary["fields_processed"] += 1
            summary["fields"].append({
                "field": field_name,
                "crop": field_config["cropType"],
                "dates_count": len(wb_results),
                "planting_date": field_config["plantingDate"],
                "first_irrig": field_config["firstIrrigDate"]
            })
            
        except Exception as e:
            print(f"  ERROR processing {field_name}: {e}")
            import traceback
            traceback.print_exc()
    
    # Save summary
    summary_file = exports_path / "water_balance_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"WATER BALANCE CALCULATION COMPLETE")
    print(f"{'='*60}")
    print(f"Fields processed: {summary['fields_processed']}/{summary['total_fields']}")
    print(f"Summary saved: {summary_file.name}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    process_all_fields()
