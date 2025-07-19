from TeamTalk5 import TextMsgType

def handle_time(bot, msg_from_id, channel_id, args_str, msg_type, **kwargs):
    """Handles the !time command to get the current time for a location."""
    location = args_str.strip()
    if not location:
        reply = "Usage: !time <city/country> (e.g., !time London or !time New_York)"
    else:
        reply = bot.time_service.get_time_for_location(location)
    
    if msg_type == TextMsgType.MSGTYPE_USER: # PM command
        bot._send_pm(msg_from_id, reply)
    else: # Channel command
        bot._send_channel_message(channel_id, reply)

def handle_news(bot, msg_from_id, args_str, **kwargs):
    """Handles the news command to fetch top headlines."""
    topic = args_str.strip() if args_str.strip() else "top"
    reply = bot.news_service.get_news(topic)
    bot._send_pm(msg_from_id, reply)

def handle_shorten_url(bot, msg_from_id, args_str, **kwargs):
    """Handles the shorten command to shorten a URL."""
    url = args_str.strip()
    if not url:
        reply = "Usage: shorten <long_url>"
    else:
        reply = bot.url_shortener_service.shorten_url(url)
    bot._send_pm(msg_from_id, reply)

def handle_remind_me(bot, msg_from_id, args_str, **kwargs):
    """Handles the remindme command to set a reminder."""
    reminder_text = args_str.strip()
    reply = bot.reminder_service.parse_and_add_reminder(msg_from_id, reminder_text)
    bot._send_pm(msg_from_id, reply)