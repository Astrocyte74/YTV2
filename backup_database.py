#!/usr/bin/env python3
"""
Database Backup Script for YTV2 Dashboard
Creates timestamped backup of SQLite database and makes it downloadable
"""

import sqlite3
import shutil
import os
from datetime import datetime
from pathlib import Path
import json

def create_database_backup():
    """Create a timestamped backup of the SQLite database"""
    
    # Database paths
    db_path = Path("ytv2_content.db")
    data_dir = Path("data")
    
    # Create data directory if it doesn't exist
    data_dir.mkdir(exist_ok=True)
    
    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"ytv2_backup_{timestamp}.db"
    backup_path = data_dir / backup_filename
    
    try:
        if db_path.exists():
            # Create backup copy
            shutil.copy2(db_path, backup_path)
            print(f"✅ Database backup created: {backup_path}")
            
            # Get database statistics
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Count records in main tables
            stats = {}
            cursor.execute("SELECT COUNT(*) FROM content")
            stats['total_content'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM content_summaries")
            stats['total_summaries'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT language) FROM content WHERE language IS NOT NULL")
            stats['unique_languages'] = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(DISTINCT content_type) FROM content WHERE content_type IS NOT NULL")
            stats['unique_content_types'] = cursor.fetchone()[0]
            
            # Get language distribution
            cursor.execute("""
                SELECT language, COUNT(*) as count 
                FROM content 
                WHERE language IS NOT NULL 
                GROUP BY language 
                ORDER BY count DESC
            """)
            stats['language_distribution'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            # Get category distribution  
            cursor.execute("""
                SELECT category, COUNT(*) as count
                FROM content 
                WHERE category IS NOT NULL AND category != '[]'
                GROUP BY category 
                ORDER BY count DESC
                LIMIT 10
            """)
            stats['top_categories'] = {row[0]: row[1] for row in cursor.fetchall()}
            
            conn.close()
            
            # Save backup metadata
            backup_info = {
                'backup_timestamp': datetime.now().isoformat(),
                'original_db_path': str(db_path),
                'backup_path': str(backup_path),
                'backup_size_bytes': backup_path.stat().st_size,
                'statistics': stats
            }
            
            info_path = data_dir / f"backup_info_{timestamp}.json"
            with open(info_path, 'w') as f:
                json.dump(backup_info, f, indent=2)
            
            print(f"📊 Backup statistics:")
            print(f"   Total content records: {stats['total_content']:,}")
            print(f"   Total summaries: {stats['total_summaries']:,}")
            print(f"   Unique languages: {stats['unique_languages']}")
            print(f"   Language distribution: {stats['language_distribution']}")
            print(f"   Backup size: {backup_path.stat().st_size / 1024 / 1024:.1f} MB")
            print(f"📝 Backup info saved: {info_path}")
            
            return {
                'success': True,
                'backup_path': str(backup_path),
                'info_path': str(info_path),
                'statistics': stats
            }
            
        else:
            print(f"❌ Database not found: {db_path}")
            return {'success': False, 'error': 'Database file not found'}
            
    except Exception as e:
        print(f"❌ Backup failed: {e}")
        return {'success': False, 'error': str(e)}

if __name__ == "__main__":
    result = create_database_backup()
    if result['success']:
        print("🎉 Database backup completed successfully!")
    else:
        print(f"💥 Backup failed: {result['error']}")