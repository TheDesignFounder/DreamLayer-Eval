"""
Generation History Database
Manages persistent storage of all generations (images, videos, etc.)
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from contextlib import contextmanager

# Database file location
DB_PATH = os.getenv('DREAMLAYER_HISTORY_DB', os.path.join(os.path.dirname(__file__), 'generation_history.db'))


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_db():
    """Initialize the database with required tables"""
    with get_db_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS generations (
                id TEXT PRIMARY KEY,
                type TEXT NOT NULL,           -- 'txt2img', 'img2img', 'txt2vid', 'img2txt', 'extras'
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                url TEXT NOT NULL,
                prompt TEXT,
                negative_prompt TEXT,
                settings TEXT,                -- JSON string of all generation settings
                created_at TIMESTAMP NOT NULL,
                downloaded INTEGER DEFAULT 0, -- 0 = not downloaded, 1 = downloaded
                favorited INTEGER DEFAULT 0,  -- 0 = not favorited, 1 = favorited
                file_size INTEGER             -- File size in bytes
            )
        ''')

        # Create indexes for common queries
        conn.execute('CREATE INDEX IF NOT EXISTS idx_type ON generations(type)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON generations(created_at)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_favorited ON generations(favorited)')

    print(f"[Database] Initialized database at {DB_PATH}")


def save_generation(generation_data: Dict[str, Any]) -> bool:
    """
    Save a generation to the database

    Args:
        generation_data: Dictionary containing:
            - id: Unique identifier
            - type: Generation type ('txt2img', 'img2img', 'txt2vid', etc.)
            - filename: Generated file name
            - file_path: Full path to file
            - url: URL to access the file
            - prompt: Generation prompt
            - negative_prompt: Negative prompt (optional)
            - settings: Dictionary of generation settings
            - file_size: File size in bytes (optional)

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Calculate file size if not provided
        file_size = generation_data.get('file_size')
        if file_size is None and os.path.exists(generation_data['file_path']):
            file_size = os.path.getsize(generation_data['file_path'])

        with get_db_connection() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO generations
                (id, type, filename, file_path, url, prompt, negative_prompt,
                 settings, created_at, downloaded, favorited, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                generation_data['id'],
                generation_data['type'],
                generation_data['filename'],
                generation_data['file_path'],
                generation_data['url'],
                generation_data.get('prompt', ''),
                generation_data.get('negative_prompt', ''),
                json.dumps(generation_data.get('settings', {})),
                generation_data.get('created_at', datetime.now().isoformat()),
                generation_data.get('downloaded', 0),
                generation_data.get('favorited', 0),
                file_size
            ))

        print(f"[Database] Saved {generation_data['type']} generation: {generation_data['id']}")
        return True

    except Exception as e:
        print(f"[Database] Error saving generation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def get_generations(gen_type: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Get generations from database

    Args:
        gen_type: Filter by generation type (None = all types)
        limit: Maximum number of results

    Returns:
        List of generation dictionaries
    """
    try:
        with get_db_connection() as conn:
            if gen_type:
                cursor = conn.execute('''
                    SELECT * FROM generations
                    WHERE type = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (gen_type, limit))
            else:
                cursor = conn.execute('''
                    SELECT * FROM generations
                    ORDER BY created_at DESC
                    LIMIT ?
                ''', (limit,))

            rows = cursor.fetchall()

            # Convert rows to dictionaries
            generations = []
            for row in rows:
                gen = dict(row)
                # Parse settings JSON
                if gen['settings']:
                    try:
                        gen['settings'] = json.loads(gen['settings'])
                    except:
                        gen['settings'] = {}

                # Check if file still exists
                gen['file_exists'] = os.path.exists(gen['file_path'])

                generations.append(gen)

            return generations

    except Exception as e:
        print(f"[Database] Error getting generations: {str(e)}")
        import traceback
        traceback.print_exc()
        return []


def delete_generation(generation_id: str, delete_file: bool = True) -> bool:
    """
    Delete a generation from database and optionally delete the file

    Args:
        generation_id: ID of the generation to delete
        delete_file: Whether to delete the actual file

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with get_db_connection() as conn:
            # Get file path before deleting from DB
            cursor = conn.execute('SELECT file_path FROM generations WHERE id = ?', (generation_id,))
            row = cursor.fetchone()

            if not row:
                print(f"[Database] Generation {generation_id} not found")
                return False

            file_path = row['file_path']

            # Delete from database
            conn.execute('DELETE FROM generations WHERE id = ?', (generation_id,))

            # Delete file if requested and exists
            if delete_file and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    print(f"[Database] Deleted file: {file_path}")
                except Exception as e:
                    print(f"[Database] Warning: Could not delete file {file_path}: {str(e)}")

            print(f"[Database] Deleted generation: {generation_id}")
            return True

    except Exception as e:
        print(f"[Database] Error deleting generation: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def mark_downloaded(generation_id: str) -> bool:
    """Mark a generation as downloaded"""
    try:
        with get_db_connection() as conn:
            conn.execute('UPDATE generations SET downloaded = 1 WHERE id = ?', (generation_id,))
        print(f"[Database] Marked as downloaded: {generation_id}")
        return True
    except Exception as e:
        print(f"[Database] Error marking as downloaded: {str(e)}")
        return False


def mark_favorited(generation_id: str, favorited: bool = True) -> bool:
    """Mark a generation as favorited or unfavorited"""
    try:
        with get_db_connection() as conn:
            conn.execute('UPDATE generations SET favorited = ? WHERE id = ?',
                        (1 if favorited else 0, generation_id))
        status = "favorited" if favorited else "unfavorited"
        print(f"[Database] Marked as {status}: {generation_id}")
        return True
    except Exception as e:
        print(f"[Database] Error marking as favorited: {str(e)}")
        return False


def cleanup_old_generations(
    image_retention_days: int = 7,
    video_retention_days: int = 2,
    delete_files: bool = True
) -> Dict[str, int]:
    """
    Clean up old generations based on retention policies

    Args:
        image_retention_days: Days to keep image generations
        video_retention_days: Days to keep video generations
        delete_files: Whether to delete the actual files

    Returns:
        Dictionary with cleanup statistics
    """
    stats = {
        'deleted_count': 0,
        'files_deleted': 0,
        'errors': 0
    }

    try:
        image_cutoff = (datetime.now() - timedelta(days=image_retention_days)).isoformat()
        video_cutoff = (datetime.now() - timedelta(days=video_retention_days)).isoformat()

        with get_db_connection() as conn:
            # Get generations to delete (not favorited, not downloaded, older than retention)
            cursor = conn.execute('''
                SELECT id, file_path, type FROM generations
                WHERE favorited = 0
                  AND downloaded = 0
                  AND (
                    (type IN ('txt2img', 'img2img', 'img2txt', 'extras') AND created_at < ?)
                    OR
                    (type = 'txt2vid' AND created_at < ?)
                  )
            ''', (image_cutoff, video_cutoff))

            rows = cursor.fetchall()

            for row in rows:
                gen_id = row['id']
                file_path = row['file_path']
                gen_type = row['type']

                # Delete from database
                conn.execute('DELETE FROM generations WHERE id = ?', (gen_id,))
                stats['deleted_count'] += 1

                # Delete file if requested
                if delete_files and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        stats['files_deleted'] += 1
                        print(f"[Cleanup] Deleted {gen_type}: {file_path}")
                    except Exception as e:
                        print(f"[Cleanup] Warning: Could not delete file {file_path}: {str(e)}")
                        stats['errors'] += 1

        print(f"[Cleanup] Deleted {stats['deleted_count']} generations, {stats['files_deleted']} files")

    except Exception as e:
        print(f"[Cleanup] Error during cleanup: {str(e)}")
        import traceback
        traceback.print_exc()
        stats['errors'] += 1

    return stats


def get_storage_stats() -> Dict[str, Any]:
    """Get storage statistics"""
    try:
        with get_db_connection() as conn:
            # Total counts by type
            cursor = conn.execute('''
                SELECT type, COUNT(*) as count, SUM(file_size) as total_size
                FROM generations
                GROUP BY type
            ''')

            stats = {
                'by_type': {},
                'total_count': 0,
                'total_size': 0
            }

            for row in cursor.fetchall():
                gen_type = row['type']
                count = row['count']
                total_size = row['total_size'] or 0

                stats['by_type'][gen_type] = {
                    'count': count,
                    'size_bytes': total_size,
                    'size_mb': round(total_size / (1024 * 1024), 2)
                }

                stats['total_count'] += count
                stats['total_size'] += total_size

            stats['total_size_mb'] = round(stats['total_size'] / (1024 * 1024), 2)
            stats['total_size_gb'] = round(stats['total_size'] / (1024 * 1024 * 1024), 2)

            return stats

    except Exception as e:
        print(f"[Database] Error getting storage stats: {str(e)}")
        return {'error': str(e)}


# Initialize database on module import
if not os.path.exists(DB_PATH):
    init_db()
