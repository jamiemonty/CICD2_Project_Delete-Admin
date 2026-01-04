import os
import time
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy. exc import OperationalError
 
# Pick env file by APP_ENV (default dev)
envfile = {
    "dev": ".env. dev",
    "docker": ".env.docker",
    "test": ".env.test",
}. get(os.getenv("APP_ENV", "dev"), ".env.dev")
 
load_dotenv(envfile, override=True)
 
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")
SQL_ECHO = os.getenv("SQL_ECHO", "false").lower() == "true"
RETRIES = int(os.getenv("DB_RETRIES", "10"))
DELAY = float(os.getenv("DB_RETRY_DELAY", "1.5"))
 
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
 
# small retry (harmless for SQLite, useful for Postgres)
engine = None
for attempt in range(RETRIES):
    try:
        engine = create_engine(
            DATABASE_URL, pool_pre_ping=True, echo=SQL_ECHO, connect_args=connect_args
        )
        with engine.connect():  # smoke test
            pass
        break
    except OperationalError as e:
        if attempt < RETRIES - 1:
            print(f"Database connection attempt {attempt + 1}/{RETRIES} failed.  Retrying in {DELAY}s...")
            time.sleep(DELAY)
        else:
            raise Exception(
                f"Could not connect to database at {DATABASE_URL} after {RETRIES} retries"
            ) from e
 
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
 
 
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()