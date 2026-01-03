import aio_pika
import os
import asyncio
import json
from docu_serve.database import get_db
from sqlalchemy import text
from dotenv import load_dotenv

# Load environment variables based on APP_ENV
envfile = {
    "dev": ".env.dev",
    "docker": ".env.docker",
    "test": ".env.test",
}.get(os.getenv("APP_ENV", "dev"), ".env.dev")

load_dotenv(envfile, override=True)

RABBIT_URL = os.getenv("RABBIT_URL")
print(f"Worker starting with RABBIT_URL: {RABBIT_URL}")

async def main():
    try:
        print("Connecting to RabbitMQ...")
        connection = await aio_pika.connect_robust(RABBIT_URL)
        channel = await connection.channel()

        exchange = await channel.declare_exchange("user_events", aio_pika.ExchangeType.TOPIC, durable=True)

        queue = await channel.declare_queue("admin_sync_queue", durable=True)
        await queue.bind(exchange, routing_key="user.created")
        print("Listening for new user registrations...")

        async with queue.iterator() as q:
            async for message in q:
                async with message.process():
                    data = json.loads(message.body)
                    print(f"Received new user registration: {data}")
                    
                    # Use PostgreSQL via SQLAlchemy
                    db = next(get_db())
                    try:
                        db.execute(text("""
                            INSERT INTO users (user_id, name, email, age, role, hashed_password)
                            VALUES (:user_id, :name, :email, :age, :role, :hashed_password)
                            ON CONFLICT (user_id) DO NOTHING
                        """), {
                            "user_id": data["user_id"],
                            "name": data["name"],
                            "email": data["email"],
                            "age": data["age"],
                            "role": data["role"],
                            "hashed_password": "N/A"
                        })
                        db.commit()
                        print(f"User {data['email']} synced to database")
                    except Exception as e:
                        print(f"Database error: {e}")
                        db.rollback()
                    finally:
                        db.close()
    except Exception as e:
        print(f"Worker error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())