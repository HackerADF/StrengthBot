import aiosqlite
import asyncio
import os

async def create_transcript_db():
    if os.path.exists("data/databases/transcripts.db"):
        os.remove("data/databases/transcripts.db")
        print("Existing database deleted.")
    async with aiosqlite.connect("data/databases/transcripts.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                user_id INTEGER,
                content TEXT,
                timestamp INTEGER
            )
        """)
        await db.commit()
        await db.execute("""
            CREATE TABLE IF NOT EXISTS ticket_channels (
                channel_id INTEGER PRIMARY KEY
            );
        """)
        await db.commit()
        print("New transcripts database created.")
asyncio.run(create_transcript_db())
