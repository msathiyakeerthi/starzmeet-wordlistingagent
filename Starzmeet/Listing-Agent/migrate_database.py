"""
Database Migration Script
Adds new columns and tables for WordPress sync and keyword management
"""
import sqlite3
import os

DB_PATH = "autism_services.db"

def migrate_database():
    print("Starting database migration...")
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Check if wp_synced column exists
        c.execute("PRAGMA table_info(places)")
        columns = [row[1] for row in c.fetchall()]
        
        if 'wp_synced' not in columns:
            print("Adding WordPress sync columns to places table...")
            c.execute("ALTER TABLE places ADD COLUMN wp_synced INTEGER DEFAULT 0")
            c.execute("ALTER TABLE places ADD COLUMN wp_post_id INTEGER")
            c.execute("ALTER TABLE places ADD COLUMN wp_sync_date TEXT")
            print("[OK] WordPress sync columns added")
        else:
            print("[OK] WordPress sync columns already exist")
        
        # Create index for wp_synced
        try:
            c.execute('CREATE INDEX IF NOT EXISTS idx_wp_synced ON places (wp_synced)')
            print("[OK] Index created for wp_synced")
        except Exception as e:
            print(f"Index creation skipped: {e}")
        
        # Create search_keywords table
        c.execute('''
            CREATE TABLE IF NOT EXISTS search_keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                category TEXT,
                active INTEGER DEFAULT 1,
                created_at TEXT,
                last_used TEXT
            )
        ''')
        print("[OK] search_keywords table created")
        
        # Check if keywords table is empty
        c.execute("SELECT COUNT(*) FROM search_keywords")
        if c.fetchone()[0] == 0:
            print("Inserting default keywords...")
            default_keywords = [
                ("autism therapy centers", "Autism Core", 1),
                ("autism treatment clinics", "Autism Core", 1),
                ("autism support services", "Autism Core", 1),
                ("ABA therapy centers", "Autism Core", 1),
                ("autism behavioral therapy", "Autism Core", 1),
                ("autism diagnostic centers", "Autism Core", 1),
                ("developmental disabilities services", "Special Needs", 1),
                ("special needs therapy", "Special Needs", 1),
                ("ADHD therapy centers", "ADHD", 1),
                ("ADHD coaching clinics", "ADHD", 1),
                ("behavioral therapy ADHD", "ADHD", 1),
                ("parent training autism ADHD", "Training", 1),
                ("speech therapy autism ADHD", "Therapy", 1),
                ("occupational therapy sensory integration", "Therapy", 1),
                ("sensory integration therapy", "Therapy", 1),
                ("sensory gyms autism ADHD", "Recreation", 1),
                ("dyslexia learning centers", "Learning", 1),
                ("learning disability centers", "Learning", 1),
                ("social skills groups autism ADHD", "Community", 1),
                ("special needs camps autism ADHD", "Recreation", 1),
                ("adaptive sports autism ADHD", "Recreation", 1),
                ("autism ADHD inclusive recreation centers", "Recreation", 1),
                ("autism ADHD support groups", "Community", 1)
            ]
            c.executemany(
                "INSERT INTO search_keywords (keyword, category, active) VALUES (?, ?, ?)",
                default_keywords
            )
            print(f"[OK] Inserted {len(default_keywords)} default keywords")
        else:
            print("[OK] Keywords already exist")
        
        conn.commit()
    
    print("\n[SUCCESS] Database migration completed successfully!")
    print("\nYou can now run: python app-latest-4.py")

if __name__ == "__main__":
    if not os.path.exists(DB_PATH):
        print(f"❌ Database file '{DB_PATH}' not found!")
        print("The database will be created when you run the app.")
    else:
        migrate_database()

