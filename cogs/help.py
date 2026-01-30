import discord
from discord import app_commands
from discord.ext import commands

class HelpCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="help", description="View basic server information and how to join the Minecraft server.")
    async def help_command(self, interaction: discord.Interaction):

        embed = discord.Embed(
            title="📘 Server Help Menu",
            description="Here is some helpful information about our Discord and Minecraft server!",
            color=discord.Color.blue()
        )

        # --- Minecraft Connection Info ---
        embed.add_field(
            name="🟩 How to Join the Minecraft Server",
            value=(
                "**Java Edition:** `luminox.minehut.gg`\n"
                "**Bedrock Edition:** `luminox.bedrock.minehut.gg`\n"
                "Make sure you're on the correct version!"
            ),
            inline=False
        )

        # --- Important Channels ---
        embed.add_field(
            name="📌 Important Channels",
            value=(
                "• <#1446711846563483810> — Read the full server rules\n"
                "• <#1446711846563483811> — General server information\n"
                "• <#1446711846563483815> — Open a ticket or get help\n"
                "• <#1446766049973502044> — Updates and events"
            ),
            inline=False
        )

        # --- Rules Summary ---
        embed.add_field(
            name="📜 Quick Rules Summary",
            value=(
                "• No griefing or raiding\n"
                "• No hacking or exploiting\n"
                "• No harassment or hate speech\n"
                "• No advertising\n"
                "• Use common sense and respect others"
            ),
            inline=False
        )

        # --- Footer ---
        embed.set_footer(text="If you need more help, feel free to open a support ticket!")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot):
    await bot.add_cog(HelpCog(bot))
