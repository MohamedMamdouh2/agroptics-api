"""
Batch process all fields in the AA GT Restructured files folder
"""

from pathlib import Path
from Processing.calculate_indices import process_field
import json
import time

def main():
    # Get all field folders
    base_path = Path(__file__).parent
    field_folders = [f for f in base_path.iterdir() 
                    if f.is_dir() and f.name.startswith('Field_')]
    
    if not field_folders:
        print("ERROR: No field folders found!")
        return
    
    print(f"\n{'='*60}")
    print(f"BATCH PROCESSING: {len(field_folders)} fields")
    print(f"{'='*60}\n")
    
    for field_folder in sorted(field_folders):
        print(f"Field: {field_folder.name}")
    
    print(f"\n{'='*60}\n")
    
    # Process each field
    all_summaries = []
    start_time = time.time()
    
    for i, field_folder in enumerate(sorted(field_folders), 1):
        print(f"\n[{i}/{len(field_folders)}] Processing {field_folder.name}...")
        
        field_start = time.time()
        summary = process_field(field_folder)
        field_duration = time.time() - field_start
        
        summary['processing_time_seconds'] = round(field_duration, 2)
        all_summaries.append(summary)
        
        print(f"Time: {field_duration:.1f}s")
    
    # Overall summary
    total_duration = time.time() - start_time
    total_images = sum(s['total'] for s in all_summaries)
    total_success = sum(s['success'] for s in all_summaries)
    total_errors = sum(s['errors'] for s in all_summaries)
    
    print(f"\n{'='*60}")
    print(f"OVERALL SUMMARY")
    print(f"{'='*60}")
    print(f"Fields processed: {len(field_folders)}")
    print(f"Total images: {total_images}")
    print(f"OK Successful: {total_success} ({total_success/total_images*100:.1f}%)")
    print(f"ERROR Errors: {total_errors} ({total_errors/total_images*100:.1f}%)")
    print(f"Total time: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
    print(f"Average: {total_duration/total_images:.2f}s per image")
    print(f"{'='*60}\n")
    
    # Save combined summary
    combined_summary = {
        'total_fields': len(field_folders),
        'total_images': total_images,
        'total_success': total_success,
        'total_errors': total_errors,
        'processing_time_seconds': round(total_duration, 2),
        'average_time_per_image': round(total_duration/total_images, 2),
        'fields': all_summaries
    }
    
    summary_path = base_path.parent / 'exports' / 'batch_processing_summary.json'
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(summary_path, 'w') as f:
        json.dump(combined_summary, f, indent=2)
    
    print(f"Summary saved to: {summary_path}")

if __name__ == "__main__":
    main()
