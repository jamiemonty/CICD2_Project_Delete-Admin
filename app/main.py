# app/main.py 
import sqlite3
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import os
from dotenv import load_dotenv
#load environment variables
load_dotenv()
#settings for JWT 
SECRET_KEY = os.getenv("SECRET_KEY", "JAMIESKEY")
ALGORITHM = "HS256"

app = FastAPI(title="Admin User Deletion API")
# OAuth2 scheme definition OAuth2PasswordBearer for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")
# Dependency to get current admin user from token, raises exception if not admin
def get_current_admin(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=401, detail="Invalid token", headers={"WWW-Authenticate": "Bearer"})
    try:
        #Try to decode the JWT token using the SECRET_KEY and ALGORITHM
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM], audience="delete-service")
        role = payload.get("role")
        email = payload.get("sub")
        if role != "admin":# if role is not admin, raise exception
            raise HTTPException(status_code=403, detail="Admin access required")
        return {"email": email, "role": role}
    except JWTError:
        raise credentials_exception
# Dependency to get database connection
def get_db():
    conn = sqlite3.connect("users.db")
    conn.row_factory = sqlite3.Row
    return conn
# Endpoint to delete a user by user_id, requires admin authentication
@app.delete("/api/admin/delete/{user_id}")
def delete_user(user_id: int, admin: dict = Depends(get_current_admin)):# get admin user from token
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

@app.patch("/api/admin/update/{user_id}")
