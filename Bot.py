import logging                                       import re
from telegram import Update, ChatPermissions         from telegram.ext import (                               ApplicationBuilder, MessageHandler, ChatMemberHandler,                                                    filters, ContextTypes                            )
from telegram.error import TelegramError                                                                  logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)                                                                      BOT_TOKEN = "8829579785:AAH79xvOakNnmZFrouB8S1pchFFyj-ho4GY"                                                                                                   # warning count store: {chat_id: {user_id: count}}
warnings: dict[int, dict[int, int]] = {}                                                                  # URL/link detect regex
LINK_PATTERN = re.compile(                               r"(https?://\S+|www\.\S+|t\.me/\S+|@\w{5,}|\S+\.(com|net|org|io|xyz|site|online|info|co)\S*)",            re.IGNORECASE
)                                                    
def has_link(text: str) -> bool:
    return bool(LINK_PATTERN.search(text)) if text else False

async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    try:
        member = await context.bot.get_chat_member(update.effective_chat.id, user_id)
        return member.status in ("administrator", "creator")
    except TelegramError:
        return False

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.effective_message
    chat = update.effective_chat
    user = update.effective_user

    if not msg or not user or not chat:
        return

    # Skip admins/bots
    if user.is_bot or await is_admin(update, context, user.id):
        return

    text = msg.text or msg.caption or ""

    if not has_link(text):
        return

    chat_id = chat.id
    user_id = user.id

    # Delete message
    try:
        await msg.delete()
    except TelegramError as e:
        logger.warning(f"Delete failed: {e}")

    # Init warning dict
    if chat_id not in warnings:
        warnings[chat_id] = {}
    if user_id not in warnings[chat_id]:
        warnings[chat_id][user_id] = 0

    warnings[chat_id][user_id] += 1
    count = warnings[chat_id][user_id]

    if count == 1:
        # First offense → warning
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"⚠️ {user.mention_html()}, links is group mein allowed nahi hain!\n"
                    f"Tera message delete kar diya gaya.\n\n"
                    f"🚨 <b>Dobara link dala to ban kar diya jayega!</b>"
                ),
                parse_mode="HTML"
            )
        except TelegramError as e:
            logger.warning(f"Warning message failed: {e}")

    else:
        # Second+ offense → ban
        try:
            await context.bot.ban_chat_member(chat_id=chat_id, user_id=user_id)
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"🔨 {user.mention_html()} ko ban kar diya gaya!\n"
                    f"Reason: Group mein baar baar links bheja."
                ),
                parse_mode="HTML"
            )
            # Clear warnings after ban
            warnings[chat_id].pop(user_id, None)
        except TelegramError as e:
            logger.warning(f"Ban failed: {e}")

async def handle_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Scan bio when user joins"""
    result = update.chat_member
    if not result:
        return

    new_member = result.new_chat_member
    chat = result.chat

    if new_member.status not in ("member", "restricted"):
        return

    user = new_member.user
    if user.is_bot:
        return

    try:
        user_info = await context.bot.get_chat(user.id)
        bio = user_info.bio or ""

        if has_link(bio):
            await context.bot.send_message(
                chat_id=chat.id,
                text=(
                    f"🚫 {user.mention_html()} ke bio mein link mila!\n"
                    f"Unke messages automatically delete hote rahenge jab tak bio saaf nahi karte."
                ),
                parse_mode="HTML"
            )
            logger.info(f"Bio link found for user {user.id} in chat {chat.id}")
    except TelegramError as e:
        logger.warning(f"Bio scan failed for {user.id}: {e}")

async def handle_any_message_bio_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """For users with link in bio, delete every message"""
    msg = update.effective_message
    user = update.effective_user
    chat = update.effective_chat

    if not msg or not user or not chat:
        return
    if user.is_bot or await is_admin(update, context, user.id):
        return

    try:
        user_info = await context.bot.get_chat(user.id)
        bio = user_info.bio or ""
        if has_link(bio):
            await msg.delete()
            logger.info(f"Deleted message from bio-link user {user.id}")
    except TelegramError:
        pass

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Bio check runs on every message (before link check)
    app.add_handler(MessageHandler(
        filters.TEXT | filters.CAPTION,
        handle_any_message_bio_check
    ), group=0)

    # Link detection in messages
    app.add_handler(MessageHandler(
        filters.TEXT | filters.CAPTION,
        handle_message
    ), group=1)

    # New member bio scan
    app.add_handler(ChatMemberHandler(
        handle_new_member,
        ChatMemberHandler.CHAT_MEMBER
    ))

    logger.info("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
