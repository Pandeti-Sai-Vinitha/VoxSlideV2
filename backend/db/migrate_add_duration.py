"""
Migration script to add duration column to documents table if it doesn't exist
Run this script once to update the existing database schema
"""
import sqlite3
from pathlib import Path
from database import DB_PATH

def migrate():
    """Add duration column to documents table if it doesn't exist"""
    conn = sqlite3.connect(f"sqlite:///{DB_PATH.as_posix()}".replace("sqlite:///", ""))
    cursor = conn.cursor()
    
    try:
        # Check if duration column already exists
        cursor.execute("PRAGMA table_info(documents)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'duration' not in columns:
            print("Adding 'duration' column to documents table...")
            cursor.execute("ALTER TABLE documents ADD COLUMN duration REAL")
            conn.commit()
            print("✓ Successfully added 'duration' column")
        else:
            print("✓ 'duration' column already exists")
    
    except Exception as e:
        print(f"✗ Error during migration: {e}")
        conn.rollback()
    
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
