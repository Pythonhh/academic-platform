import sqlite3

def fix_database():
    conn = sqlite3.connect('instance/forum.db')
    cursor = conn.cursor()
    
    # 1. Add profile_image to user table
    try:
        cursor.execute("ALTER TABLE user ADD COLUMN profile_image VARCHAR(150) DEFAULT 'default.png'")
        print("Column 'profile_image' added to 'user' table.")
    except sqlite3.OperationalError as e:
        print(f"Skipping user.profile_image: {e}")

    # 2. Add reported_post_id to report table
    try:
        cursor.execute("ALTER TABLE report ADD COLUMN reported_post_id INTEGER")
        print("Column 'reported_post_id' added to 'report' table.")
    except sqlite3.OperationalError as e:
        print(f"Skipping report.reported_post_id: {e}")

    # 3. Add reported_user_id to report table (just in case it was missing from initial creation if using old schema)
    # The Report table was created recently so it might be fine, but let's be safe if it was created before the split
    try:
        cursor.execute("ALTER TABLE report ADD COLUMN reported_user_id INTEGER")
        print("Column 'reported_user_id' added to 'report' table.")
    except sqlite3.OperationalError as e:
        print(f"Skipping report.reported_user_id: {e}")

    conn.commit()
    conn.close()
    print("Database schema update completed.")

if __name__ == '__main__':
    fix_database()
