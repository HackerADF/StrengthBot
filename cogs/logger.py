import discord
from discord.ext import commands
import aiosqlite
import json

from libs.database_utils import TranscriptDB
DB_PATH = "data/databases/tickets.db"

class TicketLogger(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return

        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute(
                "SELECT status FROM tickets WHERE channel_id = ?",
                (message.channel.id,)
            )
            row = await cur.fetchone()

        if not (row and row[0] == "open"):
            return

        attachments = []
        for att in message.attachments:
            attachments.append({
                "url": att.url,
                "filename": att.filename,
                "content_type": att.content_type
            })
        attachments_json = json.dumps(attachments) if attachments else None

        embed_list = []
        for e in message.embeds:
            try:
                embed_list.append(e.to_dict())
            except:
                pass
        embeds_json = json.dumps(embed_list) if embed_list else None

        await TranscriptDB.add_message(
            message.channel.id,
            message.author.id,
            message.content or "",
            attachments_json,
            embeds_json
        )

async def setup(bot):
    await bot.add_cog(TicketLogger(bot))
