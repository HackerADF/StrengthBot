import os
import aiosqlite
import time

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "..", "data", "databases", "transcripts.db")

class TranscriptDB:
    @staticmethod
    async def add_message(channel_id: int, user_id: int, content: str):
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT INTO messages (channel_id, user_id, content, timestamp) VALUES (?, ?, ?, ?)",
                (channel_id, user_id, content, int(time.time()))
            )
            await db.commit()

    @staticmethod
    async def get_messages(channel_id: int):
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT user_id, content, timestamp FROM messages WHERE channel_id = ? ORDER BY id ASC",
                (channel_id,)
            )
            rows = await cursor.fetchall()
            return rows

    @staticmethod
    async def clear_messages(channel_id: int):
        """Delete all transcript messages for that channel"""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("DELETE FROM messages WHERE channel_id = ?", (channel_id,))
            await db.commit()

    @staticmethod
    async def register_ticket_channel(channel_id: int):
        """Add a channel to the persistent list if it isn't already registered."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "INSERT OR IGNORE INTO ticket_channels (channel_id) VALUES (?)",
                (channel_id,)
            )
            await db.commit()

    @staticmethod
    async def remove_ticket_channel(channel_id: int):
        """Remove when ticket is deleted."""
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                "DELETE FROM ticket_channels WHERE channel_id = ?",
                (channel_id,)
            )
            await db.commit()

    @staticmethod
    async def get_all_ticket_channels():
        """Return all channels that should load persistent transcript buttons on startup."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute("SELECT channel_id FROM ticket_channels")
            rows = await cursor.fetchall()
            return [r[0] for r in rows]

    @staticmethod
    async def ticket_exists(channel_id: int):
        """Check if ticket is registered."""
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT 1 FROM ticket_channels WHERE channel_id = ?", (channel_id,)
            )
            return await cursor.fetchone() is not None
