import asyncio
import json
import os
import aio_pika
from docu_serve.database import SessionLocal
from docu_serve.models import User
from dotenv import load_dotenv
from sqlalchemy. orm import Session

# Load environment variables based on APP_ENV
envfile = {
    "dev": ". env.dev",
    "docker": ".env.docker",
    "test": ".env.test",
}.get(os.getenv("APP_ENV", "dev"), ".env.dev")

load_dotenv(envfile, override=True)

RABBIT_URL = os.getenv("RABBIT_URL", "amqp://guest:guest@rabbitmq:5672/")
print(f"Worker starting with RABBIT_URL: {RABBIT_URL}")

async def connect_to_rabbitmq_with_retry():
    """Connect to RabbitMQ with retry logic"""
    max_retries = 10
    retry_delay = 3
    
    for attempt in range(max_retries):
        try:
            print(f"Attempting to connect to RabbitMQ (attempt {attempt + 1}/{max_retries})...")
            connection = await aio_pika.connect_robust(RABBIT_URL)
            print("Successfully connected to RabbitMQ")
            return connection
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Failed to connect: {e}. Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                print(f"Failed to connect to RabbitMQ after {max_retries} attempts")
                raise

async def on_message(message:  aio_pika.IncomingMessage):
    """Handle incoming user registration messages"""
    async with message.process():
        try:
            # Parse message
            data = json.loads(message.body. decode())
            print(f"Received new user registration: {data}")
            
            # Create database session
            db:  Session = SessionLocal()
            try:
                # Check if user already exists
                existing_user = db.query(User).filter(User.user_id == data['user_id']).first()
                
                if existing_user:
                    print(f"User {data['email']} already exists in database")
                else:
                    # Create new user
                    new_user = User(
                        user_id=data['user_id'],
                        name=data['name'],
                        email=data['email'],
                        age=data. get('age'),
                        hashed_password=data['hashed_password'],
                        role=data.get('role', 'user')
                    )
                    db.add(new_user)
                    db.commit()
                    print(f"User {data['email']} synced to database")
            
            except Exception as e:
                db.rollback()
                print(f"Database error: {e}")
            finally:
                db.close()
                
        except json.JSONDecodeError as e:
            print(f"Failed to parse message: {e}")
        except Exception as e:
            print(f"Error processing message: {e}")

async def main():
    """Main worker function"""
    try:
        print("Connecting to RabbitMQ...")
        
        # Connect to RabbitMQ with retry logic
        connection = await connect_to_rabbitmq_with_retry()
        channel = await connection.channel()
        
        # Declare exchange
        exchange = await channel.declare_exchange(
            "user_events",
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        
        # Declare queue
        queue = await channel.declare_queue(
            "admin_sync_queue",
            durable=True
        )
        
        # Bind queue to exchange with routing key
        await queue.bind(exchange, routing_key="user.created")
        
        print("Listening for new user registrations...")
        
        # Start consuming messages
        await queue.consume(on_message)
        
        # Keep the worker running
        await asyncio.Future()
        
    except Exception as e:
        print(f"Worker error: {e}")
        raise
    finally:
        if 'connection' in locals():
            await connection.close()

if __name__ == "__main__": 
    asyncio.run(main())