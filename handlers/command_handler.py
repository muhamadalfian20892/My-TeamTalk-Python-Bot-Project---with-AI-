
import logging
import re
from TeamTalk5 import TextMsgType, ttstr, UserRight
from datetime import datetime
from utils import format_uptime

from . import user_commands, ai_commands, poll_commands, communication_commands, utility_commands
from .admin import bot_control, config_management, feature_toggles, user_management, channel_management

COMMAND_MAP_PM = user_commands.COMMAND_MAP_PM
ADMIN_COMMANDS = user_commands.ADMIN_COMMANDS

COMMAND_MAP_CHANNEL = {
    "h": user_commands.handle_help,
    "w": communication_commands.handle_weather,
    "c": ai_commands.handle_channel_ai,
    "!poll": poll_commands.handle_poll_create,
    "!vote": poll_commands.handle_vote,
    "!results": poll_commands.handle_results,
    "!time": utility_commands.handle_time,
}

def handle_message(bot, textmessage, full_message_text):
    msg_from_id = textmessage.nFromUserID
    msg_type = textmessage.nMsgType
    msg_channel_id = textmessage.nChannelID
    
    sender_nick = f"UserID_{msg_from_id}"
    try:
        sender_user = bot.getUser(msg_from_id)
        if sender_user and sender_user.nUserID == msg_from_id:
            sender_nick = ttstr(sender_user.szNickname)
    except Exception: pass

    # --- Last Seen and AFK Handling ---
    action_text = ""
    if msg_type == TextMsgType.MSGTYPE_CHANNEL:
        action_text = "sending a message in channel"
    elif msg_type == TextMsgType.MSGTYPE_USER:
        action_text = "sending a private message"
    
    if action_text:
        bot.data_service.update_last_seen(msg_from_id, sender_nick, action_text)
        # If user was AFK, remove their status and notify them
        if bot.data_service.remove_afk(msg_from_id):
            bot._send_pm(msg_from_id, "Welcome back! Your AFK status has been removed.")
            logging.info(f"User {sender_nick} is no longer AFK.")

    # --- AFK Auto-Reply Logic ---
    if msg_type == TextMsgType.MSGTYPE_USER:
        afk_recipient = bot.data_service.get_afk_user(textmessage.nToUserID)
        if afk_recipient:
            try:
                afk_time = datetime.fromisoformat(afk_recipient['timestamp'])
                time_ago = format_uptime(datetime.now().timestamp() - afk_time.timestamp())
                reply = (f"[Auto-Reply] User '{afk_recipient['nick']}' is AFK (since {time_ago} ago).\n"
                         f"Reason: {afk_recipient['reason']}")
                bot._send_pm(msg_from_id, reply)
            except (ValueError, TypeError):
                # Fallback if timestamp is weird
                bot._send_pm(msg_from_id, f"[Auto-Reply] User is AFK. Reason: {afk_recipient['reason']}")
            return # Stop further processing of the message to the AFK user

    log_and_process(bot, msg_type, msg_from_id, msg_channel_id, sender_nick, full_message_text)

def log_and_process(bot, msg_type, msg_from_id, msg_channel_id, sender_nick, full_message_text):
    process_commands = False
    
    if msg_type == TextMsgType.MSGTYPE_CHANNEL:
        # --- FIX: Check if bot is in the specific channel the message came from ---
        if msg_channel_id in bot._in_channel_ids:
            process_commands = True
    elif msg_type == TextMsgType.MSGTYPE_USER:
        process_commands = True
    else: return

    if not process_commands: return
    
    if msg_type == TextMsgType.MSGTYPE_CHANNEL and check_word_filter(bot, msg_from_id, msg_channel_id, sender_nick, full_message_text):
        return

    # For channel messages, command can start with '!' or '/'
    is_channel_command = False
    if msg_type == TextMsgType.MSGTYPE_CHANNEL:
        if full_message_text.startswith('!') or full_message_text.startswith('/'):
            is_channel_command = True
            full_message_text = full_message_text[1:]

    parts = full_message_text.strip().split(maxsplit=1)
    command_word = parts[0].lower() if parts else ""
    args_str = parts[1] if len(parts) > 1 else ""

    if not command_word: return
    
    if bot.bot_locked and command_word not in bot.UNBLOCKABLE_COMMANDS:
        if msg_type == TextMsgType.MSGTYPE_USER: bot._send_pm(msg_from_id, f"Command ignored; bot is locked."); return
    if command_word in bot.blocked_commands and command_word not in ['block', 'unblock']:
        if msg_type == TextMsgType.MSGTYPE_USER: bot._send_pm(msg_from_id, f"Command '{command_word}' is blocked."); return

    handler_func = None
    if msg_type == TextMsgType.MSGTYPE_USER:
        handler_func = user_commands.ALL_COMMANDS.get(command_word)
    elif msg_type == TextMsgType.MSGTYPE_CHANNEL and is_channel_command:
        handler_func = COMMAND_MAP_CHANNEL.get(f"!{command_word}") or COMMAND_MAP_CHANNEL.get(command_word)


    if handler_func:
        if command_word in ADMIN_COMMANDS and not bot._is_admin(msg_from_id):
            bot._send_pm(msg_from_id, f"Error: You are not authorized to use '{command_word}'.")
            logging.warning(f"Unauthorized admin command '{command_word}' by {sender_nick}.")
            return
        
        try:
            handler_func(bot=bot, msg_from_id=msg_from_id, args_str=args_str, channel_id=msg_channel_id, sender_nick=sender_nick, command=command_word, msg_type=msg_type)
        except Exception as e:
            logging.error(f"Error executing command '{command_word}': {e}", exc_info=True)
            bot._send_pm(msg_from_id, f"An unexpected error occurred executing '{command_word}'.")

def check_word_filter(bot, user_id, channel_id, user_nick, message):
    if not bot.filter_enabled or not bot.filtered_words: return False
    
    msg_lower = message.lower()
    found_bad_word = next((word for word in bot.filtered_words if re.search(r'\b' + re.escape(word) + r'\b', msg_lower, re.IGNORECASE)), None)
    
    if found_bad_word:
        bot.warning_counts[user_id] = bot.warning_counts.get(user_id, 0) + 1
        warning_msg = f"Warning {bot.warning_counts[user_id]}/3 for {user_nick}: Please avoid inappropriate language."
        bot._send_channel_message(channel_id, warning_msg)

        if bot.warning_counts[user_id] >= 3:
            if bot.my_rights & UserRight.USERRIGHT_KICK_USERS:
                bot.doKickUser(user_id, channel_id)
                bot._send_channel_message(channel_id, f"User {user_nick} kicked after 3 warnings.")
            else:
                bot._send_channel_message(channel_id, f"{user_nick} has 3 warnings, but bot cannot kick.")
            bot.warning_counts[user_id] = 0
        return True
    return False