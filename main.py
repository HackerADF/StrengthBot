# === Standard Library Imports ===
import asyncio
import base64
import datetime
import json
import logging
import os
import io
import random
import re
import sys
import subprocess
import time
from datetime import datetime, timedelta
from io import BytesIO
from operator import truediv
from typing import Union, Optional

# === Third-Party Imports ===
import aiohttp
import aiosqlite
import discord
import requests
from charset_normalizer.md import getLogger
from discord import app_commands, ButtonStyle, Webhook
from discord.ext import commands, tasks
from discord.ui import View
from discord import FFmpegPCMAudio
from dotenv import load_dotenv

# == Local Imports ===
from libs import verbose

# === Runtime Cleanup & Signal Handling ===
import atexit

TICKET_DATABASE = "tickets.db"
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
_log = logging.getLogger("discord")

TICKETS_FILE = "data/tickets/persistent_view.json"

TICKET_LOG_CHANNEL_ID = 1446711847641157765

APPLICATIONS_CATEGORY = 1446783417457836117
BUG_REPORTS_CATEGORY = 1446711847339425902
USER_REPORTS_CATEGORY = 1446711847339425902
APPEALS_CATEGORY = 1446711847339425902
SUPPORT_CATEGORY = 1446711847339425902
QUESTIONS_CATEGORY = 1446711847339425902
OTHER_CATEGORY = 1446711847339425902


intents = discord.Intents.all()
bot = commands.AutoShardedBot(command_prefix="!", intents=intents,
                              activity=discord.Streaming(name='ADF coding me!', url="https://nauticalhosting.org"))
# Helper functions
def load_ticket_channels():
    if not os.path.exists(TICKETS_FILE):
        return []
    with open(TICKETS_FILE, "r") as f:
        return json.load(f)

def save_ticket_channels(channels):
    with open(TICKETS_FILE, "w") as f:
        json.dump(channels, f)
def slugify(user: discord.User) -> str:
    name = user.name.lower().replace(" ", "-").replace(".", "-")

    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    cleaned = "".join(c for c in name if c in allowed)

    return cleaned[:20]  # Keep usernames short for channel names

def map_reason(user: discord.User, reason: str):
    """
    Returns:
    {
        "channel_name": "application-{user}",
        "category_id": 123456789012345678
    }
    """

    username = slugify(user)
    reason = reason.lower().strip()

    mappings = {
        "become a team member": ("application", APPLICATIONS_CATEGORY),
        "staff application": ("application", APPLICATIONS_CATEGORY),

        "report a bug": ("bug-report", BUG_REPORTS_CATEGORY),
        "bug": ("bug-report", BUG_REPORTS_CATEGORY),

        "report a user": ("user-report", USER_REPORTS_CATEGORY),

        "appeal": ("appeal", APPEALS_CATEGORY),
        "ban appeal": ("appeal", APPEALS_CATEGORY),

        "ask a question": ("question", QUESTIONS_CATEGORY),

        "need support": ("support", SUPPORT_CATEGORY),
        "support": ("support", SUPPORT_CATEGORY),
    }

    if reason in mappings:
        base, cat_id = mappings[reason]
        return {
            "channel_name": f"{base}-{username}",
            "category_id": cat_id
        }

    for key, mapping in mappings.items():
        if key in reason:
            base, cat_id = mapping
            return {
                "channel_name": f"{base}-{username}",
                "category_id": cat_id
            }
    return {
        "channel_name": f"other-{username}",
        "category_id": OTHER_CATEGORY
    }

async def load_extensions(folder: str, package: str = "cogs"):
    """Recursively load all cogs inside the given folder."""
    for root, _, files in os.walk(folder):
        for file in files:
            if file.endswith(".py"):
                relative_path = os.path.relpath(os.path.join(root, file), folder)
                module = relative_path.replace(os.sep, ".")[:-3]  # strip .py
                ext = f"{package}.{module}"
                try:
                    await bot.load_extension(ext)
                    print(f"✅ Loaded {ext}")
                except Exception as e:
                    print(f"❌ Failed to load {ext}: {e}")

async def getTicketCreator(ticket: discord.TextChannel) -> discord.User:
    async with aiosqlite.connect(TICKET_DATABASE) as db:
        cursor = await db.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (ticket.id,))
        result = await cursor.fetchone()

        return await bot.fetch_user(result[0])

async def getUserTicketCount(user: discord.User) -> int:
    async with aiosqlite.connect(TICKET_DATABASE) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM tickets WHERE user_id = ?", (user.id,))
        result = await cursor.fetchone()

        return int(result[0])

class VerificationChallengeView(discord.ui.View):
    def __init__(self, user: discord.Member, code: int):
        super().__init__(timeout=300)
        self.user = user
        self.code = code
    @discord.ui.button(label="Enter Code", style=discord.ButtonStyle.gray, custom_id="verify_code")
    async def verify_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("This challenge isn't for you.", ephemeral=True)
        modal = VerificationModal(self.code)
        await interaction.response.send_modal(modal)
class VerificationModal(discord.ui.Modal, title="Enter Verification Code"):
    def __init__(self, code: int):
        super().__init__()
        self.code = code
        self.code_input = discord.ui.TextInput(
            label="Verification Code",
            placeholder="Enter the 6-digit code...",
            required=True,
            max_length=6
        )
        self.add_item(self.code_input)
    async def on_submit(self, interaction: discord.Interaction):
        guild_id = 1446711845787275404
        if self.code_input.value == str(self.code):
            guild = await interaction.client.fetch_guild(guild_id)
            if guild:
                role = guild.get_role(1446711845787275409)
                if role:
                    server = bot.get_guild(guild_id)
                    member = server.get_member(interaction.user.id)
                    await member.add_roles(role)
                    await edit_verification_embed(member, "Verified")
                    await interaction.response.send_message("✅ Verification successful!",
                                                            ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Role not found.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Couldn't find the server. Please try again later.",
                                                        ephemeral=True)
        else:
            await interaction.response.send_message("❌ Incorrect code. Please try again.", ephemeral=True)
class VerificationView(discord.ui.View):
    def __init__(self, bot, guild_id):
        super().__init__(timeout=None)
    @discord.ui.button(label="Verify", style=discord.ButtonStyle.blurple, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild  # Get the guild from the interaction
        member = guild.get_member(interaction.user.id)
        verify_role_id = 1414392497383149639
        verify_role = guild.get_role(verify_role_id)
        if verify_role in member.roles:
            channel = discord.utils.get(guild.text_channels, id=1414393765350604800)
            if channel:
                await channel.send(f"🚫 {member.mention} tried to verify but already has the verified role.")
            await interaction.response.send_message(
                "⚠️ |  Sorry, a raid has been detected, and you were flagged. Please check the channel list for the alternate verification channel, or wait for this raid to be resolved.",
                ephemeral=True)
            return
        await interaction.response.send_message("📩 Check your DMs for the verification challenge!", ephemeral=True)
        verification_code = random.randint(100000, 999999)
        embed = discord.Embed(
            title="Verification Challenge",
            description=f"To verify your identity, please enter your Minecraft username and the following code in the challenge panel:\n\n`{verification_code}`",
            color=discord.Color.blue()
        )
        embed.set_footer(text="This verification code expires in 5 minutes.")
        try:
            await interaction.user.send(embed=embed,
                                        view=VerificationChallengeView(interaction.user, verification_code))
        except discord.Forbidden:
            await interaction.followup.send("⚠ Unable to send DM. Please enable direct messages and try again.",
                                            ephemeral=True)
async def edit_verification_embed(member, status):
    joinLogChannel = discord.utils.get(member.guild.text_channels, id=1446711847641157767)
    welcomeChannel = discord.utils.get(member.guild.text_channels, id=1446762688947552386)
    if joinLogChannel:
        verified_embed = discord.Embed(title=f"Member {member.name} has been verified.",
                                       description=f"» **Member**: {member.name} **[{member.id}]** ({member.mention})\n» **Account Created**: {member.created_at}\n\n**Verification**:\n> **Status**: Verified ✅",
                                       colour=discord.Color.green())  # Change the color to Green when verified
        verified_embed.set_author(name="Security")
    if welcomeChannel:
        await welcomeChannel.send(f"👋 |  {member.mention} has successfully joined & verified! - Welcome!")
# ====================================================================================================
class TicketDropdown(discord.ui.Select):
    def __init__(self, parent_view):
        self.parent_view = parent_view

        options = [
            discord.SelectOption(label="Report a User", emoji="⛑️", value="report_user"),
            discord.SelectOption(label="Report a Bug", emoji="🐛", value="report_bug"),
            discord.SelectOption(label="Ask a Question", emoji="❓", value="ask_question"),
            discord.SelectOption(label="Need Support", emoji="🧩", value="need_support"),
            discord.SelectOption(label="Staff Application", emoji="💼", value="staff_application"),
            discord.SelectOption(label="Appeal Punishment", emoji="⚠️", value="appeal_punishment"),
        ]

        super().__init__(
            placeholder="Select a support option...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        value = self.values[0]

        if value == "report_user":
            await interaction.response.send_modal(
                TicketReportModal(reason="report a user", interaction=interaction, parent_view=self.parent_view)
            )

        elif value == "report_bug":
            await interaction.response.send_modal(
                TicketBugReportModal(reason="report a bug", interaction=interaction, parent_view=self.parent_view)
            )

        elif value == "ask_question":
            await interaction.response.defer()
            await self.parent_view.create_ticket(interaction, "Ask a Question")

        elif value == "need_support":
            await interaction.response.send_modal(
                TicketSupportModal(reason="need support", interaction=interaction, parent_view=self.parent_view)
            )

        elif value == "staff_application":
            await interaction.response.send_modal(
                TicketApplicationModal(reason="Staff Application", interaction=interaction, parent_view=self.parent_view)
            )

        elif value == "appeal_punishment":
            await interaction.response.send_modal(
                TicketAppealModal(reason="Appeal Punishment", interaction=interaction, parent_view=self.parent_view)
            )

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketDropdown(self))

    async def create_ticket(self, interaction: discord.Interaction, reason: str, answers: str = []):
        if not interaction.response.is_done():
            await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user
        staff = discord.utils.get(guild.roles, id=1446763200715690045)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),  # Hide for everyone
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True),  # Allow user
            staff: discord.PermissionOverwrite(view_channel=True, send_messages=True)  # Allow user
        }
        result = map_reason(user, reason)
        channel_name = result["channel_name"]
        category_id = result["category_id"]
        channel = await guild.create_text_channel(
            name=channel_name,
            category=guild.get_channel(category_id),
            overwrites=overwrites
        )
        async with aiosqlite.connect(TICKET_DATABASE) as db:
            await db.execute("INSERT INTO tickets (channel_id, user_id, reason, status) VALUES (?, ?, ?, ?)",
                             (channel.id, user.id, reason, "open"))
            await db.commit()

        ticket_channels = load_ticket_channels()
        if channel.id not in ticket_channels:
            ticket_channels.append(channel.id)
            save_ticket_channels(ticket_channels)
        user_ticket_count = await getUserTicketCount(user)
        embed = discord.Embed(
            description=f"# {user.mention}\nUser ticket **#{user_ticket_count}**\n\n# __{reason.capitalize()}__\n\n## **Thank you for contacting support.**\n\n## **Please provide any evidence you have below**",
            color=0x21d391
        )

        embed.set_footer(text="Powered by ADF Industries",
                         icon_url=bot.user.avatar.url)
        embed.set_author(name="✅ Ticket Created! - Welcome to the support channel.")
        await channel.send("<@&1346650884838260860>", embed=embed)

        answers = answers

        if reason.lower() == "appeal punishment":
            embed = discord.Embed(
                description=(
                    f"**What is your Minecraft username?**\n```{answers['name']}```\n"
                    f"**Do you play on Java or Bedrock?**\n```{answers['version ']}```\n"
                    f"**Why did you receive your punishment?**\n```{answers['punishment_reason'] if answers['punishment_reason'] else 'Not answered.'}```\n"
                    f"**Why should your punishment be revoked?**\n```{answers['revoke_reason'] if answers['revoke_reason'] else 'No answer provided.'}```\n"
                ),
            )
            await channel.send(embed=embed, view=TicketPanelView(channel))

        elif reason.lower() == "need support":
            embed = discord.Embed(title="Please answer the following questions:",
                                  description=(
                                      f"**What is your name?**\n```{answers['name']}```\n"
                                      f"**How can we assist you today?**\n```{answers['support_reason']}```\n"
                                  ))
            await channel.send(embed=embed, view=TicketPanelView(channel))
        elif reason.lower() == "report a bug":
            embed = discord.Embed(
                description=(
                    f"**What is your Minecraft username?**\n```{answers['name']}```\n"
                    f"**What bug are you reporting?**\n```{answers['bug']}```\n"
                    f"*Steps to re-create the bug:**\n```{answers['steps'] if answers['steps'] else 'No answered provided.'}```\n"
                    f"**How did you find this bug?**\n```{answers['how']}```\n"
                    f"**Any additional information?**:\n```{answers['additional'] if answers['additional'] else 'No answer provided.'}```"
                )
            )
            await channel.send(embed=embed, view=TicketPanelView(channel))
        elif reason.lower() == "report a user":
            embed = discord.Embed(
                description=(
                    f"**What is your name?**\n```{answers['name']}```\n"
                    f"**Who are you reporting?**\n```{answers['reported_user']}```\n"
                    f"**Why are you reporting them?**\n```{answers['reason'] if answers['reason'] else 'No answered provided.'}```\n"
                    f"**Do you have Evidence?**\n```{answers['has_proof']}```\n"
                    f"**Any additional information?**:\n```{answers['extra'] if answers['extra'] else 'No answer provided.'}```"
                )
            )
            await channel.send(embed=embed, view=TicketPanelView(channel))
        elif reason.lower() == "staff application":
            embed = discord.Embed(
                description=(
                    f"**What is Minecraft username?**\n```{answers['name']}```\n"
                    f"**Why do you want to join the staff team?**\n```{answers['why']}```\n"
                    f"**Do you have past experience?**\n```{answers['experience'] if answers['experience'] else 'No answered provided.'}```\n"
                    f"**What makes you a better candidate?**\n```{answers['candidate']}```\n"
                    f"**Any additional information?**:\n```{answers['additional'] if answers['additional'] else 'No answer provided.'}```"
                )
            )
            await channel.send(embed=embed, view=TicketPanelView(channel))
        else:
            return
        embed = discord.Embed(description=f"Opened a new ticket: {channel.mention}",
                              colour=0x21d391)

        embed.set_author(name="Ticket")

        embed.set_footer(text="Powered by ADF Industries",
                         icon_url=bot.user.avatar.url)
        await interaction.followup.send(embed=embed, ephemeral=True)

class TicketPanelView(discord.ui.View):
    def __init__(self, ticket_channel: discord.TextChannel):
        super().__init__(timeout=None)  # Persistent view, no timeout
        self.ticket_channel = ticket_channel

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.red,
        emoji="🔒",
        custom_id="ticket_close"
    )
    async def close_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel.id != self.ticket_channel.id:
            await interaction.response.send_message(
                "This button isn't for this channel.",
                ephemeral=True
            )
            return

        ticket_channels = load_ticket_channels()
        if self.ticket_channel.id in ticket_channels:
            ticket_channels.remove(self.ticket_channel.id)
            save_ticket_channels(ticket_channels)
        creator = await getTicketCreator(interaction.channel)
        await log_ticket_closure(bot, self.ticket_channel, creator, interaction.user)
        await interaction.response.send_message("Closing ticket...", ephemeral=True)
        await self.ticket_channel.delete()

    @discord.ui.button(
        label="Close with Reason",
        style=discord.ButtonStyle.red,
        emoji="🔒",
        custom_id="ticket_close_reason"
    )
    async def close_reason_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.channel.id != self.ticket_channel.id:
            await interaction.response.send_message(
                "This button isn't for this channel.",
                ephemeral=True
            )
            return

        modal = CloseReasonModal(self.ticket_channel)
        await interaction.response.send_modal(modal)
class CloseReasonModal(discord.ui.Modal, title="Close Ticket With Reason"):
    reason = discord.ui.TextInput(
        label="Reason for closing the ticket",
        style=discord.TextStyle.paragraph,
        placeholder="Enter the reason here...",
        required=True,
        max_length=500
    )
    def __init__(self, channel: discord.TextChannel):
        super().__init__()
        self.channel = channel
    async def on_submit(self, interaction: discord.Interaction):
        verbose.send(f"Ticket {self.channel.id} closed with reason: {self.reason.value}")

        await interaction.response.send_message(
            f"Ticket closed with reason:\n```{self.reason.value}```",
            ephemeral=True
        )
        ticket_channels = load_ticket_channels()
        if self.channel.id in ticket_channels:
            ticket_channels.remove(self.channel.id)
            save_ticket_channels(ticket_channels)
        creator = await getTicketCreator(interaction.channel)
        await log_ticket_closure(bot, self.channel, interaction.user, creator, self.reason.value)
        await asyncio.sleep(5)
        await self.channel.delete()
async def log_ticket_closure(bot: commands.Bot, channel: discord.TextChannel, user: discord.User, creator: discord.User, reason: Optional[str] = None):
    log_channel = bot.get_channel(TICKET_LOG_CHANNEL_ID)
    if not log_channel:
        verbose.send(f"Log channel with ID {TICKET_LOG_CHANNEL_ID} not found.")
        return

    timestamp = f"<t:{int(time.time())}>"
    embed = discord.Embed(colour=0x00ff80)

    embed.set_author(name="Ticket Closed")

    embed.add_field(name="<:id:1446929158419513446> Ticket ID",
                    value=f"{channel.id}",
                    inline=True)
    embed.add_field(name="<:open:1446929139767574651> Opened By",
                    value=f"{creator.mention}",
                    inline=True)
    embed.add_field(name="<:close:1446929115897925703> Closed By",
                    value=f"{user.mention}",
                    inline=True)
    embed.add_field(name="<:opentime:1446929127222280195> Open Time",
                    value=f"{timestamp}",
                    inline=True)
    embed.add_field(name="<:reason:1446929098017476841> Close Reason",
                    value=f"{reason}",
                    inline=False)

    await log_channel.send(embed=embed)
    try:
        await creator.send(content="Thanks for contacting support", embed=embed)
    except discord.Forbidden:
        pass

class TicketCloseView(View):
    def __init__(self, interaction, channel_id, ticket_creator_id):
        super().__init__()
        self.interaction = interaction  # Store the interaction for later use
        self.channel_id = channel_id
        self.ticket_creator_id = ticket_creator_id
    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle the 'Confirm' button click."""
        await self.close_ticket(interaction)
    @discord.ui.button(label="Leave Open/Cancel", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle the 'Cancel' button click."""
        await interaction.response.send_message("Ticket closure has been canceled.", ephemeral=True)
    async def close_ticket(self, interaction: discord.Interaction):
        """Function to close and archive the ticket."""
        async with aiosqlite.connect(TICKET_DATABASE) as db:
            cursor = await db.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (self.channel_id,))
            result = await cursor.fetchone()
            if not result:
                await interaction.response.send_message("This channel is not a ticket.", ephemeral=True)
                return
            ticket_creator_id = result[0]
            await db.execute(
                "UPDATE tickets SET status = 'closed' WHERE channel_id = ?",
                (self.channel_id,)
            )
            await db.commit()
            channel = interaction.channel
            user_to_remove = interaction.guild.get_member(self.ticket_creator_id)
            if user_to_remove:
                await channel.set_permissions(user_to_remove, view_channel=False)
            archive_category = discord.utils.get(interaction.guild.categories, id=1414429643003527339)
            if archive_category:
                await channel.edit(category=archive_category)
                await channel.send("🔒 This ticket has been archived and is now private.")
            else:
                await channel.send("⚠️ Archive category not found. Please check the category ID.")
            await interaction.response.send_message("Ticket has been closed and archived.", ephemeral=True)
class TicketReportModal(discord.ui.Modal, title="Player Report Form"):
    name = discord.ui.TextInput(
        label="What is your Minecraft username?",
        placeholder="Enter your Minecraft username here...",
        required=True,
        max_length=16
    )
    reportee_name = discord.ui.TextInput(
        label="Who are you reporting?",
        placeholder="Enter their Minecraft/Discord username...",
        required=True,
        max_length=18
    )
    place = discord.ui.TextInput(
        label="Where did this occur?",
        placeholder="Discord/Minecraft/Any server",
        required=True,
        max_length=20
    )
    report_reason = discord.ui.TextInput(
        label="What are you reporting them for?",
        placeholder="Please be very detailed in why you're reporting them.",
        required=True,
        max_length=1000
    )
    additional_info = discord.ui.TextInput(
        label="Any additional info?",
        placeholder="Optional",
        required=False,
        max_length=300
    )
    def __init__(self, reason: str, interaction: discord.Interaction, parent_view):
        super().__init__()
        self.reason = reason
        self.interaction = interaction
        self.parent_view = parent_view
    async def on_submit(self, interaction: discord.Interaction):
        answers = {
            "name": self.name.value,
            "reportee": self.reportee_name.value,
            "place": self.place.value,
            "reason": self.report_reason.value,
            "additional": self.additional_info.value
        }
        await self.parent_view.create_ticket(interaction, self.reason, answers)
class TicketApplicationModal(discord.ui.Modal, title="StrengthKits Staff Member Application"):
    name = discord.ui.TextInput(
        label="What is your Minecraft username?",
        placeholder="Enter your Minecraft username here...",
        required=True,
        max_length=16
    )
    why = discord.ui.TextInput(
        style=discord.TextStyle.paragraph,
        label="Why do you want to join the staff team?",
        placeholder="Explain why you wish to become a member of the StrengthKits Staff Team",
        required=True,
        max_length=1000
    )
    experience = discord.ui.TextInput(
        style=discord.TextStyle.paragraph,
        label="Do you have past experience?",
        placeholder="If you have past staff experience, not required however will help!",
        required=True,
        max_length=2000
    )
    candidate = discord.ui.TextInput(
        style=discord.TextStyle.paragraph,
        label="What makes you a better candidate?",
        placeholder="Why should we pick you over other applicants? What are your strengths? weaknesses?",
        required=True,
        max_length=1000
    )
    additional_info = discord.ui.TextInput(
        style=discord.TextStyle.paragraph,
        label="Any additional information?",
        placeholder="Optional",
        required=False,
        max_length=300
    )
    def __init__(self, reason: str, interaction: discord.Interaction, parent_view):
        super().__init__()
        self.reason = reason
        self.interaction = interaction
        self.parent_view = parent_view
    async def on_submit(self, interaction: discord.Interaction):
        answers = {
            "name": self.name.value,
            "why": self.why.value,
            "experience": self.experience.value,
            "candidate": self.candidate.value,
            "additional": self.additional_info.value

        }
        await self.parent_view.create_ticket(interaction, self.reason, answers)

class TicketSupportModal(discord.ui.Modal, title="Contact Support"):
    name = discord.ui.TextInput(
        label="What is your Minecraft username?",
        placeholder="Enter your Minecraft username here...",
        required=True,
        max_length=16
    )
    support_reason = discord.ui.TextInput(
        style=discord.TextStyle.paragraph,
        label="How can we assist you?",
        placeholder="Explain your reasoning for contacting us.",
        required=True,
        max_length=1000
    )
    def __init__(self, reason: str, interaction: discord.Interaction, parent_view):
        super().__init__()
        self.reason = reason
        self.interaction = interaction
        self.parent_view = parent_view
    async def on_submit(self, interaction: discord.Interaction):
        answers = {
            "name": self.name.value,
            "support_reason": self.support_reason.value,
        }
        await self.parent_view.create_ticket(interaction, self.reason, answers)

class TicketAppealModal(discord.ui.Modal, title="Contact Support"):
    name = discord.ui.TextInput(
        label="What is your Minecraft username?",
        placeholder="Enter your Minecraft username here...",
        required=True,
        max_length=16
    )
    version = discord.ui.TextInput(
        style=discord.TextStyle.short,
        label="Do you play on Bedrock or Java?",
        placeholder="Java | Bedrock",
        required=True,
        max_length=7
    )
    punishment_reason = discord.ui.TextInput(
        style=discord.TextStyle.paragraph,
        label="Why did you receive your punishment?",
        placeholder="Example: Unfair Advantage, Racism, Bug Abuse",
        required=True,
        max_length=50
    )
    revoke_reason = discord.ui.TextInput(
        style=discord.TextStyle.paragraph,
        label="Why should your punishment be revoked??",
        placeholder="This field should be at least 75 words, 150+ is appreciated.",
        required=True,
        max_length=1750
    )
    def __init__(self, reason: str, interaction: discord.Interaction, parent_view):
        super().__init__()
        self.reason = reason
        self.interaction = interaction
        self.parent_view = parent_view
    async def on_submit(self, interaction: discord.Interaction):
        answers = {
            "name": self.name.value,
            "version": self.version.value,
            "punishment_reason": self.punishment_reason.value,
            "revoke_reason": self.revoke_reason.value
        }
        await self.parent_view.create_ticket(interaction, self.reason, answers)

class TicketBugReportModal(discord.ui.Modal, title="Bug Report Forum"):
    name = discord.ui.TextInput(
        label="What is your Minecraft username?",
        placeholder="Enter your Minecraft username here...",
        required=True,
        max_length=16
    )
    bug = discord.ui.TextInput(
        style=discord.TextStyle.paragraph,
        label="What bug are you reporting?",
        placeholder="Describe the bug you found, and it's effects",
        required=True,
        max_length=1000
    )
    steps = discord.ui.TextInput(
        style=discord.TextStyle.paragraph,
        label="Steps to re-create the bug:",
        placeholder="A detailed explanation on how to cause/trigger the bug.",
        required=True,
        max_length=2000
    )
    how = discord.ui.TextInput(
        style=discord.TextStyle.paragraph,
        label="How did you find this bug?",
        placeholder="How did you come across it? When did it happen?",
        required=True,
        max_length=1000
    )
    additional_info = discord.ui.TextInput(
        style=discord.TextStyle.paragraph,
        label="Any additional information?",
        placeholder="Optional",
        required=False,
        max_length=300
    )
    def __init__(self, reason: str, interaction: discord.Interaction, parent_view):
        super().__init__()
        self.reason = reason
        self.interaction = interaction
        self.parent_view = parent_view
    async def on_submit(self, interaction: discord.Interaction):
        answers = {
            "name": self.name.value,
            "bug": self.bug.value,
            "steps": self.steps.value,
            "how": self.how.value,
            "additional": self.additional_info.value

        }
        await self.parent_view.create_ticket(interaction, self.reason, answers)

@bot.tree.command(name="master", description="Master command")
@app_commands.describe(
    action="Choose an action.",
)
@app_commands.choices(
    action=[
        app_commands.Choice(name="Verification Panel", value="vp"),
        app_commands.Choice(name="Informations Panel", value="ip"),
        app_commands.Choice(name="Tickets Panel", value="tp"),
        app_commands.Choice(name="Rules Panel", value="rp"),
        app_commands.Choice(name="Anti-Raid Panel", value="arp")
    ]
)
async def master(interaction: discord.Interaction, action: str):
    if interaction.user.id != 1248492933875765328:
        await interaction.response.send_message("You are not permitted to use this command", ephemeral=True)
        return
    if action == "vp":
        embed = discord.Embed(
            title="Welcome to Strength Kits",
            description=(
                "Please verify by pressing the button below to ensure you are not a bot!\n\n**⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻**\n\n"
                "> **Welcome to Strength Kits!**  \n\n"
                "```\nStrengthSMP | PvP | Free Kits\n```\n\n"
                "**Strength Kits** is a Minecraft server dedicated to providing a space for players"
                "to practice StrengthSMP! \n\n"
                "We're dedicated and trusted among many PvPers and SMP players alike.\n"
                "\n\nGet ready to experience the StrengthSMP Practice Server!"
            ),
            colour=discord.Color.blue(),
            timestamp=datetime.now()
        )
        embed.set_author(name="Verification required")
        bot_user = await bot.fetch_user(bot.user.id) # ig we have to fetch the user first
        embed.set_image(url=bot_user.banner.url)
        embed.set_thumbnail(url="https://dan.onl/images/emptysong.jpg")
        embed.set_footer(text="Powered by: ADF Industries, LLC", icon_url="https://slate.dan.onl/slate.png")
        view = VerificationView(bot, 1414363675552252048)
        await interaction.response.send_message("Sending Verification Panel...", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)
    elif action == "ip":
        embed = discord.Embed(
            title="Welcome to StrengthKits",
            description=(
                "StrengthKits is the official practice environment for the StrengthSMP community. "
                "Our goal is to provide a fast, competitive, and polished PvP experience modeled after the "
                "StrengthSMP combat system.\n\n"

                "**What is StrengthSMP?**\n"
                "StrengthSMP is a content-driven survival multiplayer series where players gain or lose "
                "Strength levels on kill or death, up to a maximum of 5. Strength cannot be obtained through "
                "potions, creating a unique combat meta that rewards consistency, strategy, and skill.\n\n"

                "**What do we offer?**\n"
                "• Custom PvP attacks inspired by StrengthSMP\n"
                "• Free kits designed for skill-based practice\n"
                "• Smooth dueling and kit-based combat\n"
                "• Cosmetics and unlockable visuals\n"
                "• A competitive environment suitable for both casual players and creators\n\n"

                "Whether you're training for events, recording content, or simply looking to improve, "
                "StrengthKits is the place to sharpen your skills."
            ),
            colour=0xFF0000,
            timestamp=datetime.now()
        )

        embed.set_author(name="Server Information")
        embed.add_field(
            name="Important Channels",
            value=(
                    "**Information:** <#1446711846563483811> (this channel)\n"
                    "**Chat:** <#1446711846781325433>\n"
                    "**Support:** <#1446711846563483815>\n"
                    "**Bug Reports:** <#1446711847037173819>"
            ),
            inline=False
        )

        embed.add_field(
            name="Useful Links",
            value=(
                "[StrengthKits Website](https://strengthkits.com/)\n"
                "[Coming Soon]\n"
                "[Coming Soon]"
            ),
            inline=False
        )
        bot_user = await bot.fetch_user(bot.user.id)
        embed.set_image(url=bot_user.banner.url)
        embed.set_footer(text="StrengthKits Network")
        await interaction.response.send_message("Sending Informations Panel...", ephemeral=True)
        await interaction.channel.send(embed=embed)
    elif action == "tp":
        embed = discord.Embed(
            description="# **STRKitz - Tickets**"
                        "\n*Come in contact with our staff team by creating a ticket.*"
                        "\n\n**How to create a ticket:**"
                        "\n> Click the drop-down below, to select a category"
                        "\n> Fill out the form, and submit your ticket"
                        "\n> Wait for a staff member to respond, please be patient"
                        "\n\nAbusing the ticket system in any way, will result in a permanent ticket blacklist.")
        bot_user = await bot.fetch_user(bot.user.id)
        embed.set_image(url=bot_user.banner.url)
        embed.set_footer(text="Powered by ADF Industries, LLC",
                         icon_url="https://origin.adfindustries.org/logo_1.jpg")
        view = TicketView()
        await interaction.response.send_message("Sending Ticket Panel...", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)
        return
    elif action == "rp":
        transitionEmbed1 = discord.Embed(
            title="======================  DISCORD RULES  ======================",
            color=discord.Color.blurple()
        )
        embed1 = discord.Embed(
            title="Server Rules - Part 1",
            description="Please follow the rules to ensure a great experience for everyone.",
            color=discord.Color.blurple()
        )
        embed1.add_field(name="1. Be respectful", value="Treat everyone with kindness and respect.", inline=False)
        embed1.add_field(name="2. Abide by Discord ToS", value="Follow Discord's Terms of Service at all times.",
                         inline=False)
        embed1.add_field(name="3. Use family-friendly language",
                         value="Keep your language appropriate for all audiences.", inline=False)
        embed1.add_field(name="4. No advertising", value="No unsolicited advertising or self-promotion.", inline=False)
        embed2 = discord.Embed(
            title="Server Rules - Part 2",
            description="Please continue to follow the rules for a better experience.",
            color=discord.Color.blurple()
        )
        embed2.add_field(name="5. Abide by our ToS", value="Ensure you follow our Terms of Service.", inline=False)
        embed2.add_field(name="6. Do NOT ask for support in <#1446711846781325433>",
                         value="Support requests should be handled in the proper channels.", inline=False)
        embed2.add_field(name="7. Do not ping staff", value="Avoid unnecessarily pinging staff members.", inline=False)
        embed2.add_field(name="8. Keep channels respective to their purpose",
                         value="Each channel has a specific purpose. Stay on-topic.", inline=False)
        embed3 = discord.Embed(
            title="Server Rules - Part 3",
            description="Please be mindful of the community rules.",
            color=discord.Color.blurple()
        )
        embed3.add_field(name="9. No spamming, chatwalling, flooding, or disruptions of chat",
                         value="Do not spam, flood, or disrupt the chat.", inline=False)
        embed3.add_field(name="10. Do NOT DM staff for support",
                         value="Contact support through the appropriate channels.", inline=False)

        embed4 = discord.Embed(
            title="Server Rules - Part 4",
            description="Please respect these rules, they're important!",
            color=discord.Color.blurple()
        )
        embed4.add_field(name="11. Do not ping staff members",
                         value="Do not ping them, including reply pings! You **will** be punished!", inline=False)
        embed4.add_field(name="12. Do NOT ask for support for other servers.",
                         value="Support requests should be directly related to this server. (**NOT EYSERVER**)",
                         inline=False)
        embed6 = discord.Embed(
            title="Server Rules - Part 5",
            description="Respect everyone's privacy.",
            color=discord.Color.blurple()
        )
        embed6.add_field(
            name="13. Do not share or ask about personal information",
            value="Do not discuss or ask about someone's private information (e.g., age, real name, face) unless they explicitly allow it.",
            inline=False
        )
        embed7 = discord.Embed(
            title="Server Rules - Part 6",
            description="Ethical behavior is expected from all members.",
            color=discord.Color.blurple()
        )
        embed7.add_field(
            name="14. Maintain ethical conduct",
            value="Treat others fairly and act with integrity. Toxic, manipulative, or unethical behavior will not be tolerated.",
            inline=False
        )
        embed7.add_field(
            name=" **14**.1 Dox, SWATs, DDoS",
            value="Attempting to or threatening to dox, SWAT, or DDoS will **not** be tolorated, and will result in a permanent ban.",
            inline=False
        )
        embed8 = discord.Embed(
            title="Server Rules - Part 7",
            description="Certain client modifications are not allowed.",
            color=discord.Color.blurple()
        )
        embed8.add_field(
            name="15. Vencord plugin restrictions",
            value="Use of any Vencord plugins that display hidden channels or deleted/edited messages is strictly prohibited. "
                  "You will receive two warnings. After the third offense, a punishment will be issued.",
            inline=False
        )
        embed9 = discord.Embed(
            title="Server Rules - Part 8",
            description="Use your best judgment.",
            color=discord.Color.blurple()
        )
        embed9.add_field(
            name="16. Use common sense",
            value="Not every rule can cover every situation. Use common sense and act in a way that maintains a positive, safe community.",
            inline=False
        )
        transitionEmbed2 = discord.Embed(
            title="=====================  MINECRAFT RULES  =====================",
            color=discord.Color.teal()
        )
        mc_embed1 = discord.Embed(
            title="Minecraft Rules - Part 1",
            description="Core gameplay rules to keep the server fair and enjoyable.",
            color=discord.Color.teal()
        )
        mc_embed1.add_field(
            name="1. No Spamming",
            value="Avoid flooding chat with repeated messages.",
            inline=False
        )
        mc_embed1.add_field(
            name="2. No Griefing",
            value="Do **not** destroy or alter other players' builds. Includes claimed land **and surrounding claimed areas**. "
                  "If land is unclaimed, it is **not** considered griefing.",
            inline=False
        )
        mc_embed1.add_field(
            name="3. No Raiding",
            value="Do not steal from players. Same rules apply as griefing.",
            inline=False
        )

        mc_embed2 = discord.Embed(
            title="Minecraft Rules - Part 2",
            description="Integrity and fairness are essential.",
            color=discord.Color.teal()
        )
        mc_embed2.add_field(
            name="4. No Scamming",
            value="Do not scam players in trades, shops, or deals.",
            inline=False
        )
        mc_embed2.add_field(
            name="5. No Hacking",
            value="Includes hacked clients, cheating modules, baritone, autoclickers, and any automation mods.",
            inline=False
        )
        mc_embed2.add_field(
            name="6. No Exploiting",
            value="Using or abusing glitches, dupes, or unintended mechanics will result in a **permanent ban**.",
            inline=False
        )

        mc_embed3 = discord.Embed(
            title="Minecraft Rules - Part 3",
            description="Respect all players and their space.",
            color=discord.Color.teal()
        )
        mc_embed3.add_field(
            name="7. No Close Claims",
            value="Do not purposely claim land extremely close to another player's claim to inconvenience them.",
            inline=False
        )
        mc_embed3.add_field(
            name="8. No Racism",
            value="Racist content or behavior will result in an **immediate 7-day ban**.",
            inline=False
        )
        mc_embed3.add_field(
            name="9. No Hate Speech",
            value="Hate speech of any kind may result in a **permanent ban**.",
            inline=False
        )

        mc_embed4 = discord.Embed(
            title="Minecraft Rules - Part 4",
            description="Community behavior expectations.",
            color=discord.Color.teal()
        )
        mc_embed4.add_field(
            name="10. No Harassment",
            value="Harassing players or staff is strictly prohibited and may result in a **permanent ban**.",
            inline=False
        )
        mc_embed4.add_field(
            name="11. No Advertising",
            value="No advertising YouTube videos, Discord servers, Minecraft servers, or anything similar.",
            inline=False
        )
        mc_embed4.add_field(
            name="12. No Swearing in Chat",
            value="If the filter blocks it, it's not allowed. Do **not** bypass the filter. Slurs result in an **immediate 7-day ban**.",
            inline=False
        )
        await interaction.response.send_message("Sending Rules Panel...", ephemeral=True)
        await interaction.channel.send(embeds=[transitionEmbed1, embed1, embed2, embed3, embed4, embed6, embed7, embed8, embed9])
        await interaction.channel.send(embeds=[transitionEmbed2, mc_embed1, mc_embed2, mc_embed3, mc_embed4])
    if action == "arp":
        embed = discord.Embed(
            title="🚨 A Raid Has Been Detected! 🚨",
            description=(
                "### Immediate Action Required!\n\n"
                "---\n\n"
                "> **A potential raid has been detected on ADF Industries!**\n\n"
                "```\nSecurity | Protection | Stability\n```\n\n"
                "Our automated security system has flagged **unusual activity** that may indicate a coordinated attack. "
                "To protect our community, additional **security measures** have been activated.\n\n"
                "**What does this mean?**\n"
                "🔹 Temporary restrictions may apply.\n"
                "🔹 New users will require manual verification.\n"
                "🔹 Staff intervention may be necessary.\n\n"
                "If you believe this is a false alarm, please contact an **Administrator** immediately.\n\n"
                "[🛡️ Learn More About Security](https://example.com)\n\n"
                "**Stay vigilant and keep our community safe!**\n\n"
                "||Our systems continuously monitor and improve to prevent threats.||"
            ),
            color=0xFF0000,
            timestamp=datetime.now()
        )
        embed.set_author(name="Security Alert", icon_url="https://example.com/security-icon.png")
        embed.set_image(url="https://cubedhuang.com/images/security-alert.webp")
        embed.set_thumbnail(url="https://dan.onl/images/warning-icon.jpg")
        embed.set_footer(text="ADF Industries Security", icon_url="https://slate.dan.onl/slate.png")
        view = None
        await interaction.response.send_message("Sending Anti-Raid Panel...", ephemeral=True)
        await interaction.channel.send(embed=embed, view=view)
    else:
        await interaction.followup.send("Invalid action!", ephemeral=True)
@bot.tree.command(name="close", guild=discord.Object(id=int(1414363675552252048)))
async def close(interaction: discord.Interaction):
    async with aiosqlite.connect(TICKET_DATABASE) as db:
        cursor = await db.execute("SELECT user_id FROM tickets WHERE channel_id = ?", (interaction.channel.id,))
        result = await cursor.fetchone()
        if not result:
            await interaction.response.send_message("This channel is not a ticket.", ephemeral=True)
            return
        """Closes a ticket by making it private and moving it to an archive category."""
        embed = discord.Embed(title="Are you sure?", description="Do you want to close and archive this ticket?",
                              color=discord.Color.dark_red())
        view = TicketCloseView(interaction, interaction.channel.id, interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

@bot.event
async def on_ready():
    _log.info(f"{bot.user} has connected to Discord!")
    await load_extensions("cogs")
    synced_commands = await bot.tree.sync()
    _log.info(f"Synced {len(synced_commands)} global slash command(s).")
    guild = discord.Object(id=1446711845787275404)
    await bot.tree.sync(guild=guild)
    _log.info("StrengthKits' specific commands have been registered & synced!\n")
    _log.info(f"Successfully loaded Strength Bot (v1)!")
    ticket_channels = load_ticket_channels()
    for channel_id in ticket_channels:
        channel = bot.get_channel(channel_id)
        if channel:
            bot.add_view(TicketPanelView(channel))
            verbose.send(f"Restored ticket panel view for channel ID {channel_id}")
        else:
            verbose.send(f"Channel ID {channel_id} not found, removing from ticket list")
            ticket_channels.remove(channel_id)
            save_ticket_channels(ticket_channels)
    for guild in bot.guilds:
        bot.add_view(VerificationView(bot, guild.id))
    bot.add_view(TicketView())
    activity = discord.Game(name="play.strengthkits.com")
    await bot.change_presence(
        activity=activity)

bot.run(DISCORD_TOKEN)