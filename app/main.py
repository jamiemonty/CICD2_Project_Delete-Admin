from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from dotenv import load_dotenv
import os
from .schemas import UserDeleteRequest

load_dotenv()

app = FastAPI(title="Admin User Deletion API")


@app.delete("/api/admin/delete", status_code=status.HTTP_200_OK)
def delete_user(request: UserDeleteRequest):
    global users
    for user in users:
        if user["email"] == request.email:
            users = [u for u in users if u["email"] != request.email]
            return {"message": f"User with email {request.email} has been deleted."}
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")
