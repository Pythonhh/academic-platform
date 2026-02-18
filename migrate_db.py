from app import app, db
from models import User
from sqlalchemy import text

# Manually add the column to existing database
with app.app_context():
    try:
        # Check if column exists first to avoid error
        db.session.execute(text("ALTER TABLE user ADD COLUMN last_username_change DATETIME"))
        db.session.commit()
        print("Column 'last_username_change' added successfully.")
    except Exception as e:
        print(f"Column already exists or error: {e}")
