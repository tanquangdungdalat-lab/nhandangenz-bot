import logging, re, time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from telegram import Update, ChatPermissions
from telegram.constants import ChatMemberStatus
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# === DÁN TOKEN MỚI VÀO ĐÂY ===
TOKEN = "8899914599:AAFwyS2S7_Y_JkELsvMKsgba42m200q_-MY"

FLOOD_LIMIT = 5
FLOOD_SECONDS = 8
MUTE_MINUTES = 10
MAX_WARNINGS = 3
BLOCK_LINKS = True
BLOCKED_WORDS = ["kiem tien nhanh", "nap tien nhan thuong", "casino"]

logging.basicConfig(format="%(asctime)s | %(levelname)s | %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
message_times = defaultdict(deque)
warnings = defaultdict(int)

async def is_admin(chat_id, user_id, context):
    try:
        m = await context.bot.get_chat_member(chat_id, user_id)
        return m.status in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER)
    except: return False

def get_message_text(message):
    return (message.text or message.caption or "").strip()

def contains_link(message, text):
    if re.search(r"(?i)(https?://|www\.|t\.me/|telegram\.me/|telegra\.ph/|tg://)", text): return True
    entities = list(message.entities or []) + list(message.caption_entities or [])
    return any(e.type in ("url", "text_link") for e in entities)

async def mute_user(update, context, minutes=MUTE_MINUTES):
    chat, user = update.effective_chat, update.effective_user
    if not chat or not user or await is_admin(chat.id, user.id, context): return
    try:
        until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        await context.bot.restrict_chat_member(chat.id, user.id, ChatPermissions(can_send_messages=False), until_date=until)
        await context.bot.send_message(chat.id, f"{user.full_name} bị hạn chế {minutes} phút do vi phạm.")
    except Exception as e: logger.warning(e)

async def register_violation(update, context, reason):
    user, chat = update.effective_user, update.effective_chat
    if not user or not chat: return
    key = (chat.id, user.id)
    warnings[key] += 1
    await context.bot.send_message(chat.id, f"{user.full_name}: {reason}\nVi phạm: {warnings[key]}/{MAX_WARNINGS}")
    if warnings[key] >= MAX_WARNINGS:
        warnings[key] = 0
        await mute_user(update, context)

async def moderate_message(update, context):
    msg, user, chat = update.effective_message, update.effective_user, update.effective_chat
    if not msg or not user or not chat or user.is_bot or await is_admin(chat.id, user.id, context): return
    text = get_message_text(msg)
    key = (chat.id, user.id)

    if BLOCK_LINKS and contains_link(msg, text):
        try: await msg.delete()
        except: pass
        await register_violation(update, context, "Tin nhắn chứa link đã bị xóa.")
        return

    if any(w.casefold() in text.casefold() for w in BLOCKED_WORDS):
        try: await msg.delete()
        except: pass
        await register_violation(update, context, "Tin nhắn chứa từ khóa bị cấm.")
        return

    now = time.monotonic()
    q = message_times[key]
    q.append(now)
    while q and now - q[0] > FLOOD_SECONDS: q.popleft()
    if len(q) >= FLOOD_LIMIT:
        q.clear()
        try: await msg.delete()
        except: pass
        await register_violation(update, context, f"Spam {FLOOD_LIMIT} tin/{FLOOD_SECONDS}s")

async def start(update, context): await update.effective_message.reply_text("Bot quản lý Nhân Dân GenZ đã sẵn sàng!")
async def help_command(update, context): await update.effective_message.reply_text("/start /help /status /warns /unmute (reply vào người cần gỡ)")
async def status_command(update, context): await update.effective_message.reply_text("Bot đang hoạt động.")
async def warns_command(update, context):
    c = warnings[(update.effective_chat.id, update.effective_user.id)]
    await update.effective_message.reply_text(f"Cảnh báo của bạn: {c}/{MAX_WARNINGS}")
async def unmute_command(update, context):
    if not update.effective_message.reply_to_message: return await update.effective_message.reply_text("Reply vào người cần unmute rồi gõ /unmute")
    target = update.effective_message.reply_to_message.from_user
    try:
        await context.bot.restrict_chat_member(update.effective_chat.id, target.id, ChatPermissions.all_permissions())
        warnings[(update.effective_chat.id, target.id)] = 0
        await update.effective_message.reply_text(f"Đã gỡ hạn chế cho {target.full_name}")
    except: await update.effective_message.reply_text("Không gỡ được, kiểm tra quyền admin của bot.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("warns", warns_command))
    app.add_handler(CommandHandler("unmute", unmute_command))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & ~filters.StatusUpdate.ALL, moderate_message))
    print("Bot dang chay...")
    app.run_polling()

if __name__ == "__main__": main()