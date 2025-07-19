import logging
from datetime import datetime
from utils import format_uptime

def handle_afk(bot, msg_from_id, sender_nick, args_str, **kwargs):
    """Handles setting a user's AFK status."""
    reason = args_str.strip()
    if not reason:
        bot._send_pm(msg_from_id, "Usage: afk <reason>")
        return
    
    bot.data_service.set_afk(msg_from_id, sender_nick, reason)
    bot._send_pm(msg_from_id, f"You are now marked as AFK. Reason: {reason}")
    logging.info(f"User {sender_nick} (ID: {msg_from_id}) set AFK status.")

def handle_seen(bot, msg_from_id, args_str, **kwargs):
    """Handles checking when a user was last seen."""
    target_nick = args_str.strip()
    if not target_nick:
        bot._send_pm(msg_from_id, "Usage: seen <nickname>")
        return
    
    seen_data = bot.data_service.get_last_seen(target_nick)

    if not seen_data:
        bot._send_pm(msg_from_id, f"I have no record of anyone named '{target_nick}'.")
        return

    try:
        last_seen_time = datetime.fromisoformat(seen_data['timestamp'])
        time_ago = format_uptime(datetime.now().timestamp() - last_seen_time.timestamp())
        
        # Format the timestamp for display
        formatted_timestamp = last_seen_time.strftime('%Y-%m-%d %H:%M:%S')

        reply = (f"I last saw {seen_data['nick']} about {time_ago} ago ({formatted_timestamp}), "
                 f"when they {seen_data['action']}.")
        bot._send_pm(msg_from_id, reply)

    except (ValueError, TypeError) as e:
        logging.error(f"Error parsing timestamp for 'seen' command: {e}")
        bot._send_pm(msg_from_id, f"Could not parse the last seen time for '{target_nick}'.")