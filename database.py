import sqlite3
import json
import os

DATABASE_FILE = 'bizstarter.db'
ASSESSMENT_MESSAGES_JSON_PATH = 'assessment_messages.json' # Path to the original JSON

def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row # This allows accessing columns by name
    return conn

def init_db(app):
    """
    Initializes the database by creating tables and seeding initial data
    from the assessment_messages.json file if the table is empty.
    """
    with app.app_context():
        conn = get_db_connection()
        cursor = conn.cursor()

        # Create assessment_messages table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS assessment_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                risk_level TEXT UNIQUE NOT NULL,
                status TEXT NOT NULL,
                caption TEXT NOT NULL,
                status_class TEXT NOT NULL,
                dscr_status TEXT NOT NULL
            );
        ''')

        # Check if the table is empty and seed it from the JSON file
        cursor.execute('SELECT COUNT(*) FROM assessment_messages')
        if cursor.fetchone()[0] == 0:
            print(f"Seeding assessment_messages table from {ASSESSMENT_MESSAGES_JSON_PATH}...")
            try:
                with open(ASSESSMENT_MESSAGES_JSON_PATH, 'r') as f:
                    json_data = json.load(f)
                
                for risk_level, data in json_data.items():
                    cursor.execute('''
                        INSERT INTO assessment_messages (risk_level, status, caption, status_class, dscr_status)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (risk_level, data['status'], data['caption'], data['status_class'], data['dscr_status']))
                conn.commit()
                print("Assessment messages seeded successfully.")
            except FileNotFoundError:
                print(f"Warning: {ASSESSMENT_MESSAGES_JSON_PATH} not found. Assessment messages table might be empty.")
            except Exception as e:
                print(f"Error seeding assessment messages: {e}")
                conn.rollback()
        
        conn.close()

def get_assessment_messages():
    """Retrieves all assessment messages from the database."""
    conn = get_db_connection()
    messages = {}
    rows = conn.execute('SELECT risk_level, status, caption, status_class, dscr_status FROM assessment_messages').fetchall()
    conn.close()
    for row in rows:
        messages[row['risk_level']] = dict(row)
    return messages