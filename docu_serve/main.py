# app/main.py 
import sqlite3
from fastapi import FastAPI, Depends, HTTPException, status
from app.schemas import DeleteResponse, UserUpdate, UserOut, DeletedUserSummary
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
import os
import aio_pika
import json
from dotenv import load_dotenv
#load environment variables
load_dotenv()
#settings for JWT 
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"

# Loaded from .env.rabbit (in Codespaces) 
RABBIT_URL = os.getenv("RABBIT_URL")


app = FastAPI(title="Admin User Deletion API")

async def publish_event(event_type:str, payload: dict):
    #Publishes the event to RabbitMQ
    try: 
        connection = await aio_pika.connect_robust(RABBIT_URL)
        channel = await connection.channel()
        exchange = await channel.declare_exchange(
            "user_events", aio_pika.ExchangeType.TOPIC, durable=True
        )
        message = aio_pika.Message(body=json.dumps(payload).encode())
        await exchange.publish(message, routing_key=event_type)
        print(f"Published event {event_type} with payload {payload}")
        await connection.close()
    except Exception as e:
        print(f"Failed to publish event {event_type}: {e}")

# OAuth2 scheme definition OAuth2PasswordBearer for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="https://automatic-pancake-v4pj9649wqvfx6pg-8001.app.github.dev/api/users/login")

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
@app.delete("/api/admin/delete/{user_id}", response_model=DeleteResponse)
async def delete_user(user_id: int, admin: dict = Depends(get_current_admin)):# get admin user from token
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cursor.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    await publish_event("user.deleted", {"user_id": user_id, "email": user["email"]})
    return DeleteResponse(
        message=f"User {user['email']} deleted by admin {admin['email']}",
        deleted=DeletedUserSummary(user_id=user_id, email=user["email"])
    )

@app.patch("/api/admin/users/{user_id}", response_model=UserOut)
async def patch_user(user_id: int, payload: UserUpdate, admin: dict = Depends(get_current_admin)):
    conn = get_db()
    cursor = conn.cursor()
    #Check if the user exists in the database.
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    #Collect only the fields that are set in the request json (patch/partial update section)
    data = payload.model_dump(exclude_unset=True)

    if not data:
        conn.close()
        raise HTTPException(status_code=400, detail="No fields to update")
    #Build parameterised UPDATE query to avoid SQL injection
    set_parts = []
    values = []
    for field in ("name", "email", "age", "role"):
        if field in data:
            set_parts.append(f"{field}=?")
            values.append(data[field])

    sql = f"UPDATE users SET {', '.join(set_parts)} WHERE user_id=?"
    try:
        cursor.execute(sql, (*values, user_id))
        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        conn.close()
    #Handle if user tries to update to an email that already exists
        if "UNIQUE constraint failed: users.email" in str(e):
            raise HTTPException(status_code=409, detail="Email already exists")
        raise HTTPException(status_code=400, detail="Failed to update user")
   
    #return the updated user
    cursor.execute("SELECT user_id, name, email, age, role FROM users WHERE user_id=?", (user_id,))
    updated_user = cursor.fetchone()
    conn.close() 
    #publish user.updated event
    await publish_event("user.updated", {
        "user_id": updated_user["user_id"],
        "name": updated_user["name"],
        "email": updated_user["email"],
        "age": updated_user["age"],
        "role": updated_user["role"]
    })
    return {
        "user_id": updated_user["user_id"],
        "name": updated_user["name"],
        "email": updated_user["email"],
        "age": updated_user["age"],
        "role": updated_user["role"]
    }

