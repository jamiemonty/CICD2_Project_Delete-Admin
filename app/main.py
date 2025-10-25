# from fastapi import FastAPI, Depends, HTTPException, status
# from fastapi.security import OAuth2PasswordBearer
# from jose import JWTError, jwt
# from dotenv import load_dotenv
# import os
# from .schemas import UserDeleteRequest

# load_dotenv()

# app = FastAPI(title="Admin User Deletion API")

# SECRET_KEY = os.getenv("SECRET_KEY", "JAMIESKEY")
# ALGORITHM = "HS256"

# oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# def get_current_admin(token: str = Depends(oauth2_scheme)):
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,
#         detail="Could not validate credentials",
#         headers={"WWW-Authenticate": "Bearer"},
#     )
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         role: bool = payload.get("role")
#         email: str = payload.get("sub")
#         if role != "admin": 
#             raise HTTPException(status_code=403, detail = "Admin access required")
#         return {"email": email, "role": role}
#     except JWTError:
#         raise credentials_exception
    

# @app.delete("/api/admin/delete/{user_id}", status_code=status.HTTP_200_OK)
# def delete_user(user_id: int, admin: dict = Depends(get_current_admin)):
#     user = next((u for u in users if u["user_id"] == user_id), None)
#     if not user:
#         raise HTTPException(status_code=404, detail="User not found")
#     users.remove(user)
#     return {"message": f"User with email {request.email} has been deleted by {admin['email']}."}

# app/main.py 
import sqlite3
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import os

SECRET_KEY = os.getenv("SECRET_KEY", "JAMIESKEY")
ALGORITHM = "HS256"
app = FastAPI(title="Admin User Deletion API")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")
def get_current_admin(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=401, detail="Invalid token",
                                          headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
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