#!/usr/bin/env python3
"""
Backfill Script: Add indexed_at and language fields to existing JSON reports

This script adds:
- indexed_at: timestamp when report was first added (from file mtime)
- original_language: language of the original video (default: 'en')
- summary_language: language of the summary (from analysis.language)
- audio_language: language of audio if different from summary

Usage:
    python backfill_metadata.py --reports-dir data --dry-run
    python backfill_metadata.py --reports-dir data
"""

import json
import os
import argparse
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any

def iso_utc(timestamp: float) -> str:
    """Convert timestamp to UTC ISO format with Z suffix"""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def atomic_write(file_path: Path, data: Dict[str, Any]) -> None:
    """Atomically write JSON data to file (write to temp, then replace)"""
    tmp_path = file_path.with_suffix(".json.tmp")
    
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    
    tmp_path.replace(file_path)

def process_file(json_file: Path, dry_run: bool = False) -> Dict[str, Any]:
    """Process a single JSON file and return stats"""
    stats = {
        'processed': False,
        'changes': [],
        'errors': []
    }
    
    try:
        # Read existing data
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        original_data = data.copy()
        modified = False
        
        # Add indexed_at from file mtime if missing
        if 'indexed_at' not in data:
            indexed_at = iso_utc(json_file.stat().st_mtime)
            data['indexed_at'] = indexed_at
            stats['changes'].append(f"Added indexed_at: {indexed_at}")
            modified = True
        
        # Add original_language if missing (default to English)
        if 'original_language' not in data:
            data['original_language'] = 'en'
            stats['changes'].append("Added original_language: en")
            modified = True
        
        # Add summary_language from analysis.language if missing
        if 'summary_language' not in data:
            analysis_lang = data.get('analysis', {}).get('language', 'en')
            data['summary_language'] = analysis_lang
            stats['changes'].append(f"Added summary_language: {analysis_lang}")
            modified = True
        
        # Add audio_language if missing (default to summary_language)
        if 'audio_language' not in data:
            audio_lang = data.get('summary_language', 'en')
            data['audio_language'] = audio_lang
            stats['changes'].append(f"Added audio_language: {audio_lang}")
            modified = True
        
        # Write back if changes were made and not dry run
        if modified and not dry_run:
            atomic_write(json_file, data)
            stats['processed'] = True
        elif modified and dry_run:
            stats['processed'] = True  # Mark as would-be-processed
            
    except Exception as e:
        stats['errors'].append(str(e))
    
    return stats

def main():
    parser = argparse.ArgumentParser(description='Backfill metadata for JSON reports')
    parser.add_argument('--reports-dir', default='data', 
                       help='Directory containing JSON report files (default: data)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be changed without writing files')
    
    args = parser.parse_args()
    
    reports_dir = Path(args.reports_dir)
    
    if not reports_dir.exists():
        print(f"❌ Reports directory not found: {reports_dir}")
        return 1
    
    print(f"🔍 Scanning {reports_dir} for JSON files...")
    if args.dry_run:
        print("🏃 DRY RUN MODE - No files will be modified")
    print()
    
    json_files = list(reports_dir.glob('*.json'))
    if not json_files:
        print(f"❌ No JSON files found in {reports_dir}")
        return 1
    
    print(f"📁 Found {len(json_files)} JSON files")
    print()
    
    # Process all files
    total_processed = 0
    total_errors = 0
    all_changes = []
    
    for json_file in json_files:
        if json_file.name.startswith('.'):
            continue  # Skip hidden files
            
        stats = process_file(json_file, args.dry_run)
        
        if stats['processed']:
            total_processed += 1
            if stats['changes']:
                change_summary = ", ".join(stats['changes'])
                print(f"✅ {json_file.name}: {change_summary}")
                all_changes.extend(stats['changes'])
            else:
                print(f"⏭️  {json_file.name}: No changes needed")
        
        if stats['errors']:
            total_errors += 1
            for error in stats['errors']:
                print(f"❌ {json_file.name}: {error}")
    
    # Summary
    print()
    print("=" * 60)
    print("BACKFILL SUMMARY")
    print("=" * 60)
    print(f"📊 Total files scanned: {len(json_files)}")
    print(f"✅ Files processed: {total_processed}")
    print(f"❌ Files with errors: {total_errors}")
    
    if all_changes:
        print(f"🔧 Total changes: {len(all_changes)}")
        
        # Count change types
        change_types = {}
        for change in all_changes:
            change_type = change.split(':')[0]
            change_types[change_type] = change_types.get(change_type, 0) + 1
        
        for change_type, count in change_types.items():
            print(f"   - {change_type}: {count}")
    
    if args.dry_run:
        print()
        print("🏃 This was a dry run. Re-run without --dry-run to apply changes.")
    else:
        print()
        print("✅ Backfill complete!")
    
    return 0 if total_errors == 0 else 1

if __name__ == "__main__":
    exit(main())