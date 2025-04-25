import logging
logger = logging.getLogger(__name__)
from typing import Optional, Tuple, Union, Dict, List
from telegram import (
    Update,
    Chat,
    ChatMemberUpdated,
    ChatMemberOwner,
    ChatMemberAdministrator,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    ChatMemberHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import re
import os
import time
from telethon import TelegramClient
import asyncio
from language_manager import language_manager  # Added import statement

# --- Added Imports for Flask Health Check ---
import threading
from flask import Flask

# Configure logging with more details
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO)
logger = logging.getLogger(__name__)

# Use environment variables for tokens and credentials
BOT_TOKEN = os.getenv("BOT_TOKEN", "7396319401:AAEPif6ZxkEaJBiTXeEPZpRgYl7XOI4HUto")
API_ID = 21547048
API_HASH = "aaca55f2ee5af88fbe9f589393a7b9b6"

# Initialize Telethon client
telethon_client = None


async def get_telethon_client():
    """Get or create Telethon client instance"""
    global telethon_client
    if telethon_client is None:
        try:
            telethon_client = TelegramClient('bot_session', API_ID, API_HASH)
            await telethon_client.start(bot_token=BOT_TOKEN)
            logger.info("Telethon client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Telethon client: {e}")
            return None
    return telethon_client


async def resolve_username(
    username: str,
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: Optional[int] = None
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Enhanced username resolution using Telethon and PTB methods
    Returns (user_id, first_name, error_message)
    """
    logger.info(
        f"Starting username resolution for: {username} in chat {chat_id}")
    clean_username = username.lstrip('@').strip().lower()

    if not await is_valid_username(clean_username):
        logger.warning(f"Invalid username format: {clean_username}")
        return None, None, "Invalid username format. Username should be 5-32 characters long and contain only letters, numbers, and underscores."

    try:
        # Try Telethon first
        client = await get_telethon_client()
        if client:
            try:
                logger.info(f"Attempting Telethon lookup for {clean_username}")
                user = await client.get_entity(clean_username)
                if user and hasattr(user, 'id'):
                    logger.info(
                        f"Successfully resolved {clean_username} using Telethon. User ID: {user.id}"
                    )
                    return user.id, getattr(user, 'first_name',
                                            clean_username), None
            except ValueError as ve:
                logger.warning(
                    f"Telethon ValueError for {clean_username}: {ve}")
            except Exception as e:
                logger.warning(
                    f"Telethon lookup failed for {clean_username}: {e}")
        else:
            logger.warning("Telethon client initialization failed")

        # Fallback to PTB methods
        try:
            logger.info(f"Attempting direct chat lookup for @{clean_username}")
            user = await context.bot.get_chat(f"@{clean_username}")
            if user and user.id:
                logger.info(
                    f"Successfully resolved {clean_username} using direct lookup. User ID: {user.id}"
                )
                return user.id, user.first_name or clean_username, None
        except Exception as e1:
            logger.warning(f"Direct lookup failed for {clean_username}: {e1}")

        # If chat_id provided, try getting member info
        if chat_id is not None:
            try:
                logger.info(f"Attempting chat member lookup in chat {chat_id}")
                chat = await context.bot.get_chat(chat_id)
                logger.info(f"Chat type: {chat.type}")

                if chat.type in ['supergroup', 'channel']:
                    try:
                        member = await context.bot.get_chat_member(
                            chat_id, f"@{clean_username}")
                        if member and member.user:
                            logger.info(
                                f"Successfully resolved {clean_username} using chat member lookup. User ID: {member.user.id}"
                            )
                            return member.user.id, member.user.first_name or clean_username, None
                    except Exception as e2:
                        logger.warning(
                            f"Chat member lookup failed for {clean_username}: {e2}"
                        )

                    # Try one more time by searching through admin list
                    try:
                        admins = await context.bot.get_chat_administrators(
                            chat_id)
                        for admin in admins:
                            if admin.user.username and admin.user.username.lower(
                            ) == clean_username:
                                logger.info(
                                    f"Found user in admin list. User ID: {admin.user.id}"
                                )
                                return admin.user.id, admin.user.first_name or clean_username, None
                    except Exception as e3:
                        logger.warning(f"Admin list lookup failed: {e3}")

            except Exception as e4:
                logger.error(f"Error getting chat info for {chat_id}: {e4}")

    except Exception as e:
        logger.error(f"Error in resolve_username: {e}")

    logger.warning(
        f"All resolution methods failed for username {clean_username}")
    return None, clean_username, f"Could not resolve username @{clean_username}. Please try using the numeric User ID instead."


async def is_valid_username(username: str) -> bool:
    """Validate Telegram username format"""
    username_pattern = re.compile(r'^[a-zA-Z0-9_]{5,32}$')
    return bool(username_pattern.match(username))


async def is_valid_user_id(user_id: Union[str, int]) -> bool:
    """Validate Telegram user ID format"""
    try:
        uid = int(user_id) if isinstance(user_id, str) else user_id
        return uid > 0
    except ValueError:
        return False


async def normalize_username(username: str) -> str:
    """Normalize username for comparison"""
    return username.lstrip('@').strip().lower()


async def resolve_user_id(
    user_id: Union[str, int],
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: Optional[int] = None
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Enhanced user ID resolution with validation
    Returns (user_id, first_name, error_message)
    """
    try:
        uid = int(user_id) if isinstance(user_id, str) else user_id
        if not await is_valid_user_id(uid):
            return None, None, "Invalid user ID format. Please provide a valid numeric ID."

        user = await context.bot.get_chat(uid)
        if user and user.id:
            return user.id, user.first_name or str(uid), None
    except ValueError:
        return None, None, "Invalid user ID format. Please provide a valid numeric ID."
    except Exception as e:
        logger.warning(f"Failed to resolve user ID {user_id}: {e}")
        return None, str(
            user_id
        ), f"Could not find user with ID {user_id}. Please verify the ID is correct."


async def check_bot_permissions(chat_id, context):
    """Verify the bot has the necessary permissions in a chat/channel"""
    try:
        bot_id = context.bot.id
        bot_member = await context.bot.get_chat_member(chat_id, bot_id)

        if not isinstance(bot_member, ChatMemberAdministrator):
            logger.warning(f"Bot is not an admin in {chat_id}")
            return False, "I need to be an administrator to work properly."

        # Check for required permissions
        permissions = bot_member.can_promote_members and bot_member.can_restrict_members

        if not permissions:
            logger.warning(
                f"Bot doesn't have required permissions in {chat_id}")
            return False, "I need permission to promote members and restrict users."

        return True, None
    except Exception as e:
        logger.error(f"Failed to check bot permissions in {chat_id}: {e}")
        return False, f"Error checking permissions: {str(e)}"


async def verify_user_in_channel(
        user_id: int, first_name: str, chat_id: int,
        context: ContextTypes.DEFAULT_TYPE) -> Tuple[bool, str]:
    """
    Verify if a user is a member of the channel
    Returns (is_member, message)
    """
    try:
        logger.info(
            f"Verifying user {first_name} (ID: {user_id}) in chat {chat_id}")

        # Check user's membership status
        member = await context.bot.get_chat_member(chat_id, user_id)
        logger.info(f"User {user_id} membership status: {member.status}")

        if member.status == "administrator":
            return False, f"User {first_name} is already an administrator"
        elif member.status == "creator":
            return False, f"User {first_name} is the channel creator"
        elif member.status == "member":
            return True, ""
        elif member.status == "restricted":
            return False, f"User {first_name} is restricted in this channel"
        elif member.status in ["left", "kicked"]:
            return False, f"User {first_name} is not a member of this channel"
        else:
            return False, f"User {first_name} has unknown status: {member.status}"

    except Exception as e:
        logger.error(f"Error verifying user in channel: {e}")
        return False, f"Could not verify membership status: {str(e)}"


async def promote_user(chat_id: int,
                      user_id: Union[int, str],
                      context: ContextTypes.DEFAULT_TYPE,
                      custom_title: Optional[str] = None) -> Tuple[bool, str]:
    """
    Centralized user promotion function with enhanced verification and custom title support
    Returns (success, message)
    """
    logger.info(f"Starting promotion process for user {user_id} in chat {chat_id}")

    try:
        # Get owner information
        admins = await context.bot.get_chat_administrators(chat_id)
        creator = next((admin for admin in admins if admin.status == "creator"), None)

        if not creator:
            return False, "Could not verify channel ownership. Please try again later."

        # Convert user_id to int if it's a string
        if isinstance(user_id, str):
            if not user_id.isdigit():
                logger.error(f"Invalid user_id format: {user_id}")
                return False, "Invalid user ID format. Please provide a numeric ID."
            user_id = int(user_id)
            logger.info(f"Converted string user_id to int: {user_id}")

        if not isinstance(user_id, int):
            logger.error(f"Invalid user_id type after conversion: {type(user_id)}")
            return False, "Internal error: Invalid user ID type"

        # Get user details
        try:
            user_info = await context.bot.get_chat_member(chat_id, user_id)
            first_name = user_info.user.first_name
            logger.info(f"Found user: {first_name} (ID: {user_id})")
        except Exception as e:
            logger.warning(f"Failed to get user info: {e}")
            return False, "Could not find user information. Please verify the user ID and ensure they are a member of the channel."

        # Verify user membership
        is_member, error_message = await verify_user_in_channel(user_id, first_name, chat_id, context)
        if not is_member:
            return False, error_message

        # Get chat type
        chat = await context.bot.get_chat(chat_id)
        is_group = chat.type in ['group', 'supergroup']

        # Attempt promotion with all permissions except promoting others
        logger.info(f"Attempting to promote user {user_id} with permissions")
        await context.bot.promote_chat_member(
            chat_id=chat_id,
            user_id=user_id,
            can_manage_chat=True,
            can_delete_messages=True,
            can_manage_video_chats=True,
            can_promote_members=False,  # Never allow promoting others
            can_change_info=False,
            can_post_messages=True,
            can_edit_messages=True,
            can_invite_users=True,
        )

        # Set custom title if provided and in a group
        if custom_title and is_group:
            custom_title = custom_title[:16]  # Trim title to 16 characters
            try:
                await context.bot.set_chat_administrator_custom_title(
                    chat_id=chat_id,
                    user_id=user_id,
                    custom_title=custom_title)
                logger.info(f"Set custom title '{custom_title}' for user {user_id}")
                return True, f"Successfully promoted {first_name} with title '{custom_title}'."
            except Exception as e:
                logger.warning(f"Failed to set custom title: {e}")
                return True, f"Promoted {first_name} but couldn't set custom title: {str(e)}"

        logger.info(f"Successfully promoted user {user_id} in chat {chat_id}")
        return True, f"Successfully promoted {first_name} to administrator."

    except Exception as e:
        error_msg = str(e).lower()
        logger.error(f"Promotion failed for user {user_id} in chat {chat_id}: {e}")

        if "not enough rights" in error_msg:
            return False, "Bot lacks necessary permissions. Please ensure bot is an administrator with promotion rights."
        elif "user not found" in error_msg:
            return False, "User not found. Please ensure the user has joined the channel."
        elif "chat not found" in error_msg:
            return False, "Chat/Channel not found. Please verify the chat ID."
        else:
            return False, f"Promotion failed: {str(e)}"


async def is_chat_owner(chat_id: int, user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if the user is the owner/creator of the chat"""
    try:
        # Get fresh list of administrators
        admins = await context.bot.get_chat_administrators(chat_id)
        # Find the creator (owner)
        creator = next((admin for admin in admins if admin.status == "creator"), None)
        # Return True only if the user is the creator
        return creator and creator.user.id == user_id
    except Exception as e:
        logger.error(f"Failed to check owner status: {e}")
        return False


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /admin - Promotes the target user to admin.
    Usage:
    - Reply to a message with: /admin [nickname]
    - Or use: /admin @username [nickname] (in groups)
    - Or use: /admin @username or /admin user_id (in channels)
    """
    if update.channel_post:
        return

    if not update.message:
        logger.warning("Admin command received with no message")
        return

    chat_id = update.effective_chat.id
    message = update.message
    user_id = update.effective_user.id if update.effective_user else None

    # Disallow usage in private chats
    if update.effective_chat.type == "private":
        await message.reply_text("This command is for channel/group usage only.")
        return

    # Store the message for later use in ownership verification
    context.chat_data['last_command_message'] = update.message

    # Check if the user is the owner
    if not await is_chat_owner(chat_id, user_id, context):
        error_msg = await message.reply_text("Only the group/channel owner can promote members to admin.")
        # Delete the command and error message after a short delay
        try:
            await message.delete()
            await asyncio.sleep(3)
            await error_msg.delete()
        except Exception as e:
            logger.error(f"Failed to delete messages: {e}")
        return

    # Check if bot has necessary permissions
    has_permissions, error_message = await check_bot_permissions(chat_id, context)
    if not has_permissions:
        await message.reply_text(f"I cannot perform admin actions: {error_message}")
        return

    target_user_id = None
    target_user_first_name = None
    error_msg = None
    nickname = None

    # Check if message is a reply
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_user_id = target_user.id
        target_user_first_name = target_user.first_name

        # Extract nickname from command text if provided
        command_parts = message.text.split()
        if len(command_parts) > 1:
            nickname = ' '.join(command_parts[1:])
            logger.info(f"Nickname provided in reply: {nickname}")

    # If not a reply, check command arguments
    elif context.args:
        # First argument is always username/user_id
        arg = context.args[0]

        # Check for nickname (only in groups)
        if len(context.args) > 1 and update.effective_chat.type in ['group', 'supergroup']:
            nickname = ' '.join(context.args[1:])  # Join remaining args as nickname
            logger.info(f"Nickname provided in command: {nickname}")

        if arg.startswith('@'):
            # Try username lookup
            target_user_id, target_user_first_name, error_msg = await resolve_username(arg, context, chat_id)
        else:
            # Try user ID lookup
            target_user_id, target_user_first_name, error_msg = await resolve_user_id(arg, context, chat_id)

        if error_msg:
            await message.reply_text(error_msg)
            if not target_user_id:  # Cannot proceed without a valid user ID
                return
    else:
        usage_text = (
            "Please use one of these formats:\n"
            "- Reply to a message with: /admin [nickname]\n"
            "- Or use: /admin @username [nickname] (in groups)\n"
            "- Or use: /admin @username or /admin user_id (in channels)"
        )
        await message.reply_text(usage_text)
        return

    # Use the centralized promote_user function with nickname
    success, message_text = await promote_user(chat_id, target_user_id, context, nickname)

    # Send success/failure message and handle deletion
    response_message = await message.reply_text(message_text)

    if success:
        logger.info(f"Successfully promoted user {target_user_id} in chat {chat_id}")
        try:
            # Delete both messages immediately on success
            await message.delete()
            await response_message.delete()
        except Exception as e:
            logger.error(f"Failed to delete messages: {e}")
    else:
        logger.warning(f"Failed to promote user {target_user_id} in chat {chat_id}: {message_text}")


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    /start - Sends a welcome message with inline buttons.
    Works in private chats, groups, and channels.
    """
    if update.channel_post:
        if not update.channel_post:
            return
        chat_id = update.effective_chat.id

    chat_id = update.effective_chat.id
    user = update.effective_user
    username = user.username if user else "None"
    first_name = user.first_name if user else "None"
    user_id = user.id if user else "None"

    welcome_text = (f"👋🏻 Merhaba @{username}\n"
                    f"—{first_name}  None ({user_id})\n\n"
                    "@CyberChanneISecurity_bot Kanalınızı\n"
                    "Güvenle Korur Ve İşlerinizi Kolaylaştırır.\n\n"
                    "👉🏻 Çalışmama izin vermek için kanalınızda\n"
                    "tüm yetkileri veriniz.\n\n"
                    "❓ Komutlar Neler?\n"
                    "Komutlar Hakkında Bilgi Almak İçin Bot\n"
                    "Kullanım Butonuna Basınız Lütfen.\n\n"
                    "🌎 Desteklenen Diller Neler?\n"
                    "Dil Değiştir Butonuna Basarak Seçenekleri\n"
                    "Görebilirsin\n\n"
                    "✨ Legali Bot")

    keyboard = [[
        InlineKeyboardButton(
            "➕ Kanala Ekle",
            url="https://t.me/CyberChannelSecurity_bot?startchannel=s&admin=manage_video_chats+pin_messages+invite_users"
        ),
        InlineKeyboardButton("📝 Bot hakkında bilgi", callback_data="bot_info")
    ],
                [
                    InlineKeyboardButton(
                        "⚙️ BOT İNFO KANALI",
                        url="https://t.me/CyberChannelSecurity")
                ]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(chat_id=chat_id,
                                       text=welcome_text,
                                       reply_markup=reply_markup)
        logger.info(f"Start command processed for chat {chat_id}")
    except Exception as e:
        logger.error(f"Failed to send start message to {chat_id}: {e}")


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles inline button presses."""
    query = update.callback_query
    await query.answer()

    if query.data == "bot_usage":
        usage_text = ("👑 Kanal Yöneticileri Komutları\n\n"
                      "👮 /admin @User Etikete Sahip Olan\n"
                      "Kullanıcı Kanalda Yetki Alır\n\n"
                      "👮 /admin ID Etikete Sahip Olan\n"
                      "Kullanıcı Kanalda Yetki Alır\n\n"
                      "👑 Kanal Koruma Sistemi\n\n"
                      "📢 Eğer Kanal Admini Bir\n"
                      "Kullanıcıyı Kanaldan Çıkartırsa\n"
                      "Bot Otomatik Olarak Kanaldan\n"
                      "Banlar Ve Kanala Kimi Ve Çıkaran\n"
                      "Kişi Hakkında Bilgi Metini İletir\n\n"
                      "➡️ Örnek: Adlı Admin Tarafından Adlı\n"
                      "Kullanıcı Kanaldan Çıkarıldı Admin\n"
                      "Kanaldan Banlandı\n\n"
                      "📝 Örnek Sadece Tanıtım Olarak\n"
                      "Gösterilmiştir Yazı Stili Değişiktir\n\n"
                      "/kanal yazarak kanal hakkında bilgi edinin")
        keyboard = [[
            InlineKeyboardButton("⬅️ Geri Dön", callback_data="bot_info")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=usage_text,
                                      reply_markup=reply_markup)

    elif query.data == "bot_info":
        bot_info_text = ("👋 Merhaba Canım, Ben Bir Koruma Botuyum\n\n"
                         "👮 Kanalını Dağıtacak Kullanıcıları\n"
                         "Sen Yokken Engelleyebilirim\\!\n\n"
                         "➡️ Kurulum Aşamaları\n\n"
                         "`⚙️ Beni Kanalına Ekle 1/3`\n"
                         "`⚙️ Benim Yetkimi Fulle 2/3`\n"
                         "`⚙️ İşlem Tamam Artık Aktif\\! 3/3`\n\n"
                         "📢 Fakat Kanalında Bana Tam Yetki\n"
                         "Vermez İsen Kanalını Koruyamam\\.\\.\\.\n\n"
                         "✨ Legali Bot\\.")
        keyboard = [[
            InlineKeyboardButton("👾Bot Kullanım", callback_data="bot_usage")
        ],
                    [
                        InlineKeyboardButton("🌍Dil değiştir",
                                             callback_data="change_language")
                    ],
                    [
                        InlineKeyboardButton("1️⃣BOT DEVELOPER",
                                             url="https://t.me/canlaryakan"),
                        InlineKeyboardButton("2️⃣BOT DEVELOPER 2",
                                             url="https://t.me/thetis0")
                    ]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        try:
            await query.edit_message_text(text=bot_info_text,
                                          reply_markup=reply_markup,
                                          parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Failed to edit message: {e}")
            # Try without MarkdownV2 if formatting fails
            await query.edit_message_text(text=bot_info_text,
                                          reply_markup=reply_markup)

    elif query.data == "change_language":
        language_text = ("👋 Merhaba Kullanıcı İsim Yada ID İşte\n\n"
                         "⚙️ Aşşağıdaki butonlara basarak\n"
                         "Dili değiştirebilirsiniz\n\n"
                         "🌍 [Türkçe] %100\n"
                         "🌍 [English] %83\n\n"
                         "✨ Yeni Diller Eklenecektir Bilginize")
        keyboard = [[
            InlineKeyboardButton("🌍 Türkçe", callback_data="lang_tr"),
            InlineKeyboardButton("🌍 English", callback_data="lang_en")
        ], [InlineKeyboardButton("⬅️ Geri Dön", callback_data="bot_info")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=language_text,
                                      reply_markup=reply_markup)

    elif query.data in ["lang_tr", "lang_en"]:
        # Set the language
        language_code = query.data.split('_')[1]
        success = language_manager.set_language(language_code)

        if success:
            confirmation_text = ("✅ Dil Türkçe olarak değiştirildi"
                                 if language_code == "tr" else
                                 "✅ Language has been changed to English")

            # Send confirmation as a separate message
            await context.bot.send_message(chat_id=query.message.chat_id,
                                           text=confirmation_text)

            # Show language selection menu again
            language_text = ("👋 Merhaba Kullanıcı İsim Yada ID İşte\n\n"
                             "⚙️ Aşşağıdaki butonlara basarak\n"
                             "Dili değiştirebilirsiniz\n\n"
                             "🌍 [Türkçe] %100\n"
                             "🌍 [English] %83\n\n"
                             "✨ Yeni Diller Eklenecektir Bilginize")
            keyboard = [[
                InlineKeyboardButton("🌍 Türkçe", callback_data="lang_tr"),
                InlineKeyboardButton("🌍 English", callback_data="lang_en")
            ], [InlineKeyboardButton("⬅️ Geri Dön", callback_data="bot_info")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            try:
                await query.edit_message_text(text=language_text,
                                              reply_markup=reply_markup)
            except Exception as e:
                logger.error(f"Failed to update language selection menu: {e}")

    elif query.data == "bot_usage":
        usage_text = ("👑 Kanal Yöneticileri Komutları\n\n"
                      "👮 /admin @User Etikete Sahip Olan\n"
                      "Kullanıcı Kanalda Yetki Alır\n\n"
                      "👮 /admin ID Etikete Sahip Olan\n"
                      "Kullanıcı Kanalda Yetki Alır\n\n"
                      "👑 Kanal Koruma Sistemi\n\n"
                      "📢 Eğer Kanal Admini Bir\n"
                      "Kullanıcıyı Kanaldan Çıkartırsa\n"
                      "Bot Otomatik Olarak Kanaldan\n"
                      "Banlar Ve Kanala Kimi Ve Çıkaran\n"
                      "Kişi Hakkında Bilgi Metini İletir\n\n"
                      "➡️ Örnek: Adlı Admin Tarafından Adlı\n"
                      "Kullanıcı Kanaldan Çıkarıldı Admin\n"
                      "Kanaldan Banlandı\n\n"
                      "📝 Örnek Sadece Tanıtım Olarak\n"
                      "Gösterilmiştir Yazı Stili Değişiktir\n\n"
                      "/kanal yazarak kanal hakkında bilgi edinin")
        keyboard = [[
            InlineKeyboardButton("⬅️ Geri Dön", callback_data="bot_info")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text=usage_text,
                                      reply_markup=reply_markup)


async def channel_post_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages and commands posted in channels"""
    if not update.channel_post:
        return

    message = update.channel_post
    chat_id = update.effective_chat.id

    # Handle admin command
    if message.text and message.text.startswith('/admin'):
        logger.info(f"Processing /admin command in channel {chat_id}")
        logger.info(f"Message sender_chat: {message.sender_chat}")
        logger.info(f"Message from_user: {message.from_user}")

        try:
            # Get list of administrators
            admins = await context.bot.get_chat_administrators(chat_id)
            creator = next((admin for admin in admins if admin.status == "creator"), None)

            if not creator:
                logger.warning(f"Could not find creator for channel {chat_id}")
                return

            # Verify sender is either the owner or the channel itself
            sender_id = None
            if message.from_user:
                sender_id = message.from_user.id
            elif message.sender_chat:
                sender_id = message.sender_chat.id

            # Allow command only from owner or channel
            if sender_id != creator.user.id and sender_id != chat_id:
                error_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text="Only the channel owner can promote members to admin."
                )
                await asyncio.sleep(3)
                await error_msg.delete()
                return

            # Process command arguments
            args = message.text.split()[1:] if len(message.text.split()) > 1 else []
            if not args:
                instruction_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text="Please specify a user to promote with /admin @username or /admin user_id"
                )
                await asyncio.sleep(3)
                await instruction_msg.delete()
                return

            # Process username/user_id
            arg = args[0]
            if arg.startswith('@'):
                target_user_id, target_user_first_name, error_msg = await resolve_username(arg, context, chat_id)
            else:
                target_user_id, target_user_first_name, error_msg = await resolve_user_id(arg, context, chat_id)

            if error_msg:
                error_response = await context.bot.send_message(chat_id=chat_id, text=error_msg)
                await asyncio.sleep(3)
                await error_response.delete()
                if not target_user_id:
                    return

            # Attempt promotion
            success, message_text = await promote_user(chat_id, target_user_id, context)
            response_message = await context.bot.send_message(chat_id=chat_id, text=message_text)

            if success:
                try:
                    await message.delete()
                    await response_message.delete()
                except Exception as e:
                    logger.error(f"Failed to delete messages: {e}")

        except Exception as e:
            logger.error(f"Error in channel_post_handler: {e}", exc_info=True)
            error_msg = await context.bot.send_message(
                chat_id=chat_id,
                text="An error occurred. Please try again later."
            )
            await asyncio.sleep(3)
            await error_msg.delete()


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors caused by updates."""
    logger.error(f"Update {update} caused error: {context.error}")

    # If we have a chat_id, notify about the error
    if update and update.effective_chat:
        chat_id = update.effective_chat.id
        try:
            error_message = (
                "An error occurred while processing your request. "
                f"Error details: {str(context.error)}")
            await context.bot.send_message(chat_id=chat_id, text=error_message)
        except Exception as e:
            logger.error(f"Failed to send error notification: {e}")


async def track_new_member(user_id: int, username: str, first_name: str,
                           chat_id: int):
    """Store information about new channel members"""
    global recent_members
    member_info = {
        'user_id': user_id,
        'username': username,
        'first_name': first_name or "Unknown User",  # Fallback if first_name is None
        'chat_id': chat_id,
        'joined_at': time.time()
    }

    # Add to recent members, maintaining max size
    recent_members.append(member_info)
    if len(recent_members) > MAX_RECENT_MEMBERS:
        recent_members.pop(0)  # Remove oldest member

    # Enhanced logging
    logger.info("=" * 50)
    logger.info("New Member Tracked:")
    logger.info(f"Name: {first_name}")
    logger.info(f"Username: @{username if username else 'None'}")
    logger.info(f"Total tracked members: {len(recent_members)}")
    logger.info("=" * 50)


async def get_channel_info(chat_id: int,
                           context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Fetch and log all available channel member information
    """
    try:
        logger.info("=" * 50)
        logger.info(f"Channel Information for {chat_id}")
        logger.info("=" * 50)

        # Get channel information
        chat = await context.bot.get_chat(chat_id)
        logger.info(f"Channel Title: {chat.title}")
        logger.info(f"Channel Type: {chat.type}")
        logger.info(
            f"Channel Username: @{chat.username if chat.username else 'None'}")

        # Get member count and show tracked subscribers
        try:
            member_count = await context.bot.get_chat_member_count(chat_id)
            logger.info("\nChannel Member Information:")
            logger.info("-" * 30)
            logger.info(f"Total Channel Members: {member_count}")

            # Show recent members with enhanced formatting
            if recent_members:
                logger.info("\n" + "=" * 50)
                logger.info("📱 SUBSCRIBERS LIST (Most Recent First):")
                logger.info("=" * 50)

                # Filter members for this chat and sort by join time (newest first)
                chat_members = [m for m in recent_members if m['chat_id'] == chat_id]
                chat_members.sort(key=lambda x: x['joined_at'], reverse=True)

                for idx, member in enumerate(chat_members, 1):
                    logger.info("\n" + "-" * 40)
                    logger.info(f"📍 Subscriber #{idx}:")
                    logger.info(f"  👤 Name: {member['first_name']}")
                    logger.info(
                        f"  📝 Username: @{member['username'] if member['username'] else 'None'}"
                    )
                    logger.info(
                        f"  ⏰ Joined: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(member['joined_at']))}"
                    )

                logger.info("\n" + "=" * 50)
                logger.info(f"✅ Total Tracked Subscribers: {len(chat_members)}")
                logger.info("=" * 50)
                if len(chat_members) < member_count:
                    logger.info("\nℹ️ Note: Some earlier subscribers are not shown")
                    logger.info("Only new subscribers who joined after bot activation are tracked")
            else:
                logger.info("\n📢 No subscribers tracked yet")
                logger.info("ℹ️ New subscribers will be tracked as they join")

        except Exception as e:
            logger.warning(f"Could not get member count: {e}")

    except Exception as e:
        logger.error(f"Error fetching channel information: {e}")


async def is_bot_admin(chat_id, context):
    """Check if the bot is an admin in the chat/channel"""
    try:
        bot_id = context.bot.id
        bot_member = await context.bot.get_chat_member(chat_id, bot_id)
        return bot_member.status == "administrator"
    except Exception as e:
        logger.error(f"Failed to check bot admin status in {chat_id}: {e}")
        return False

async def bot_self_update(update: ChatMemberUpdated, context: ContextTypes.DEFAULT_TYPE):
    """When bot’s own permissions/status change in a chat."""
    chat = update.chat_member.chat
    old = update.chat_member.old_chat_member
    new = update.chat_member.new_chat_member

    # Critical permissions required for bot operation
    required_perms = [
        "can_promote_members",
        "can_restrict_members",
        "can_manage_chat",
        "can_delete_messages",
        "can_invite_users",
        "can_pin_messages",
        "can_manage_video_chats",
    ]

    # If we are no longer admin, leave immediately
    if not isinstance(new, ChatMemberAdministrator):
        try:
            await context.bot.leave_chat(chat.id)
        except Exception as e:
            logger.error(f"Failed to leave chat: {e}")
        return

    # Check missing permissions
    missing_perms = [perm for perm in required_perms if not getattr(new, perm, False)]

    # Determine if bot previously had full permissions
    had_full_perms = isinstance(old, ChatMemberAdministrator) and all(
        getattr(old, perm, False) for perm in required_perms
    )

    # Case 1: Added without full permissions
    if not had_full_perms and missing_perms:
        logger.warning(f"Added without full permissions. Missing: {missing_perms}")
        try:
            await context.bot.leave_chat(chat.id)
        except Exception as e:
            logger.error(f"Failed to leave chat: {e}")
        return

    # Case 2: Permissions reduced after having full access
    if had_full_perms and missing_perms:
        logger.info("Permissions reduced. Demoting admins and leaving...")
        
        # Demote all admins except owner
        admins = await context.bot.get_chat_administrators(chat.id)
        for admin in admins:
            if isinstance(admin, ChatMemberOwner):
                continue
                
            try:
                await context.bot.promote_chat_member(
                    chat_id=chat.id,
                    user_id=admin.user.id,
                    can_manage_chat=False,
                    can_delete_messages=False,
                    can_manage_video_chats=False,
                    can_restrict_members=False,
                    can_promote_members=False,
                    can_change_info=False,
                    can_pin_messages=False,
                    can_invite_users=False,
                )
            except Exception as e:
                logger.error(f"Failed to demote {admin.user.id}: {e}")

        # Leave the channel
        try:
            await context.bot.send_message(
                chat.id,
                "⚠️ My permissions were reduced. Demoting all admins and leaving!"
            )
            await context.bot.leave_chat(chat.id)
        except Exception as e:
            logger.error(f"Failed to leave chat: {e}")

async def chat_member_update_handler(update: Update,
                                     context: ContextTypes.DEFAULT_TYPE):
    """
    Monitors chat member status changes:
      - Tracks new members joining
      - Automatically grants full rights to a new admin
      - Demotes an admin if they remove (kick/ban) a member
    """
    try:
        chat_member_update = update.chat_member
        chat_id = chat_member_update.chat.id
        chat_type = chat_member_update.chat.type

        # Enhanced debug logging
        logger.info("=" * 50)
        logger.info("Chat Member Update Event")
        logger.info(f"Chat ID: {chat_id}")
        logger.info(f"Chat Type: {chat_type}")
        logger.info(f"Old Status: {chat_member_update.old_chat_member.status}")
        logger.info(f"New Status: {chat_member_update.new_chat_member.status}")
        logger.info("=" * 50)

        new_status = chat_member_update.new_chat_member.status
        old_status = chat_member_update.old_chat_member.status

        # Track new members joining
        if old_status in ["left", "kicked"] and new_status == "member":
            new_member = chat_member_update.new_chat_member.user
            logger.info(
                f"New member detected - Processing: {new_member.first_name} (ID: {new_member.id})"
            )

            await track_new_member(new_member.id, new_member.username,
                                   new_member.first_name, chat_id)

            # Log success and current stats
            logger.info("\n" + "=" * 50)
            logger.info("✅ New Member Successfully Tracked")
            logger.info(f"👤 Name: {new_member.first_name}")
            logger.info(
                f"📝 Username: `@{new_member.username if new_member.username else 'None'}"
            )

            # Show current tracking stats
            member_count = len([m for m in recent_members if m['chat_id'] == chat_id])
            logger.info(f"📊 Current tracked members for chat {chat_id}: {member_count}")
            logger.info("=" * 50)

        # Skip handling if bot doesn't have necessary permissions
        has_permissions, _ = await check_bot_permissions(chat_id, context)
        if not has_permissions:
            logger.warning(
                f"Skipping chat member update handling due to insufficient permissions in {chat_id}"
            )
            return

        # Handle member removal and admin demotion
        if old_status in ["member", "restricted"] and new_status in ["kicked", "banned"]:
            try:
                removed_user_id = chat_member_update.new_chat_member.user.id
                performing_admin = chat_member_update.from_user

                if performing_admin is not None:
                    admin_id = performing_admin.id
                    logger.info(
                        f"Admin {admin_id} removed user {removed_user_id} in chat {chat_id}"
                    )

                    # Demote the admin
                    await context.bot.promote_chat_member(
                        chat_id=chat_id,
                        user_id=admin_id,
                        can_manage_chat=False,
                        can_delete_messages=False,
                        can_manage_video_chats=False,
                        can_promote_members=False,
                        can_change_info=False,
                        can_post_messages=False,
                        can_edit_messages=False,
                        can_invite_users=False,
                    )

                    ## Fix another potential issue with get_chat_member vs get_chat_member
                    try:
                        admin_info = await context.bot.get_chat_member(chat_id, admin_id)
                        admin_name = admin_info.user.first_name
                        notification = f"Admin {admin_name} has been demoted for removing a member."
                        await context.bot.send_message(chat_id=chat_id, text=notification)
                    except Exception as e:
                        logger.error(f"Failed to notify about admin demotion: {e}")
            except Exception as e:
                logger.error(f"Failed to process member removal: {e}")

    except Exception as e:
        logger.error(f"Error in chat member update handler:{e}")


async def find_user_by_username_or_id(
    identifier: Union[str, int],
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: Optional[int] = None
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """
    Enhanced user resolution with better validation and error handling
    Returns (user_id, user_first_name, error_message)
    """
    try:
        logger.info(
            f"Finding user by identifier: {identifier} (type: {type(identifier)})"
        )

        if isinstance(identifier, str):
            # Handle username
            if identifier.startswith('@'):
                return await resolve_username(identifier, context, chat_id)
            # Handle numeric string
            elif identifier.isdigit():
                return await resolve_user_id(int(identifier), context, chat_id)
        elif isinstance(identifier, int):
            return await resolve_user_id(identifier, context, chat_id)

        return None, None, "Invalid identifier. Please provide a valid username (with @) or user ID."
    except Exception as e:
        logger.error(f"Error in find_user_by_username_or_id: {e}")
        return None, None, f"Error processing identifier: {str(e)}"


async def lookup_subscriber(username_or_id: str,
                            context: ContextTypes.DEFAULT_TYPE,
                            chat_id: int) -> str:
    """
    Look up a specific subscriber's information
    Returns formatted string with subscriber details
    """
    try:
        # If it's a username, ensure it has @ prefix
        if isinstance(username_or_id, str) and not username_or_id.startswith('@') and not username_or_id.isdigit():
            username_or_id = f"@{username_or_id}"

        # Try to get member info
        try:
            member = await context.bot.get_chat_member(chat_id, username_or_id)
            if member:
                return (
                    f"Subscriber Information:\n"
                    f"👤 Name: {member.user.first_name}\n"
                    f"📝 Username: @{member.user.username if member.user.username else 'None'}\n"
                    f"🔵 Status: {member.status}\n"
                    f"Note: Join date is only available for members who joined after bot activation."
                )
        except Exception as e:
            logger.warning(f"Failed to get member info: {e}")
            return "Could not find subscriber. Please verify the username/ID is correct."

    except Exception as e:
        logger.error(f"Error in lookup_subscriber: {e}")
        return "An error occurred while looking up the subscriber."


# --- Global variables for tracking recent members ---
recent_members: List[Dict] = []
MAX_RECENT_MEMBERS = 100

# --- Flask Health Check Setup ---
flask_app = Flask("HealthCheck")

@flask_app.route("/health")
def health_check():
    # You can include any details you want here; for example, number of tracked recent members.
    return {"status": "operational", "recent_members": len(recent_members)}, 200

def run_flask():
    flask_app.run(host="0.0.0.0", port=8000)


def main():
    try:
        # Start Flask health check server in a separate daemon thread.
        threading.Thread(target=run_flask, daemon=True).start()

        app = ApplicationBuilder().token(BOT_TOKEN).build()
        app.add_handler(ChatMemberHandler(bot_self_update, ChatMemberHandler.MY_CHAT_MEMBER))
        # Register command handlers
        app.add_handler(CommandHandler("start", start_command))
        app.add_handler(CommandHandler("admin", admin_command))

        # Register channel post handler
        app.add_handler(MessageHandler(filters.ChatType.CHANNEL, channel_post_handler))

        # Register chat member update handler
        app.add_handler(ChatMemberHandler(chat_member_update_handler, ChatMemberHandler.CHAT_MEMBER))

        # Register callback query handler for inline buttons
        app.add_handler(CallbackQueryHandler(button_handler))

        # Register error handler
        app.add_error_handler(error_handler)

        logger.info("Bot is running... Press Ctrl+C to stop.")
        app.run_polling()
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")


if __name__ == "__main__":
    main()
