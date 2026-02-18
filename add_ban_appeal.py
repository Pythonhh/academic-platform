from app import app, db
from models import User
from sqlalchemy import text

def add_ban_appeal_column():
    with app.app_context():
        # Check if column exists
        with db.engine.connect() as conn:
            # SQLite check
            result = conn.execute(text("PRAGMA table_info(user)"))
            columns = [row[1] for row in result]
            
            if 'ban_appeal_reason' not in columns:
                print("Adding ban_appeal_reason column to user table...")
                conn.execute(text("ALTER TABLE user ADD COLUMN ban_appeal_reason TEXT"))
                conn.commit()
                print("Column added successfully.")
            else:
                print("Column already exists.")

if __name__ == "__main__":
    add_ban_appeal_column()
