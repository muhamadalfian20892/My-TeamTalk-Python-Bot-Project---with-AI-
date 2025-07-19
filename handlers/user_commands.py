import time
import sys
import os
from TeamTalk5 import UserRight, TT_STRLEN, ttstr, LOADED_TT_LIB
from utils import format_uptime

from . import ai_commands, poll_commands, communication_commands, utility_commands, user_status_commands
from .admin import bot_control, config_management, feature_toggles, user_management, channel_management, diagnostic_commands

def handle_help(bot, msg_from_id, **kwargs):
    is_admin = bot._is_admin(msg_from_id)
    help_lines = ["""--- Bot Commands (Send via PM) ---"""]

    # Standard User Commands
    help_lines.append("- h: Show this help.")
    help_lines.append("- ping: Check if the bot is responding.")
    help_lines.append("- info: Display bot status and server info.")
    help_lines.append("- whoami: Show your user info.")
    help_lines.append("- rights: Show the bot's permissions.")
    help_lines.append("- cn <new_nick>: Change bot's nickname.")
    help_lines.append("- cs <new_status>: Change bot's status.")
    help_lines.append("- w <location>: Get weather (also /w in channel).")
    help_lines.append("- !time <loc>: Get time for a location (also in channel).")
    help_lines.append("- news <topic|top>: Get top news headlines.")
    help_lines.append("- shorten <url>: Create a short URL.")
    help_lines.append('- remindme "msg" in <N> <minutes|hours|days>: Set a reminder.')
    help_lines.append("- ct <msg>: Send a message to bot's channel.")
    help_lines.append("- bm <msg>: Send a broadcast message.")
    help_lines.append("- c <q>: Ask Gemini AI via PM.")
    help_lines.append("- /c <q>: Ask Gemini AI in bot's channel.")
    help_lines.append("- afk <reason>: Set your AFK status.")
    help_lines.append("- seen <nick>: Check when a user was last active.")
    help_lines.append("- !poll \"Q\" \"A\" \"B\": Create a poll.")
    help_lines.append("- !vote <id> <num>: Vote in a poll.")
    help_lines.append("- !results <id>: Show poll results.")

    if is_admin:
        help_lines.append("\n--- Admin Commands ---")
        admin_help = {
            # Bot Control
            "lock": "Toggles the bot's command lock.",
            "block <cmd>": "Blocks a command.",
            "unblock <cmd>": "Unblocks a command.",
            "rs": "Restarts the bot.",
            "q": "Shuts down the bot.",
            "health": "Shows a detailed diagnostic report.",
            # Config Management
            "gapi <key>": "Sets the Gemini API key.",
            "instruct <text>": "Sets Gemini's system instruction.",
            "setmodel <name>": "Sets the Gemini model (e.g., gemini-1.5-pro-latest).",
            "listmodels": "Lists available Gemini models.",
            "scp <path>": "Sets the bot's initial channel path.",
            "!filter <add|rm|list> [word]": "Manages the word filter.",
            "set_context_retention <min>": "Sets AI context history retention time.",
            # Feature Toggles
            "jcl": "Toggles Join/Leave announcements.",
            "tg_chanmsg": "Toggles ability to send channel messages.",
            "tg_broadcast": "Toggles ability to send broadcasts.",
            "tg_gemini_pm": "Toggles Gemini for PMs.",
            "tg_gemini_chan": "Toggles Gemini for channel.",
            "!tgmmode": "Toggles Gemini/Template welcome messages.",
            "!tfilter": "Toggles the word filter on/off.",
            "tg_context_history": "Toggles context history for AI.",
            "tg_debug_logging": "Toggles verbose debug logging.",
            # User Management
            "listusers [path]": "Lists users in a channel.",
            "listchannels": "Lists all server channels.",
            "move <nick> <path>": "Moves a user to a channel.",
            "kick <nick>": "Kicks a user from the bot's channel.",
            "ban <nick>": "Bans a user by username.",
            "unban <username>": "Unbans a user by username.",
            # Channel Management
            "jc <path>[|pass]": "Makes the bot join a channel.",
        }
        # Add admin commands with descriptions
        for cmd, desc in sorted(admin_help.items()):
            help_lines.append(f"- {cmd}: {desc}")

    bot._send_pm(msg_from_id, "\n".join(help_lines))

def handle_ping(bot, msg_from_id, **kwargs):
    bot._send_pm(msg_from_id, "Pong!")

def handle_info(bot, msg_from_id, **kwargs):
    uptime_str = format_uptime(time.time() - bot._start_time if bot._start_time > 0 else -1)
    
    gemini_status = f"ENABLED (Model: {bot.gemini_service.model_name})" if bot.gemini_service.is_enabled() else "DISABLED"
    news_status = "ENABLED" if bot.news_service.is_enabled() else "DISABLED (API Key Missing)"
    reminders_status = "ENABLED" if bot.reminder_service.is_enabled() else "DISABLED (Libraries Missing)"
    debug_logging_status = "ENABLED" if bot.config['Bot']['debug_logging_enabled'] else "DISABLED"
    context_history_status = "ENABLED" if bot.config['Bot']['context_history_enabled'] else "DISABLED"
    gemini_api_key_status = "SET" if bot.config['Bot']['gemini_api_key'] else "NOT SET"
    news_api_key_status = "SET" if bot.config['Bot']['news_api_key'] else "NOT SET"


    server_name, server_version = "N/A", "N/A"
    try:
        props = bot.getServerProperties()
        if props:
            server_name = ttstr(props.szServerName)
            server_version = ttstr(props.szServerVersion)
    except Exception: pass

    info_lines = [
        f"--- Bot Info ---",
        f"Name: {ttstr(bot.nickname)}",
        f"Uptime: {uptime_str}",
        f"Channel: {ttstr(bot.target_channel_path) if bot._in_channel else 'None'}",
        f"Locked: {'YES' if bot.bot_locked else 'NO'}",
        f"--- System Info ---",
        f"Operating System: {sys.platform}",
        f"Python Version: {sys.version.split(' ')[0]}",
        
        f"TeamTalk Library: {LOADED_TT_LIB}",
        f"--- Features ---",
        f"Gemini AI: {gemini_status}",
        f"News: {news_status}",
        f"Reminders: {reminders_status}",
        f"Debug Logging: {debug_logging_status}",
        f"Context History: {context_history_status}",
        f"Gemini API Key: {gemini_api_key_status}",
        f"News API Key: {news_api_key_status}",
        f"--- Server Info ---",
        f"Name: {server_name} ({ttstr(bot.host)})",
        f"Version: {server_version}",
    ]
    bot._send_pm(msg_from_id, "\n".join(info_lines))

def handle_whoami(bot, msg_from_id, sender_nick, **kwargs):
    try:
        user = bot.getUser(msg_from_id)
        if not user: raise ValueError("Could not get user info")
        admin_status = "Yes" if bot._is_admin(msg_from_id) else "No"
        bot._send_pm(msg_from_id, f"Nick: {sender_nick}\nID: {user.nUserID}\nUser: {ttstr(user.szUsername)}\nAdmin: {admin_status}")
    except Exception as e:
        bot._send_pm(msg_from_id, f"Error getting your info: {e}")

def handle_rights(bot, msg_from_id, **kwargs):
    rights_map = {v: k for k, v in UserRight.__dict__.items() if k.startswith('USERRIGHT_')}
    output = [f"My Permissions ({bot.my_rights:#010x}):"]
    output.extend(f"- {flag_name.replace('USERRIGHT_', '')}" for flag_val, flag_name in rights_map.items() if bot.my_rights & flag_val)
    bot._send_pm(msg_from_id, "\n".join(output))

def handle_change_nick(bot, msg_from_id, args_str, **kwargs):
    if not args_str: bot._send_pm(msg_from_id, "Usage: cn <new_nickname>"); return
    new_nick = ttstr(args_str)
    if len(new_nick) > TT_STRLEN: bot._send_pm(msg_from_id, "Error: Nickname too long."); return
    bot.doChangeNickname(new_nick)
    bot._send_pm(msg_from_id, f"Nickname change to '{new_nick}' requested.")

def handle_change_status(bot, msg_from_id, args_str, **kwargs):
    new_status = ttstr(args_str)
    if len(new_status) > TT_STRLEN: bot._send_pm(msg_from_id, "Error: Status too long."); return
    bot.doChangeStatus(0, new_status)
    bot._send_pm(msg_from_id, "Status change requested.")

COMMAND_MAP_PM = {
    # User Commands
    "h": handle_help,
    "ping": handle_ping,
    "info": handle_info,
    "whoami": handle_whoami,
    "rights": handle_rights,
    "cn": handle_change_nick,
    "cs": handle_change_status,
    # Communication Commands
    "w": communication_commands.handle_weather,
    # AI Commands
    "c": ai_commands.handle_pm_ai,
    # User Status Commands
    "afk": user_status_commands.handle_afk,
    "seen": user_status_commands.handle_seen,
    # Poll Commands
    "!poll": poll_commands.handle_poll_create,
    "!vote": poll_commands.handle_vote,
    "!results": poll_commands.handle_results,
    # Utility Commands
    "!time": utility_commands.handle_time,
    "news": utility_commands.handle_news,
    "shorten": utility_commands.handle_shorten_url,
    "remindme": utility_commands.handle_remind_me,
}

ADMIN_COMMANDS = {
    # Admin - Bot Control
    "lock": bot_control.handle_lock,
    "block": bot_control.handle_block_command,
    "unblock": bot_control.handle_block_command,
    "rs": bot_control.handle_restart,
    "q": bot_control.handle_quit,
    # Admin - Diagnostic
    "health": diagnostic_commands.handle_health,
    # Admin - Config Management
    "gapi": config_management.handle_set_gapi,
    "instruct": config_management.handle_set_instruction,
    "setmodel": config_management.handle_set_model,
    "listmodels": config_management.handle_list_models,
    "scp": config_management.handle_set_channel_path,
    "!filter": config_management.handle_filter_management,
    "set_context_retention": config_management.handle_set_context_retention,
    # Admin - Feature Toggles
    "jcl": feature_toggles.handle_toggle_jcl,
    "tg_chanmsg": feature_toggles.handle_toggle_chanmsg,
    "tg_broadcast": feature_toggles.handle_toggle_broadcast,
    "tg_gemini_pm": feature_toggles.handle_toggle_gemini_pm,
    "tg_gemini_chan": feature_toggles.handle_toggle_gemini_chan,
    "!tgmmode": feature_toggles.handle_toggle_welcome_mode,
    "!tfilter": feature_toggles.handle_toggle_filter,
    "tg_context_history": feature_toggles.handle_toggle_context_history,
    "tg_debug_logging": feature_toggles.handle_toggle_debug_logging,
    # Admin - User Management
    "listusers": user_management.handle_list_users,
    "listchannels": user_management.handle_list_channels,
    "move": user_management.handle_move_user,
    "kick": user_management.handle_kick_user,
    "ban": user_management.handle_ban_user,
    "unban": user_management.handle_unban_user,
    # Admin - Channel Management
    "jc": channel_management.handle_join_channel,
    "ct": communication_commands.handle_channel_text,
    "bm": communication_commands.handle_broadcast_message,
}

# Combine all commands for easy lookup in command_handler
ALL_COMMANDS = {**COMMAND_MAP_PM, **ADMIN_COMMANDS}