import logging
import threading
import time
from utils import format_uptime
from TeamTalk5 import ttstr

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

def handle_health(bot, msg_from_id, **kwargs):
    """Provides a detailed diagnostic report of the bot's health."""
    
    health_report = ["--- Bot Health & Diagnostics Report ---"]

    # --- Uptime & System ---
    uptime_str = format_uptime(time.time() - bot._start_time if bot._start_time > 0 else -1)
    health_report.append(f"\n[System]")
    health_report.append(f"Uptime: {uptime_str}")
    
    if PSUTIL_AVAILABLE:
        process = psutil.Process()
        mem_info = process.memory_info()
        memory_usage = f"{mem_info.rss / 1024 / 1024:.2f} MB (RSS)"
    else:
        memory_usage = "N/A (psutil not installed)"
    health_report.append(f"Memory Usage: {memory_usage}")

    # --- Threading Details ---
    active_threads = threading.enumerate()
    health_report.append(f"Threads Active: {len(active_threads)}")
    for thread in sorted(active_threads, key=lambda t: t.name):
        status = "Daemon" if thread.daemon else "Normal"
        health_report.append(f"  - {thread.name} ({status})")

    # --- Connection & Session ---
    health_report.append(f"\n[Connection & Session]")
    health_report.append(f"Server: {ttstr(bot.host)}:{bot.tcp_port}")
    health_report.append(f"Logged In: {'Yes' if bot._logged_in else 'No'}")
    health_report.append(f"My User ID: {bot._my_user_id if bot._logged_in else 'N/A'}")
    
    if bot._in_channel_ids:
        health_report.append(f"Current Channels ({len(bot._in_channel_ids)}):")
        for chan_id in bot._in_channel_ids:
            try:
                path = ttstr(bot.getChannelPath(chan_id))
                health_report.append(f"  - '{path}' (ID: {chan_id})")
            except Exception:
                health_report.append(f"  - (Error getting path for ID: {chan_id})")
    else:
        health_report.append("Current Channels: None")
    health_report.append(f"Target/Initial Channel: '{ttstr(bot.initial_channel_path)}'")


    # --- Bot State ---
    health_report.append(f"\n[Bot State]")
    health_report.append(f"Locked: {'Yes' if bot.bot_locked else 'No'}")
    
    # Admins
    admin_nicks = []
    for admin_id in bot.admin_user_ids:
        if admin_id in bot._user_cache:
            admin_nicks.append(ttstr(bot._user_cache[admin_id].szNickname))
        else:
            admin_nicks.append(f"UserID_{admin_id} (Not in cache)")
    admin_list_str = ', '.join(sorted(admin_nicks)) or "None"
    health_report.append(f"Recognized Admins: {admin_list_str}")

    # Blocked Commands
    blocked_cmds_str = ', '.join(sorted(list(bot.blocked_commands))) or "None"
    health_report.append(f"Blocked Commands: {blocked_cmds_str}")
    health_report.append(f"User Cache Size: {len(bot._user_cache)} users")


    # --- Services & APIs ---
    health_report.append(f"\n[Services & APIs]")
    
    # API Keys
    health_report.append("API Key Status:")
    health_report.append(f"  - Gemini: {'SET' if bot.config['Bot']['gemini_api_key'] else 'NOT SET'}")
    health_report.append(f"  - Weather: {'SET' if bot.config['Bot']['weather_api_key'] else 'NOT SET'}")
    health_report.append(f"  - News: {'SET' if bot.config['Bot']['news_api_key'] else 'NOT SET'}")
    
    # Service Status & Latency
    health_report.append("Service Status & Latency (Last Call):")
    
    gemini_status = f"ENABLED (Model: {bot.gemini_service.model_name})" if bot.gemini_service.is_enabled() else "DISABLED"
    gemini_latency = f"{bot.gemini_service.last_latency:.4f}s"
    health_report.append(f"  - Gemini AI: {gemini_status}, Latency: {gemini_latency}")

    weather_status = "ENABLED" if bot.weather_service.is_enabled() else "DISABLED"
    weather_latency = f"{bot.weather_service.last_latency:.4f}s"
    health_report.append(f"  - Weather: {weather_status}, Latency: {weather_latency}")

    news_status = "ENABLED" if bot.news_service.is_enabled() else "DISABLED"
    health_report.append(f"  - News: {news_status}")

    reminders_status = "ENABLED" if bot.reminder_service.is_enabled() else "DISABLED"
    health_report.append(f"  - Reminders: {reminders_status}")

    url_shortener_status = "ENABLED" if bot.url_shortener_service.is_enabled() else "DISABLED"
    health_report.append(f"  - URL Shortener: {url_shortener_status}")

    time_status = "ENABLED" if bot.time_service.is_enabled() else "DISABLED"
    health_report.append(f"  - Time: {time_status}")

    # Database
    db_status = "Connected" if bot.data_service.is_db_connected() else "Disconnected"
    health_report.append(f"  - Database ({bot.data_service.db_file}): {db_status}")

    bot._send_pm(msg_from_id, "\n".join(health_report))