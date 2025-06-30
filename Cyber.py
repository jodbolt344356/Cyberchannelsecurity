import asyncio
import logging
import os
import json
import time
from datetime import datetime

from flask import Flask
import threading

from pyrogram import Client, filters, enums, idle
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatPrivileges, Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import BotMethodInvalid, RPCError, AuthKeyUnregistered
from pyrogram.errors import UserNotParticipant, FloodWait, UserAdminInvalid, UsernameNotOccupied, PeerIdInvalid, ChatAdminRequired

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot configuration
API_ID = 21547048
API_HASH = "aaca55f2ee5af88fbe9f589393a7b9b6" # Ensure this is your correct API Hash from my.telegram.org
BOT_TOKEN = "7396319401:AAER7cmrT6jQeWrFID1uctclOaINd7c5a38" # Ensure this is your correct Bot Token from BotFather

# Initialize the bot with better connection settings
app = Client(
    "admin_monitor_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    sleep_threshold=60,
    max_concurrent_transmissions=1
)

# Store monitored channels and their admins to watch (this can also be moved to DB if needed)
monitored_channels = {}
# Keep track of recent member removals (this is in-memory, will reset on redeploy)
recent_removals = {}

# Connection retry configuration
MAX_RETRIES = 5
RETRY_DELAY = 30
connection_retries = 0

# --- NEW: Function to generate the unified main menu keyboard ---
def get_main_menu_keyboard():
    return InlineKeyboardMarkup(
        [
            # Row 1: Usage and Owner (formerly Bot Stats)
            [
                InlineKeyboardButton("🚀 ᴜꜱᴀɢᴇ", callback_data="usage"),
                InlineKeyboardButton("👤 ᴏᴡɴᴇʀ", url="https://t.me/ogxcodex") # MODIFIED: Changed text and URL
            ],
            # Row 2: Main Channel Info
            [
                InlineKeyboardButton("📢 ᴄʜᴀɴɴᴇʟ ɪɴꜰᴏ", url="https://t.me/teleprotectorbot_info")
            ],
            # Row 3: Other Bots (each on its own row for better horizontal fit)
            [
                InlineKeyboardButton("🤖 ᴀᴜᴛᴏ ʀᴇᴀᴄᴛɪᴏɴ ʙᴏᴛ ", url="https://t.me/TGautoreactionbot")
            ],
            [
                InlineKeyboardButton("✅ ʀᴇQᴜᴇꜱᴛ ᴀᴘᴘʀᴏᴠᴀʟ ʙᴏᴛ", url="https://t.me/TeleApproveUserBot")
            ],
            [
                InlineKeyboardButton("🔒 ᴄʜᴀɴɴᴇʟ ꜱᴇᴄᴜʀɪᴛʏ ʙᴏᴛ", url="https://t.me/CyberChanneISecurity_bot")
            ]
        ]
    )

# --- NEW: Function to generate the unified main menu text ---
def get_main_menu_text():
    return (
        "**🛡️ Iɴᴛʀᴏᴅᴜᴄɪɴɢ Cʜᴀɴɴᴇʟ Pʀᴏᴛᴇᴄᴛɪᴏɴ Bᴏᴛ**\n\n"
        "Iꜰ Aɴʏ Aᴅᴍɪɴ Rᴇᴍᴏᴠᴇs Mᴇᴍʙᴇʀs, Tʜᴇʏ Wɪʟʟ Bᴇ Aᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ Dᴇᴍᴏᴛᴇᴅ Fʀᴏᴍ Aᴅᴍɪɴ.\n\n"
        "**⚙️ Hᴏᴡ Tᴏ Usᴇ:**\n"
        "1. Mᴀᴋᴇ Mᴇ Aᴅᴍɪɴ Iɴ Yᴏᴜʀ Cʜᴀɴɴᴇʟ.\n\n"
        "➜ Usᴇ `/admin {username}` Tᴏ Pʀᴏᴍᴏᴛᴇ Usᴇʀ Iɴ Cʜᴀɴɴᴇʟ.\n\n"
        "Kᴇᴇᴘ Yᴏᴜʀ ᴄʜᴀɴɴᴇʟ Sᴀꜰᴇ Fʀᴏᴍ Rɪꜱᴋʏ Aᴅᴍɪɴꜱ."
    )


async def safe_api_call(func, *args, **kwargs):
    """Wrapper for safe API calls with retry logic"""
    for attempt in range(3):
        try:
            return await func(*args, **kwargs)
        except RPCError as e:
            logger.warning(f"API call failed (attempt {attempt + 1}): {e}")
            if attempt < 2:
                await asyncio.sleep(5 * (attempt + 1))
            else:
                raise
        except FloodWait as e:
            logger.warning(f"Flood wait: {e.value} seconds. Waiting...")
            await asyncio.sleep(e.value)
        except ConnectionError as e:
            logger.warning(f"Connection error (attempt {attempt + 1}): {e}")
            if attempt < 2:
                await asyncio.sleep(5 * (attempt + 1))
            else:
                raise
        except Exception as e:
            logger.error(f"Unexpected error in API call: {e}")
            raise

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    try:
        # MODIFIED: Use the new unified functions
        keyboard = get_main_menu_keyboard()
        text = get_main_menu_text()
        
        await safe_api_call(
            message.reply,
            text,
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")

@app.on_callback_query()
async def handle_callback(client, callback_query):
    try:
        data = callback_query.data

        if data == "usage":
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back")]]
            )
            await safe_api_call(
                callback_query.message.edit_text,
                "**📚 Bot Usage Guide**\n\n"
                "**Available Commands:**\n"
                "• `/start` - Show the welcome message and main menu.\n"
                "• `/help` - Display this usage guide.\n"
                "• `/admin @username` or `/admin username` - Promote a user to admin in your channel. "
                "*(Use this command directly in your channel.)*\n\n"
                "**How the Bot Works:**\n"
                "1. **Admin Rights:** Ensure the bot has full admin permissions in your channel (including 'Add New Admins' and 'Manage Join Requests').\n"
                "2. **Admin Monitoring:** The bot monitors admin actions. If an admin removes a member, they will be automatically demoted.\n"
                "**Important:** Commands like `/admin` must be used directly within the channel you wish to manage, by an existing administrator."
                ,
                reply_markup=keyboard
            )

        elif data == "stats_overview": # This callback data is now effectively unused by the button
            # MODIFIED: Simplified stats overview as no pending requests are tracked
            stats_text = (
                f"**📊 Bot Statistics Overview**\n\n"
                f"**Pending Join Requests:** `Not tracked by this bot version.`\n\n"
                f"This bot version focuses on admin monitoring and promoting users, not managing join requests."
            )
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back")]]
            )
            await safe_api_call(callback_query.message.edit_text, stats_text, reply_markup=keyboard)

        elif data == "back":
            # MODIFIED: Use the new unified functions
            keyboard = get_main_menu_keyboard()
            text = get_main_menu_text()
            await safe_api_call(
                callback_query.message.edit_text,
                text,
                reply_markup=keyboard
            )

        await safe_api_call(callback_query.answer) # Acknowledge the callback query
    except Exception as e:
        logger.error(f"Error in callback handler: {e}")

@app.on_message(filters.command("help") & filters.private)
async def help_command(client, message):
    try:
        await safe_api_call(
            message.reply,
            "**📚 Bot Usage Guide**\n\n"
            "**Available Commands:**\n"
            "• `/start` - Show the welcome message and main menu.\n"
            "• `/help` - Display this usage guide.\n"
            "• `/admin @username` or `/admin username` - Promote a user to admin in your channel. "
            "*(Use this command directly in your channel.)*\n\n"
            "**How the Bot Works:**\n"
            "1. **Admin Rights:** Ensure the bot has full admin permissions in your channel (including 'Add New Admins' and 'Manage Join Requests').\n"
            "2. **Admin Monitoring:** The bot monitors admin actions. If an admin removes a member, they will be automatically demoted.\n"
            "**Important:** Commands like `/admin` must be used directly within the channel you wish to manage, by an existing administrator."
        )
    except Exception as e:
        logger.error(f"Error in help command: {e}")

async def get_user_id_from_username(client, username):
    """Helper function to convert a username to user_id using Pyrogram's API"""
    try:
        # Remove @ if present
        username = username.lstrip('@')

        # Try to get user directly by username
        try:
            user = await safe_api_call(client.get_users, username)
            return user.id, user.first_name
        except (UsernameNotOccupied, PeerIdInvalid) as e:
            logger.error(f"Error getting user by username: {e}")
            
            # Try resolving username using resolve_peer method
            try:
                peer = await safe_api_call(client.resolve_peer, username)
                if hasattr(peer, 'user_id'):
                    user = await safe_api_call(client.get_users, peer.user_id)
                    return user.id, user.first_name
                else:
                    return None, None
            except Exception as e2:
                logger.error(f"Error resolving peer: {e2}")
                return None, None
    except Exception as e:
        logger.error(f"General error in username resolution: {e}")
        return None, None

# Helper function to check if the sender is an admin
async def is_sender_admin(client, chat_id, message: Message):
    if message.from_user:
        # Command sent by a user
        try:
            member = await safe_api_call(client.get_chat_member, chat_id, message.from_user.id)
            return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        except Exception as e:
            logger.error(f"Error checking admin status for user {message.from_user.id} in {chat_id}: {e}")
            return False
    elif message.sender_chat and message.sender_chat.type == enums.ChatType.CHANNEL:
        # Command sent as the channel itself.
        # If the bot receives this, it implies the channel has admin rights.
        # We can also check if the bot itself is an admin in this channel.
        try:
            bot_member = await safe_api_call(client.get_chat_member, chat_id, (await client.get_me()).id)
            return bot_member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        except Exception as e:
            logger.error(f"Error checking bot's admin status in channel {chat_id}: {e}")
            return False
    return False


# Handle admin command in any chat (private, group, or channel)
@app.on_message(filters.command("admin"))
async def promote_user(client, message: Message):
    try:
        # Check if command has the username
        if len(message.command) < 2:
            if message.chat.type == enums.ChatType.PRIVATE:
                await safe_api_call(message.reply, "Please provide a username to admin. Example: `/admin @username`")
            return

        # Extract the username
        username = message.command[1].lstrip('@')
        
        # Get user ID from username using our helper function
        user_id, user_first_name = await get_user_id_from_username(client, username)
        
        if not user_id:
            if message.chat.type == enums.ChatType.PRIVATE:
                await safe_api_call(message.reply, f"Couldn't find user with username @{username}. Please check the username and try again.")
            await delete_message_safely(client, message)
            return
        
        # Try to promote the user in the current chat if it's a channel or supergroup
        if message.chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]:
            # Check if the sender is an admin
            if not await is_sender_admin(client, message.chat.id, message):
                await safe_api_call(message.reply, "❌ You must be an administrator to use this command.")
                await delete_message_safely(client, message)
                return

            try:
                # Delete the command message immediately
                await delete_message_safely(client, message)

                # Promote the user in this channel
                await safe_api_call(
                    client.promote_chat_member,
                    message.chat.id,
                    user_id,
                    privileges=ChatPrivileges(
                        can_change_info=True,
                        can_post_messages=True,
                        can_edit_messages=True,
                        can_delete_messages=True,
                        can_invite_users=True,
                        can_restrict_members=True,
                        can_promote_members=False, # Bot should not grant promote rights to others
                        can_manage_chat=True,
                        can_manage_video_chats=True
                    )
                )
                
                # Send a confirmation message and delete it after 5 seconds
                confirm_msg = await safe_api_call(
                    client.send_message,
                    message.chat.id, 
                    f"✅ Successfully promoted {user_first_name} in this channel!"
                )
                
                # Schedule message deletion
                asyncio.create_task(delete_message_after(client, confirm_msg, 5))

                # Add this channel to monitoring list if not already
                if message.chat.id not in monitored_channels:
                    monitored_channels[message.chat.id] = {}
            
            except ChatAdminRequired:
                logger.error(f"Bot is not admin in channel {message.chat.id}")
                await safe_api_call(
                    client.send_message,
                    message.chat.id,
                    "❌ I need to be an administrator with full rights to promote users in this channel."
                )
            except UserAdminInvalid:
                confirm_msg = await safe_api_call(
                    client.send_message,
                    message.chat.id, 
                    f"❌ {user_first_name} is already an admin or can't be promoted."
                )
                asyncio.create_task(delete_message_after(client, confirm_msg, 5))
            except Exception as e:
                logger.error(f"Error promoting user: {e}")
                if message.chat.type == enums.ChatType.PRIVATE:
                    await safe_api_call(message.reply, f"❌ An error occurred: {str(e)}")
        else:
            # If in private chat, explain how to use the command
            await safe_api_call(message.reply, "Please add me to a channel and use the `/admin` command directly in the channel.")
    
    except Exception as e:
        logger.error(f"Error in admin command: {e}")
        if message.chat.type == enums.ChatType.PRIVATE:
            try:
                await safe_api_call(message.reply, f"❌ An error occurred: {str(e)}")
            except:
                pass

async def delete_message_safely(client, message):
    """Try to delete a message safely, handling any errors."""
    try:
        await safe_api_call(message.delete)
    except Exception as e:
        logger.error(f"Could not delete message: {e}")

async def delete_message_after(client, message, seconds):
    """Delete a message after specified seconds"""
    await asyncio.sleep(seconds)
    await delete_message_safely(client, message)

@app.on_chat_member_updated()
async def handle_ban_detection(client, update):
    try:
        chat = update.chat
        old_member = update.old_chat_member
        new_member = update.new_chat_member

        # Ensure old_member and new_member are not None before proceeding
        if not old_member or not new_member:
            logger.debug(f"Skipping ban detection: old_member or new_member is None in chat {chat.id}")
            return

        # Determine the ID of the entity that performed the action
        action_performer_id = None
        performer_name = "Unknown"

        if update.from_user:
            action_performer_id = update.from_user.id
            performer_name = update.from_user.first_name
        elif update.sender_chat and update.sender_chat.type == enums.ChatType.CHANNEL: # Action performed by the channel itself
            action_performer_id = update.sender_chat.id
            performer_name = update.sender_chat.title
        
        if not action_performer_id:
            logger.debug(f"Skipping ban detection: Could not identify action performer for chat {chat.id}")
            return

        # Detect bans (not voluntary leaves)
        if (
            new_member.status == ChatMemberStatus.BANNED
            and old_member.status != ChatMemberStatus.BANNED
        ):
            # Ignore bot's own actions
            bot_id = (await safe_api_call(client.get_me)).id
            if action_performer_id == bot_id:
                return

            # Check if action performer is the owner
            # Note: get_chat_member works for both user and channel IDs
            try:
                performer_member = await safe_api_call(client.get_chat_member, chat.id, action_performer_id)
                if performer_member and performer_member.status == ChatMemberStatus.OWNER:
                    return # Owner can ban without demotion
            except Exception as e:
                logger.warning(f"Could not get chat member status for performer {action_performer_id} in {chat.id}: {e}")
                # If we can't get status, we might proceed with demotion as a precaution,
                # or log and skip. For now, let's log and skip to avoid errors.
                return


            # Demote the admin (remove all privileges)
            await safe_api_call(
                client.promote_chat_member,
                chat.id,
                action_performer_id, # Use the identified performer ID
                privileges=ChatPrivileges(
                    can_manage_chat=False,
                    can_post_messages=False,
                    can_edit_messages=False,
                    can_delete_messages=False,
                    can_restrict_members=False,
                    can_promote_members=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                    can_manage_video_chats=False
                )
            )

            # Send permanent notification (no deletion)
            await safe_api_call(
                client.send_message,
                chat.id,
                f"⚠️ Admin {performer_name} was DEMOTED for banning {old_member.user.first_name}!"
            )

    except ChatAdminRequired:
        logger.error("Bot lacks permissions to demote admins!")
    except Exception as e:
        logger.error(f"Ban detection error: {e}")

async def handle_connection_error():
    """Handle connection errors with exponential backoff"""
    global connection_retries
    connection_retries += 1
    
    if connection_retries > MAX_RETRIES:
        logger.error(f"Max retries ({MAX_RETRIES}) exceeded. Restarting bot...")
        connection_retries = 0
        return False # Indicate that bot should restart
    
    delay = min(RETRY_DELAY * (2 ** (connection_retries - 1)), 300)  # Max 5 minutes
    logger.warning(f"Connection error. Retry {connection_retries}/{MAX_RETRIES} in {delay} seconds...")
    await asyncio.sleep(delay)
    return True

@app.on_chat_join_request()
async def handle_join_request(client, update):
    chat_id = update.chat.id
    user = update.from_user
    
    logger.info(f"New join request in chat {chat_id} from user {user.id} ({user.first_name})")

    # --- MODIFIED: Use the new unified functions ---
    try:
        keyboard = get_main_menu_keyboard()
        text = get_main_menu_text()

        await safe_api_call(
            client.send_message,
            user.id,  # Send to the user who requested to join
            text,
            reply_markup=keyboard
        )
        logger.info(f"Custom menu sent to user {user.id} after join request.")
    except Exception as e:
        logger.error(f"Error sending custom menu to user {user.id} after join request: {e}")

def run_flask_server():
    """Create a Flask app for health checks."""
    app_flask = Flask(__name__)

    @app_flask.route('/')
    def index():
        logger.info("Index route '/' was hit.")
        return "Welcome to the bot server!", 200

    @app_flask.route('/health')
    def health_check():
        logger.info("Health check '/health' was hit.")
        return "Bot is running", 200

    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Flask server on port {port}...")
    app_flask.run(host="0.0.0.0", port=port)
    
async def start_bot():
    """Start bot with automatic retry on connection failure"""
    global connection_retries
    
    while True:
        try:
            await app.start()
            bot_info = await app.get_me()
            logger.info(f"Bot @{bot_info.username} started!")
            connection_retries = 0  # Reset on successful connection
            
            try:
                await idle() # Run forever
            finally:
                await app.stop()

        except AuthKeyUnregistered:
            logger.error("Bot token is invalid! Please check your BOT_TOKEN.")
            break
        except (RPCError, ConnectionError) as e:
            logger.error(f"Connection error: {e}")
            should_retry = await handle_connection_error()
            if not should_retry:
                break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            should_retry = await handle_connection_error()
            if not should_retry:
                break

if __name__ == "__main__":
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask_server)
    flask_thread.daemon = True # Allow the main program to exit even if thread is running
    flask_thread.start()

    # Start the Telegram bot
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped!")
    except Exception as e:
        logger.critical(f"Main loop error: {e}")
    finally:
        pass # Added pass to fix IndentationError
