#!/usr/bin/env python3
"""
Parse backfill logs and update database with complete subcategory structure.

This script extracts the complete category→subcategories mappings from 
back_Fill_logs.md and updates the database with a new subcategories_json column.

Usage:
    python parse_backfill_logs.py --dry-run    # Preview changes
    python parse_backfill_logs.py              # Apply changes
"""

import re
import json
import sqlite3
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def parse_backfill_logs(log_file: Path) -> Dict[str, Dict[str, Any]]:
    """Parse the backfill logs and extract video ID → category/subcategory mappings."""
    
    with open(log_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern to match video processing blocks
    video_pattern = r'📝 Processing \d+/\d+: (.+?)\.\.\.'
    category_structure_pattern = r'📋 Detailed Category Structure:(.*?)(?=✅ Updated record|📝 Processing|\Z)'
    update_pattern = r'✅ Updated record (yt:[a-zA-Z0-9_-]+):'
    
    results = {}
    
    # Find all video processing sections
    video_matches = list(re.finditer(video_pattern, content))
    
    for i, video_match in enumerate(video_matches):
        video_title = video_match.group(1).strip()
        start_pos = video_match.end()
        
        # Find the end of this video's processing section
        end_pos = video_matches[i+1].start() if i+1 < len(video_matches) else len(content)
        section = content[start_pos:end_pos]
        
        # Extract category structure
        structure_match = re.search(category_structure_pattern, section, re.DOTALL)
        if not structure_match:
            logger.warning(f"No category structure found for video: {video_title}")
            continue
            
        structure_text = structure_match.group(1)
        
        # Extract video ID from update record
        update_match = re.search(update_pattern, section)
        if not update_match:
            logger.warning(f"No video ID found for video: {video_title}")
            continue
            
        video_id = update_match.group(1)
        
        # Parse the category structure lines
        categories = []
        category_lines = re.findall(r'(\d+)\.\s+(.+?)\s+→\s+\[(.+?)\]', structure_text)
        
        for line_match in category_lines:
            category_name = line_match[1].strip()
            subcats_text = line_match[2].strip()
            
            # Parse subcategories - handle both 'item1', 'item2' and 'item1, item2' formats
            subcats = []
            if subcats_text:
                # Remove quotes and split by comma
                subcats = [sc.strip().strip("'\"") for sc in subcats_text.split("',")]
                # Clean up the last item (remove trailing quote)
                if subcats:
                    subcats[-1] = subcats[-1].rstrip("'\"")
                # Filter out empty strings
                subcats = [sc for sc in subcats if sc]
            
            categories.append({
                "category": category_name,
                "subcategories": subcats
            })
        
        if categories:
            results[video_id] = {
                "title": video_title,
                "categories": categories
            }
            logger.info(f"Parsed {video_id}: {video_title} with {len(categories)} categories")
        else:
            logger.warning(f"No categories parsed for {video_id}: {video_title}")
    
    logger.info(f"Successfully parsed {len(results)} video records from logs")
    return results

def add_subcategories_column(db_path: Path) -> None:
    """Add subcategories_json column to the database if it doesn't exist."""
    
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # Try to add the column
        cursor.execute('ALTER TABLE content ADD COLUMN subcategories_json TEXT')
        conn.commit()
        logger.info("✅ Added subcategories_json column to content table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logger.info("ℹ️ subcategories_json column already exists")
        else:
            raise
    finally:
        conn.close()

def update_database_records(db_path: Path, parsed_data: Dict[str, Dict[str, Any]], dry_run: bool = False) -> None:
    """Update database records with subcategories_json data."""
    
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        
        updated_count = 0
        error_count = 0
        
        for video_id, data in parsed_data.items():
            try:
                # Convert to JSON
                subcategories_json = json.dumps({"categories": data["categories"]}, ensure_ascii=False)
                
                if dry_run:
                    logger.info(f"DRY RUN: Would update {video_id} with: {subcategories_json}")
                else:
                    # Update the record
                    cursor.execute(
                        "UPDATE content SET subcategories_json = ? WHERE id = ?",
                        (subcategories_json, video_id)
                    )
                    
                    if cursor.rowcount > 0:
                        updated_count += 1
                        logger.info(f"✅ Updated {video_id}: {data['title']}")
                    else:
                        logger.warning(f"⚠️ No record found for {video_id}: {data['title']}")
                        error_count += 1
                        
            except Exception as e:
                logger.error(f"❌ Error updating {video_id}: {e}")
                error_count += 1
        
        if not dry_run:
            conn.commit()
            logger.info(f"🎉 Database update complete: {updated_count} updated, {error_count} errors")
        else:
            logger.info(f"🎯 DRY RUN complete: {updated_count} records would be updated, {error_count} errors")
            
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Parse backfill logs and update database")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying them")
    parser.add_argument("--db", default="ytv2_content_live.db", help="Database file path")
    parser.add_argument("--logs", default="back_Fill_logs.md", help="Backfill logs file path")
    
    args = parser.parse_args()
    
    db_path = Path(args.db)
    logs_path = Path(args.logs)
    
    if not db_path.exists():
        logger.error(f"Database file not found: {db_path}")
        return 1
        
    if not logs_path.exists():
        logger.error(f"Logs file not found: {logs_path}")
        return 1
    
    logger.info(f"Starting backfill logs parsing...")
    logger.info(f"Database: {db_path}")
    logger.info(f"Logs: {logs_path}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE UPDATE'}")
    
    # Parse the logs
    parsed_data = parse_backfill_logs(logs_path)
    
    if not parsed_data:
        logger.error("No data parsed from logs!")
        return 1
    
    # Add column if needed (only in live mode)
    if not args.dry_run:
        add_subcategories_column(db_path)
    
    # Update records
    update_database_records(db_path, parsed_data, dry_run=args.dry_run)
    
    logger.info("Script completed successfully!")
    return 0

if __name__ == "__main__":
    exit(main())