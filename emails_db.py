#!/usr/bin/env python3
"""
SQLite helper module for email storage and verification.
Stores pending and confirmed emails with verification tokens.
"""
import sqlite3
import os
from datetime import datetime
from typing import Optional, Dict

DEFAULT_DB = 'emails.db'


def get_connection(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    """Get a connection to the SQLite database."""
    return sqlite3.connect(db_path, check_same_thread=False)


def init_db(db_path: str = DEFAULT_DB) -> None:
    """Initialize the emails database with the required schema."""
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            token TEXT UNIQUE NOT NULL,
            confirmed INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()


def add_pending_email(email: str, token: str, db_path: str = DEFAULT_DB) -> bool:
    """
    Add a pending email with verification token to the database.
    
    Args:
        email: Email address to add
        token: Unique verification token
        db_path: Path to database file
        
    Returns:
        True if successful, False if email already exists
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    try:
        created_at = datetime.utcnow().isoformat()
        cursor.execute(
            'INSERT INTO emails (email, token, confirmed, created_at) VALUES (?, ?, 0, ?)',
            (email, token, created_at)
        )
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        # Email already exists
        conn.close()
        return False


def confirm_email(token: str, db_path: str = DEFAULT_DB) -> bool:
    """
    Confirm an email by marking it as verified using the token.
    
    Args:
        token: Verification token
        db_path: Path to database file
        
    Returns:
        True if email was confirmed, False if token not found
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute(
        'UPDATE emails SET confirmed = 1 WHERE token = ? AND confirmed = 0',
        (token,)
    )
    
    rows_affected = cursor.rowcount
    conn.commit()
    conn.close()
    
    return rows_affected > 0


def email_exists(email: str, db_path: str = DEFAULT_DB) -> bool:
    """
    Check if an email already exists in the database.
    
    Args:
        email: Email address to check
        db_path: Path to database file
        
    Returns:
        True if email exists, False otherwise
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute('SELECT 1 FROM emails WHERE email = ?', (email,))
    result = cursor.fetchone()
    conn.close()
    
    return result is not None


def get_email_by_token(token: str, db_path: str = DEFAULT_DB) -> Optional[Dict[str, any]]:
    """
    Get email record by verification token.
    
    Args:
        token: Verification token
        db_path: Path to database file
        
    Returns:
        Dictionary with email data or None if not found
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT id, email, token, confirmed, created_at FROM emails WHERE token = ?',
        (token,)
    )
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'email': row[1],
            'token': row[2],
            'confirmed': row[3],
            'created_at': row[4]
        }
    
    return None
