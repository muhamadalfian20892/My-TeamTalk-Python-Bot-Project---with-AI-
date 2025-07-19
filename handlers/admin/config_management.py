
import logging
from TeamTalk5 import ttstr

def handle_set_channel_path(bot, msg_from_id, args_str, **kwargs):
    """Sets the bot's initial channel path for subsequent logins."""
    if not args_str:
        current_path = bot.config['Bot'].get('initial_channel_path', 'Not Set')
        bot._send_pm(msg_from_id, f"Usage: scp <channel_path>\nCurrent path: {current_path}")
        return

    new_path = args_str.strip()
    # FIX: Update the live instance variable as well as the config dictionary
    bot.initial_channel_path = ttstr(new_path)
    bot.config['Bot']['initial_channel_path'] = ttstr(new_path)
    bot._save_runtime_config()
    bot._send_pm(msg_from_id, f"Initial channel path set to '{new_path}'. This will take effect on the next login/restart.")


def handle_set_gapi(bot, msg_from_id, args_str, **kwargs):
    if not args_str:
        bot._send_pm(msg_from_id, "Usage: gapi <your_gemini_api_key>"); return

    new_api_key = args_str.strip()
    bot.gemini_service.api_key = new_api_key
    bot.gemini_service.init_model()

    if bot.gemini_service.is_enabled():
        bot.allow_gemini_pm = True
        bot.allow_gemini_channel = True
        feedback = "Gemini API key updated and initialized successfully."
        bot._save_runtime_config(save_gkey=True)
    else:
        feedback = "Gemini API key updated, but failed to initialize model. Check key."
        bot._save_runtime_config(save_gkey=True)
    
    bot._send_pm(msg_from_id, feedback)
    if bot.main_window: bot.main_window.update_feature_list()

def handle_set_instruction(bot, msg_from_id, args_str, **kwargs):
    """Handles setting the system instruction for the Gemini model."""
    if not args_str:
        current_instruction = bot.gemini_service.system_instruction
        bot._send_pm(msg_from_id, f"Usage: instruct <system_instruction>\nCurrent instruction: {current_instruction}")
        return

    new_instruction = args_str.strip()
    bot.gemini_service.system_instruction = new_instruction
    bot.gemini_service.init_model() # Re-initialize the model with the new instruction

    if bot.gemini_service.is_enabled():
        feedback = "Gemini system instruction updated successfully."
        bot._save_runtime_config()
    else:
        feedback = "Gemini system instruction updated, but the model is currently disabled or failed to re-initialize. Check API key."
        bot._save_runtime_config()

    bot._send_pm(msg_from_id, feedback)

def handle_set_model(bot, msg_from_id, args_str, **kwargs):
    """Handles setting the generative model for Gemini."""
    new_model_name = args_str.strip()
    if not new_model_name:
        current_model = bot.gemini_service.model_name
        bot._send_pm(msg_from_id, f"Usage: setmodel <model_name>\nCurrent model: {current_model}")
        return

    bot._send_pm(msg_from_id, f"Attempting to switch to model '{new_model_name}'...")
    if bot.gemini_service.set_model(new_model_name):
        feedback = f"Successfully switched to Gemini model: {new_model_name}"
        bot.config['Bot']['gemini_model_name'] = new_model_name
        bot._save_runtime_config()
    else:
        feedback = f"Failed to switch to model '{new_model_name}'. Check model name and API key. Reverting to previous model."
        # Revert by re-initializing with the old config value
        bot.gemini_service.set_model(bot.config['Bot']['gemini_model_name'])

    bot._send_pm(msg_from_id, feedback)

def handle_list_models(bot, msg_from_id, **kwargs):
    """Lists available Gemini models."""
    bot._send_pm(msg_from_id, "Fetching available Gemini models...")
    models = bot.gemini_service.list_available_models()
    if models:
        # Let's make the list more readable by splitting it into multiple messages if it's too long
        model_list_str = "\n".join(sorted([m.replace("models/", "") for m in models]))
        bot._send_pm(msg_from_id, f"--- Available Gemini Models ---\n{model_list_str}")
    else:
        bot._send_pm(msg_from_id, "Could not retrieve model list. Check API key or network connection.")


def handle_set_context_retention(bot, msg_from_id, args_str, **kwargs):
    try:
        retention_minutes = int(args_str.strip())
        if retention_minutes < 0:
            raise ValueError("Retention minutes cannot be negative.")
        
        bot.context_history_manager.set_retention_minutes(retention_minutes)
        bot.config['Bot']['context_history_retention_minutes'] = retention_minutes
        bot._save_runtime_config()
        bot._send_pm(msg_from_id, f"Context history retention set to {retention_minutes} minutes.")
    except ValueError:
        bot._send_pm(msg_from_id, "Usage: set_context_retention <minutes> (e.g., set_context_retention 60)")
    except Exception as e:
        logging.error(f"Error setting context retention: {e}")
        bot._send_pm(msg_from_id, f"[Error] Failed to set context retention: {e}")

def handle_filter_management(bot, msg_from_id, args_str, **kwargs):
    parts = args_str.split(maxsplit=1)
    sub_command = parts[0].lower() if parts else "list"
    word = parts[1].strip().lower() if len(parts) > 1 else ""

    if sub_command == "add":
        if not word: bot._send_pm(msg_from_id, "Usage: !filter add <word>"); return
        bot.filtered_words.add(word)
        bot.filter_enabled = True
        bot._save_runtime_config()
        bot._send_pm(msg_from_id, f"Word '{word}' added to filter. Filter enabled.")
    elif sub_command == "remove":
        if not word: bot._send_pm(msg_from_id, "Usage: !filter remove <word>"); return
        bot.filtered_words.discard(word)
        if not bot.filtered_words: bot.filter_enabled = False
        bot._save_runtime_config()
        bot._send_pm(msg_from_id, f"Word '{word}' removed from filter.")
    elif sub_command == "list":
        status = "ENABLED" if bot.filter_enabled else "DISABLED"
        word_list = ", ".join(sorted(list(bot.filtered_words))) or "Empty"
        bot._send_pm(msg_from_id, f"Filtered Words ({status}): {word_list}")
    else:
        bot._send_pm(msg_from_id, "Usage: !filter <add|remove|list> [word]")