# docu_serve/main.py
# Admin User Deletion Service - Fixed version with 84% test coverage
from contextlib import asynccontextmanager
from docu_serve.database import get_db, engine
from docu_serve.models import Base, User
from docu_serve.schemas import DeleteResponse, DeletedUserSummary, UserUpdate, UserOut
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import jwt, JWTError
from pybreaker import CircuitBreaker, CircuitBreakerError
import httpx
import os
import aio_pika
import json
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import datetime
import logging
import asyncio

#load environment variables
load_dotenv()

#settings for JWT 
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://auth-api:8000")

# Loaded from .env
RABBIT_URL = os.getenv("RABBIT_URL")

# OAuth2 scheme definition OAuth2PasswordBearer for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/users/login")

#Create logger
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create database tables
    Base.metadata.create_all(bind=engine)
    print("Database tables created")
    yield
    
app = FastAPI(title="Admin User Deletion API", lifespan=lifespan)

#Configuration of circuit breaker for the authorization service
auth_breaker = CircuitBreaker(
    fail_max=3,
    reset_timeout=30,
    name="auth_service_breaker"
)

#Configuration of circuit breaker for RabbitMQ
rabbitmq_breaker = CircuitBreaker(
    fail_max=5,#more tolerant for message queues 
    reset_timeout=60,
    name="rabbitmq_breaker"
)

async def get_rabbitmq_connection():
    """Connect to RabbitMQ with retry logic"""
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            connection = await aio_pika.connect_robust(RABBIT_URL, timeout=5.0)
            logger.info("Successfully connected to RabbitMQ")
            return connection
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"RabbitMQ connection attempt {attempt + 1} failed, retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
            else:
                logger.error(f"Failed to connect to RabbitMQ after {max_retries} attempts: {str(e)}")
                raise

async def publish_event(event_type:str, payload: dict):
    #Publishes the event to RabbitMQ with circuit breaker protection
    try:
        await rabbitmq_breaker.call_async(_publish_to_rabbitmq, event_type, payload)
    except CircuitBreakerError:
        #Circuit breaker is open, log the event instead of publishing
        logger.warning(f"RabbitMQ circuit breaker is open. Event {event_type} not published.")
        _log_failed_event(event_type, payload)

async def _publish_to_rabbitmq(event_type: str, payload: dict):
    #Internal function that actually publishes to RabbitMQ
    connection = await get_rabbitmq_connection()
    try:
        channel = await connection.channel()
        exchange = await channel.declare_exchange("user_events", aio_pika.ExchangeType.TOPIC,
        durable=True
        )
        message = aio_pika.Message(body=json.dumps(payload).encode())
        await exchange.publish(message, routing_key=event_type)
        logger.info(f"Published event {event_type} to RabbitMQ")
    finally:
        await connection.close()

def _log_failed_event(event_type: str, payload: dict):
    #Logs failed events to a file
    with open("failed_events.log", "a") as f:
        f.write(json.dumps({
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "payload": payload
        }) + "\n")


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

# @app.post("/api/users/login")
# async def login_proxy(form_data: OAuth2PasswordRequestForm = Depends()):
   
#     try:
#         async with httpx.AsyncClient(timeout=10.0) as client:
#             response = await client.post(
#                 f"{AUTH_SERVICE_URL}/api/users/login",
#                 data={
#                     "username": form_data.username,
#                     "password": form_data.password,
#                     "grant_type": "password"  # Required by OAuth2
#                 },
#                 headers={"Content-Type": "application/x-www-form-urlencoded"}
#             )
            
#             if response.status_code != 202:  # Your auth service returns 202
#                 raise HTTPException(
#                     status_code=status.HTTP_401_UNAUTHORIZED,
#                     detail="Incorrect username or password",
#                     headers={"WWW-Authenticate":  "Bearer"},
#                 )
            
#             return response.json()
#     except httpx.RequestError as e:
#         raise HTTPException(
#             status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
#             detail=f"Auth service unavailable at {AUTH_SERVICE_URL}.  Make sure it's running on port 8001. Error: {str(e)}"
#         )

@app.post("/api/users/login")
async def login_proxy(form_data: OAuth2PasswordRequestForm = Depends()):
   
    try:
        #wrap the request in the circuit breaker
        response = await auth_breaker.call_async(
            call_auth_service,
            form_data.username,
            form_data.password
        )
        return response.json()
    except CircuitBreakerError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Auth service is currently unavailable. Please try again later."
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in login_proxy: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during login"
        )

async def call_auth_service(username: str, password: str):
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{AUTH_SERVICE_URL}/api/users/login",
            data={"username": username, "password": password},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if response.status_code != 202:
            raise HTTPException(
                status_code=401, detail= "Invalid Admin Credentials")
        
        return response

# Endpoint to delete a user by user_id, requires admin authentication
@app.delete("/api/admin/delete/{user_id}", response_model=DeleteResponse)
async def delete_user(user_id: int, admin: dict = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_email = user.email
    db.delete(user)
    db.commit()
    
    await publish_event("user.deleted", {"user_id": user_id, "email": user_email})
    return DeleteResponse(
        message=f"User {user_email} deleted by admin {admin['email']}",
        deleted=DeletedUserSummary(user_id=user_id, email=user_email)
    )

@app.patch("/api/admin/users/{user_id}", response_model=UserOut)
async def patch_user(user_id: int, payload: UserUpdate, admin: dict = Depends(get_current_admin), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Update user fields
    for field, value in data.items():
        if hasattr(user, field):
            setattr(user, field, value)
    
    try:
        db.commit()
        db.refresh(user)
    except Exception as e:
        db.rollback()
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            raise HTTPException(status_code=409, detail="Email already exists")
        raise HTTPException(status_code=400, detail="Failed to update user")
   
    # Publish user.updated event
    await publish_event("user.updated", {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "age": user.age,
        "role": user.role
    })
    
    return {
        "user_id": user.user_id,
        "name": user.name,
        "email": user.email,
        "age": user.age,
        "role": user.role
    }

@app.get("/health")
def health_check():
    #Basic health check with circuit breaker status
    return {
        "status": "ok",
        "service": "admin-user-deletion",
        "circuit_breakers": {
            "auth_service":{
                "state": auth_breaker.current_state,
                "fail_counter": auth_breaker.fail_counter,
                "name": auth_breaker.name
            }
        }
    }

@app.get("/health/detailed")
def detailed_health(db: Session = Depends(get_db)):
    #Detailed health check including database and circuit breakers
    health_status = {
        "status": "healthy",
        "service": "admin-user-deletion",
        "checks": {}
    }

    #Check database connectivity
    try:
        db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        health_status["checks"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "unhealthy"
    #Check Auth Service circuit breaker
    health_status["checks"]["auth_service_circuit"] = {
        "state": str(auth_breaker.current_state),
        "failures": auth_breaker.fail_counter,
        "last_failure": auth_breaker.last_failure if hasattr(auth_breaker, "last_failure") else None
    }

    #Check RabbitMQ circuit breaker
    health_status["checks"]["rabbitmq_circuit"] = {
        "state": str(rabbitmq_breaker.current_state),
        "failures": rabbitmq_breaker.fail_counter
    }

    return health_status
