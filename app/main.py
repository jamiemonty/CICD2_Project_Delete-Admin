# app/main.py 
import sqlite3
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "JAMIESKEY")
ALGORITHM = "HS256"

app = FastAPI(title="Admin User Deletion API")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")

def get_current_admin(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=401, detail="Invalid token", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], audience="delete-service")
        role = payload.get("role")
        email = payload.get("sub")
        if role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        return {"email": email, "role": role}
    except JWTError:
        raise credentials_exception
    
def get_db():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn

@app.delete("/api/admin/delete/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(get_current_admin)):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return {"message": f"User {user['email']} deleted by admin {admin['email']}"}