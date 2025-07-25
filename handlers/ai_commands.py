
import logging

def handle_pm_ai(bot, msg_from_id, args_str, **kwargs):
    logging.debug(f"handle_pm_ai called for user_id: {msg_from_id}, prompt: '{args_str}'")
    if not bot.allow_gemini_pm:
        logging.debug(f"Gemini PM disabled for user_id: {msg_from_id}")
        bot._send_pm(msg_from_id, "[Bot] Gemini AI (PM) is disabled."); return
    if not bot.gemini_service.is_enabled():
        logging.debug(f"Gemini service not enabled for user_id: {msg_from_id}")
        bot._send_pm(msg_from_id, "[Bot Error] Gemini AI is not available."); return

    prompt = args_str.strip()
    if not prompt:
        logging.debug(f"Empty prompt from user_id: {msg_from_id}")
        bot._send_pm(msg_from_id, "Usage: c <your question>"); return

    bot._send_pm(msg_from_id, "[Bot] Asking Gemini...")
    history = bot.context_history_manager.get_history(str(msg_from_id))
    logging.debug(f"Retrieved history for user_id {msg_from_id}: {history}")
    reply = bot.gemini_service.generate_content(prompt, history=history)
    logging.debug(f"Gemini reply for user_id {msg_from_id}: {reply}")
    bot._send_pm(msg_from_id, reply)

def handle_channel_ai(bot, msg_from_id, sender_nick, channel_id, args_str, **kwargs):
    if not bot.allow_gemini_channel: return
    if not bot.gemini_service.is_enabled():
        bot._send_channel_message(channel_id, "[Bot Error] Gemini AI is not available."); return

    prompt = args_str.strip()
    if not prompt:
        bot._send_channel_message(channel_id, "Usage: /c <your question>"); return

    bot._send_channel_message(channel_id, f"[Bot] Asking Gemini for {sender_nick}...")
    history = bot.context_history_manager.get_history(str(channel_id))
    logging.debug(f"Retrieved history for channel_id {channel_id}: {history}")
    reply = bot.gemini_service.generate_content(prompt, history=history)
    logging.debug(f"Gemini reply for channel_id {channel_id}: {reply}")
    bot._send_channel_message(channel_id, f"Answering {sender_nick}: {reply}")
