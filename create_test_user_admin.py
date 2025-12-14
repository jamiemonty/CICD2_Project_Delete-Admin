# create_test_user_admin.py
import sqlite3

conn = sqlite3.connect("users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    age INTEGER,
    hashed_password TEXT,
    role TEXT DEFAULT 'user'
)
""")

try:
    cursor.execute(
        "INSERT INTO users (name, email, age, role) VALUES (?, ?, ?, ?)",
        ("Test User", "test@sync.com", 25, "user")
    )
    conn.commit()
    print(f" User created in ADMIN database with ID: {cursor.lastrowid}")
except Exception as e:
    print(f"Error: {e}")

conn.close()