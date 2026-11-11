"""
بوت ديسكورد لإرسال الرسائل (discord.py 2.x)

التثبيت:
    pip install -U discord.py python-dotenv

الإعداد:
    1) أنشئ ملف .env بجانب هذا الملف وضع فيه:
           DISCORD_TOKEN=ضع_توكن_البوت_هنا
    2) شغّل البوت:
           python bot.py

الأوامر (Slash Commands):
    /say      -> البوت يرسل رسالة عادية في القناة الحالية أو قناة تحددها
    /embed    -> إرسال رسالة بتنسيق Embed جميل
    /dm       -> إرسال رسالة خاصة لعضو
    /announce -> إرسال إعلان مع منشن @everyone (للمشرفين فقط)
"""

import logging
import os

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("bot")

# لا نحتاج message_content لأننا نستخدم Slash Commands فقط
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    log.info("تم تسجيل الدخول باسم %s (ID: %s)", bot.user, bot.user.id)
    try:
        synced = await bot.tree.sync()
        log.info("تمت مزامنة %d أمر", len(synced))
    except Exception:
        log.exception("فشلت مزامنة الأوامر")


async def safe_send(channel: discord.abc.Messageable, **kwargs) -> bool:
    """يرسل رسالة ويتعامل مع الأخطاء الشائعة. يرجع True عند النجاح."""
    try:
        await channel.send(**kwargs)
        return True
    except discord.Forbidden:
        log.warning("لا أملك صلاحية الإرسال في %s", channel)
    except discord.HTTPException as e:
        log.warning("فشل الإرسال: %s", e)
    return False


# ---------------------------------------------------------------- /say
@bot.tree.command(name="say", description="البوت يرسل رسالة في قناة")
@app_commands.describe(message="نص الرسالة", channel="القناة (اختياري، الافتراضي القناة الحالية)")
@app_commands.checks.has_permissions(manage_messages=True)
async def say(
    interaction: discord.Interaction,
    message: app_commands.Range[str, 1, 2000],
    channel: discord.TextChannel | None = None,
):
    target = channel or interaction.channel
    # allowed_mentions يمنع استغلال الأمر لعمل منشن جماعي
    ok = await safe_send(
        target,
        content=message,
        allowed_mentions=discord.AllowedMentions(everyone=False, roles=False, users=True),
    )
    await interaction.response.send_message(
        f"✅ تم الإرسال في {target.mention}" if ok else "❌ تعذّر الإرسال، تحقق من صلاحيات البوت.",
        ephemeral=True,
    )


# ------------------------------------------------------------- /embed
@bot.tree.command(name="embed", description="إرسال رسالة بتنسيق Embed")
@app_commands.describe(
    title="العنوان",
    description="المحتوى",
    color="لون بصيغة hex مثل ff5733 (اختياري)",
    channel="القناة (اختياري)",
)
@app_commands.checks.has_permissions(manage_messages=True)
async def embed_cmd(
    interaction: discord.Interaction,
    title: app_commands.Range[str, 1, 256],
    description: app_commands.Range[str, 1, 4000],
    color: str | None = None,
    channel: discord.TextChannel | None = None,
):
    try:
        colour = discord.Colour(int(color.lstrip("#"), 16)) if color else discord.Colour.blurple()
    except ValueError:
        await interaction.response.send_message("❌ اللون غير صحيح، مثال: ff5733", ephemeral=True)
        return

    emb = discord.Embed(title=title, description=description, colour=colour)
    emb.set_footer(text=f"بواسطة {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url)
    emb.timestamp = discord.utils.utcnow()

    target = channel or interaction.channel
    ok = await safe_send(target, embed=emb)
    await interaction.response.send_message("✅ تم الإرسال" if ok else "❌ تعذّر الإرسال", ephemeral=True)


# ---------------------------------------------------------------- /dm
@bot.tree.command(name="dm", description="إرسال رسالة خاصة لعضو")
@app_commands.describe(member="العضو", message="نص الرسالة")
@app_commands.checks.has_permissions(manage_messages=True)
@app_commands.guild_only()
async def dm(
    interaction: discord.Interaction,
    member: discord.Member,
    message: app_commands.Range[str, 1, 2000],
):
    if member.bot:
        await interaction.response.send_message("❌ لا يمكن إرسال رسالة خاصة لبوت.", ephemeral=True)
        return
    try:
        await member.send(message)
        await interaction.response.send_message(f"✅ تم إرسال الرسالة إلى {member.mention}", ephemeral=True)
    except discord.Forbidden:
        await interaction.response.send_message("❌ العضو مغلق رسائله الخاصة.", ephemeral=True)


# ----------------------------------------------------------- /announce
@bot.tree.command(name="announce", description="إرسال إعلان مع @everyone")
@app_commands.describe(message="نص الإعلان", channel="قناة الإعلان")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def announce(
    interaction: discord.Interaction,
    message: app_commands.Range[str, 1, 1900],
    channel: discord.TextChannel,
):
    ok = await safe_send(
        channel,
        content=f"@everyone\n{message}",
        allowed_mentions=discord.AllowedMentions(everyone=True),
    )
    await interaction.response.send_message("✅ تم نشر الإعلان" if ok else "❌ تعذّر النشر", ephemeral=True)


# ------------------------------------------------ معالجة أخطاء الأوامر
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        msg = "❌ ليس لديك الصلاحية لاستخدام هذا الأمر."
    else:
        log.exception("خطأ غير متوقع في الأمر", exc_info=error)
        msg = "❌ حصل خطأ غير متوقع."

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("ضع DISCORD_TOKEN في ملف .env")
    bot.run(TOKEN)
