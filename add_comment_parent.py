import sqlite3
from datetime import datetime

def migrate_db():
    conn = sqlite3.connect('instance/forum.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("ALTER TABLE comment ADD COLUMN parent_id INTEGER REFERENCES comment(id)")
        print("Column 'parent_id' added to 'comment' table.")
    except sqlite3.OperationalError as e:
        print(f"Skipping comment.parent_id: {e}")

    conn.commit()
    conn.close()

if __name__ == '__main__':
    migrate_db()
