import aiosqlite
import asyncio
import os

async def create_ticket_db():
    if os.path.exists("data/databases/tickets.db"):
        os.remove("data/databases/tickets.db")
        print("Existing database deleted.")
    async with aiosqlite.connect("data/databases/tickets.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                channel_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                status TEXT NOT NULL
            );
        """)
        await db.commit()
        print("New ticket database created.")
asyncio.run(create_ticket_db())
