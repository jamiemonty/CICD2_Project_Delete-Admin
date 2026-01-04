import aio_pika
import os
import asyncio
import json
import sqlite3

RABBIT_URL = os.getenv("RABBIT_URL", "amqps://ykvaygzy:Kg8o0HCEw9hRygtPpnQ3bjWv7N9KU0xZ@stingray.rmq.cloudamqp.com/ykvaygzy")

async def main():
    #Connect to RabbitMQ
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
                conn = sqlite3.connect("users.db")
                cur = conn.cursor()

                cur.execute("""
                    INSERT OR IGNORE INTO users (user_id, name, email, age, role, hashed_password)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    data["user_id"],
                    data["name"],
                    data["email"],
                    data["age"],
                    data["role"],
                    data.get("hashed_password", "N/A") # hashed_password not needed in admin DB
                ))

                conn.commit()
                conn.close()

if __name__ == "__main__":
    asyncio.run(main())