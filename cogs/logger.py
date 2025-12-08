import os

import discord
from discord.ext import commands
import aiosqlite

from libs.database_utils import TranscriptDB

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "..", "data", "databases", "tickets.db")

class TicketLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "SELECT status FROM tickets WHERE channel_id = ?",
                (message.channel.id,)
            )
            row = await cursor.fetchone()

        if row and row[0] == "open":
            await TranscriptDB.add_message(
                message.channel.id,
                message.author.id,
                message.content
            )

async def setup(bot):
    await bot.add_cog(TicketLogger(bot))
