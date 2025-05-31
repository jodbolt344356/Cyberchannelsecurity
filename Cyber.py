import asyncio
import logging
import os
from flask import Flask
import threading
from pyrogram import Client, filters, enums ,idle
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatPrivileges, Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import BotMethodInvalid, RPCError
from pyrogram.errors import UserNotParticipant, FloodWait, UserAdminInvalid, UsernameNotOccupied, PeerIdInvalid, ChatAdminRequired

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot configuration
API_ID = 21547048
API_HASH = "aaca55f2ee5af88fbe9f589393a7b9b6"
BOT_TOKEN = "7396319401:AAER7cmrT6jQeWrFID1uctclOaINd7c5a38"

# Initialize the bot
app = Client(
    "admin_monitor_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# Store monitored channels and their admins to watch
monitored_channels = {}
# Keep track of recent member removals
recent_removals = {}

@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🚀 Usage", callback_data="usage"),
                InlineKeyboardButton("👤 Owner", url="https://t.me/ogxcodex")
            ]
        ]
    )
    
    await message.reply(
        "**🛡 Hello Dear, I'm a Protection Bot**\n"
        "**I can help manage your Channel!**\n\n"
        "**Features:**\n"
        "1) **Manage admin permissions** 📊\n"
        "2) **Monitor admin activities** 👥\n\n"
        "**Installation Steps:**\n"
        "1) **Add Me to Your Channel** ➕\n"
        "2) **Make Me an Administrator with full rights** ⚡\n"
        "3) **Use /admin @username to admin admins** 📋\n\n"
        "**Note: Only channel admins can use the /admin command.**\n\n"
        "**#Sᴀᴠɪᴏᴜʀ**",
        reply_markup=keyboard
    )

@app.on_callback_query()
async def handle_callback(client, callback_query):
    data = callback_query.data

    if data == "usage":
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
        )
        await callback_query.message.edit_text(
            "**📚 Admin Monitor Bot Help**\n\n"
            "**Available Commands:**\n"
            "• `/start` - Start the bot\n"
            "• `/admin @username` or `/admin username` - Promote a user to admin in your channel\n"
            "• `/help` - Show this help message\n\n"
            "**How it works:**\n"
            "1. **Add the bot to your channel as an admin with all permissions**\n"
            "2. **The bot will automatically monitor for admin actions**\n"
            "3. **If any admin removes members, they will be automatically removed**\n"
            "4. **Use the promote command directly in the channel to promote users**\n\n"
            "**For the promote command to work, the bot must be an admin in the channel.**",
            reply_markup=keyboard
        )

    elif data == "back":
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("📚 Usage", callback_data="usage"),
                    InlineKeyboardButton("📢 Channel", url="https://t.me/teleprotectorbot_info")
                ]
            ]
        )
        await callback_query.message.edit_text(
            "**🛡 Hello Dear, I'm a Protection Bot**\n"
            "**I can help manage your Channel!**\n\n"
            "**Features:**\n"
            "1) **Manage admin permissions** 📊\n"
            "2) **Monitor admin activities** 👥\n\n"
            "**Installation Steps:**\n"
            "1) **Add Me to Your Channel** ➕\n"
            "2) **Make Me an Administrator with full rights** ⚡\n"
            "3) **Use /admin @username to promote admins** 📋\n\n"
            "**Note: Only channel admins can use the /admin command.**\n\n"
            "**#Sᴀᴠɪᴏᴜʀ**",
            reply_markup=keyboard
        )

        
@app.on_message(filters.command("help") & filters.private)
async def help_command(client, message):
    await message.reply(
        "📚 **Admin Monitor Bot Help**\n\n"
        "**Available Commands:**\n"
        "• `/start` - Start the bot\n"
        "• `/admin @username` or `/admin username` - admin a user to admin in your channel\n"
        "• `/help` - Show this help message\n\n"
        "**How it works:**\n"
        "1. Add the bot to your channel as an admin with all permissions\n"
        "2. The bot will automatically monitor for admin actions\n"
        "3. If any admin removes members, they will be automatically removed\n"
        "4. Use the promote command directly in the channel to promote users\n\n"
        "For the promote command to work, the bot must be an admin in the channel."
    )

async def get_user_id_from_username(client, username):
    """Helper function to convert a username to user_id using Pyrogram's API"""
    try:
        # Remove @ if present
        username = username.lstrip('@')
        
        # Try to get user directly by username
        try:
            user = await client.get_users(username)
            return user.id, user.first_name
        except (UsernameNotOccupied, PeerIdInvalid) as e:
            logger.error(f"Error getting user by username: {e}")
            
            # Try resolving username using resolve_peer method
            try:
                peer = await client.resolve_peer(username)
                if hasattr(peer, 'user_id'):
                    user = await client.get_users(peer.user_id)
                    return user.id, user.first_name
                else:
                    return None, None
            except Exception as e2:
                logger.error(f"Error resolving peer: {e2}")
                return None, None
    except Exception as e:
        logger.error(f"General error in username resolution: {e}")
        return None, None

# Handle promote command in any chat (private, group, or channel)
@app.on_message(filters.command("admin"))
async def promote_user(client, message: Message):
    try:
        # Check if command has the username
        if len(message.command) < 2:
            if message.chat.type == enums.ChatType.PRIVATE:
                await message.reply("⚠️ Please provide a username to admin. Example: `/admin @username`")
            return

        # Extract the username
        username = message.command[1].lstrip('@')
        
        # Get user ID from username using our helper function
        user_id, user_first_name = await get_user_id_from_username(client, username)
        
        if not user_id:
            if message.chat.type == enums.ChatType.PRIVATE:
                await message.reply(f"❌ Could not find user with username @{username}. Please check the username and try again.")
            await delete_message_safely(client, message)
            return
        
        # Try to promote the user in the current chat if it's a channel or supergroup
        if message.chat.type in [enums.ChatType.CHANNEL, enums.ChatType.SUPERGROUP]:
            try:
                # Delete the command message immediately
                await delete_message_safely(client, message)
                
                # Promote the user in this channel
                await client.promote_chat_member(
                    message.chat.id,
                    user_id,
                    privileges=ChatPrivileges(
                        can_change_info=True,
                        can_post_messages=True,
                        can_edit_messages=True,
                        can_delete_messages=True,
                        can_invite_users=True,
                        can_restrict_members=True,
                        can_promote_members=False,
                        can_manage_chat=True,
                        can_manage_video_chats=True
                    )
                )
                
                # Send a confirmation message and delete it after 5 seconds
                confirm_msg = await client.send_message(
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
            except UserAdminInvalid:
                confirm_msg = await client.send_message(
                    message.chat.id, 
                    f"❌ {user_first_name} is already an admin or can't be promoted."
                )
                asyncio.create_task(delete_message_after(client, confirm_msg, 5))
            except Exception as e:
                logger.error(f"Error promoting user: {e}")
                if message.chat.type == enums.ChatType.PRIVATE:
                    await message.reply(f"❌ An error occurred: {str(e)}")
        else:
            # If in private chat, explain how to use the command
            await message.reply("Please add me to a channel and use the `/admin` command directly in the channel.")
    
    except Exception as e:
        logger.error(f"Error in promote command: {e}")
        if message.chat.type == enums.ChatType.PRIVATE:
            await message.reply(f"❌ An error occurred: {str(e)}")

async def delete_message_safely(client, message):
    """Try to delete a message safely, handling any errors"""
    try:
        await message.delete()
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

        # Detect bans (not voluntary leaves)
        if (
            new_member.status == ChatMemberStatus.BANNED
            and old_member.status != ChatMemberStatus.BANNED
            and update.from_user  # Ensure admin action
        ):
            admin_id = update.from_user.id
            banned_user = old_member.user

            # Ignore bot's own actions
            bot_id = (await client.get_me()).id
            if admin_id == bot_id:
                return

            # Check if admin is owner
            admin_member = await client.get_chat_member(chat.id, admin_id)
            if admin_member.status == ChatMemberStatus.OWNER:
                return

            # Demote the admin (remove all privileges)
            await client.promote_chat_member(
                chat.id,
                admin_id,
                privileges=ChatPrivileges(
                    can_manage_chat=False,
                    can_post_messages=False,
                    can_edit_messages=False,
                    can_delete_messages=False,
                    can_restrict_members=False,
                    can_promote_members=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                    can_manage_video_chats=False
                )
            )

            # Send permanent notification (no deletion)
            await client.send_message(
                chat.id,
                f"🚫 Admin {update.from_user.first_name} was DEMOTED for banning {banned_user.first_name}!"
            )

    except ChatAdminRequired:
        logger.error("Bot lacks permissions to demote admins!")
    except Exception as e:
        logger.error(f"Ban detection error: {e}")
        
def run_flask_server():
    # Create a Flask app for health checks.
    app = Flask(__name__)

    @app.route('/')
    def index():
        logger.info("Index route '/' was hit.")
        return "Welcome to the bot server!", 200

    @app.route('/health')
    def health_check():
        logger.info("Health check '/health' was hit.")
        return "Bot is running", 200

    # Use the port provided by the environment variable.
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting Flask server on port {port}...")
    app.run(host="0.0.0.0", port=port)
    

async def start_bot():
    await app.start()
    bot_info = await app.get_me()
    logger.info(f"Bot @{bot_info.username} started!")
    
    try:
        await idle()  # Run forever
    finally:
        await app.stop()

if __name__ == "__main__":
    # Start Flask server in a separate thread
    flask_thread = threading.Thread(target=run_flask_server)
    flask_thread.daemon = True
    flask_thread.start()

    # Start the Telegram bot
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped!")

