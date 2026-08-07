import os
import io
import json
import sqlite3
import urllib.request
import threading
import zstandard as zstd
from datetime import datetime, timedelta

DB_PATH = "addresses.db"
TEMP_DB_PATH = "addresses_temp.db"
META_PATH = "db_meta.json"
ZST_URL = "https://raw.githubusercontent.com/LJPc-solutions/Nederlandse-adressen-en-postcodes/main/Nederland.csv.zst"
ZST_TEMP_PATH = "Nederland.csv.zst"

# Global lock to prevent simultaneous executions across threads
_db_update_lock = threading.Lock()

def get_remote_file_etag():
    """Queries the remote file headers to check the ETag / Last-Modified metadata."""
    try:
        req = urllib.request.Request(ZST_URL, method='HEAD')
        with urllib.request.urlopen(req) as response:
            etag = response.headers.get('ETag') or response.headers.get('Last-Modified')
            return etag
    except Exception as e:
        print(f"⚠️ Failed to fetch remote metadata: {e}")
        return None

def load_metadata():
    """Loads local database update metadata."""
    if os.path.exists(META_PATH):
        try:
            with open(META_PATH, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_checked": None, "etag": None}

def save_metadata(etag):
    """Saves metadata after a successful update or check."""
    data = {
        "last_checked": datetime.now().isoformat(),
        "etag": etag
    }
    with open(META_PATH, 'w') as f:
        json.dump(data, f, indent=2)

def should_check_for_update():
    """Determines whether 7 days have passed since the last check."""
    if not os.path.exists(DB_PATH):
        return True
    
    meta = load_metadata()
    last_checked_str = meta.get("last_checked")
    if not last_checked_str:
        return True

    last_checked = datetime.fromisoformat(last_checked_str)
    return datetime.now() - last_checked >= timedelta(days=7)

def build_database():
    """Downloads dataset and compiles it into a temporary database."""
    print("📥 Downloading latest Nederlandse-adressen-en-postcodes dataset...")
    urllib.request.urlretrieve(ZST_URL, ZST_TEMP_PATH)

    print("⚡ Decompressing Zstandard CSV and building SQLite database...")
    if os.path.exists(TEMP_DB_PATH):
        os.remove(TEMP_DB_PATH)

    conn = sqlite3.connect(TEMP_DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE addresses (
            straat TEXT,
            huisnummer TEXT,
            huisletter TEXT,
            huisnummertoevoeging TEXT,
            postcode TEXT,
            woonplaats TEXT
        )
    """)

    dctx = zstd.ZstdDecompressor()
    with open(ZST_TEMP_PATH, 'rb') as zst_file:
        with dctx.stream_reader(zst_file) as reader:
            text_stream = io.TextIOWrapper(reader, encoding='utf-8')
            
            # Skip CSV Header
            header = next(text_stream)

            batch = []
            count = 0
            for line in text_stream:
                parts = line.strip().split(';')
                if len(parts) >= 6:
                    straat, hnr, hlet, htoev, pc, wp = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
                    pc_clean = pc.replace(" ", "").upper()
                    batch.append((straat, hnr, hlet, htoev, pc_clean, wp))
                    count += 1

                if len(batch) >= 100000:
                    cursor.executemany("INSERT INTO addresses VALUES (?, ?, ?, ?, ?, ?)", batch)
                    batch.clear()

            if batch:
                cursor.executemany("INSERT INTO addresses VALUES (?, ?, ?, ?, ?, ?)", batch)

    print(f"📦 Imported {count:,} addresses. Indexing database...")
    cursor.execute("CREATE INDEX idx_postcode_hnr ON addresses (postcode, huisnummer)")
    conn.commit()
    conn.close()

    # Clean up dataset download
    if os.path.exists(ZST_TEMP_PATH):
        os.remove(ZST_TEMP_PATH)

    # Atomic Swap: Replace old DB with new DB safely
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    os.rename(TEMP_DB_PATH, DB_PATH)

    print("🚀 Address database updated successfully!")

def init_address_database(force=False):
    """Main function to initialize or update the database if a weekly update is due."""
    if not _db_update_lock.acquire(blocking=False):
        print("⚠️ Address database update is already running in another thread. Skipping duplicate call.")
        return

    try:
        if not os.path.exists(DB_PATH):
            print("📦 Database missing. Running initial setup...")
            remote_etag = get_remote_file_etag()
            build_database()
            save_metadata(remote_etag)
            return

        if not force and not should_check_for_update():
            print("✅ Address database is up-to-date (weekly check not due yet).")
            return

        print("🔍 Performing weekly update check for address database...")
        remote_etag = get_remote_file_etag()
        local_meta = load_metadata()

        if remote_etag and remote_etag == local_meta.get("etag") and not force:
            print("✅ Remote database source has not changed. Updating check timestamp...")
            save_metadata(remote_etag)
        else:
            print("🔄 New update found! Rebuilding database...")
            build_database()
            save_metadata(remote_etag)

    finally:
        _db_update_lock.release()

if __name__ == "__main__":
    init_address_database()