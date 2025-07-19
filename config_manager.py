
import json
import os
import logging
import collections.abc

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    'Connection': {
        'host': 'localhost',
        'port': '10333',
        'username': 'guest',
        'password': '',
        'nickname': 'PyBot+',
        'channel_password': ''
    },
    'Bot': {
        'client_name': 'New TeamTalk Bot v2.8',
        'initial_channel_path': '/',
        'admin_usernames': '',
        'gemini_api_key': '',
        'gemini_system_instruction': 'You are a helpful assistant.',
        'gemini_model_name': 'gemini-1.5-flash-latest',
        'status_message': '',
        'reconnect_delay_min': 5,
        'reconnect_delay_max': 15,
        'weather_api_key': '',
        'news_api_key': '',
        'filtered_words': '',
        'context_history_retention_minutes': 60,
        'context_history_enabled': True,
        'debug_logging_enabled': False
    },
    'Database': {
        'file': 'bot_data.db'
    }
}

def _deep_update(d, u):
    """Recursively update a dictionary."""
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = _deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

def load_config():
    if not os.path.exists(CONFIG_FILE):
        logging.warning(f"{CONFIG_FILE} not found. Will prompt for setup.")
        return None

    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            loaded_config = json.load(f)
        
        # Create a deep copy of defaults and merge loaded config on top of it
        # This ensures all keys exist, which is great for upgrades
        config = json.loads(json.dumps(DEFAULT_CONFIG)) # Deep copy
        config = _deep_update(config, loaded_config)

        # --- Type and value validation ---
        # Ensure numeric values are integers
        config['Bot']['reconnect_delay_min'] = int(config['Bot']['reconnect_delay_min'])
        config['Bot']['reconnect_delay_max'] = int(config['Bot']['reconnect_delay_max'])
        config['Bot']['context_history_retention_minutes'] = int(config['Bot']['context_history_retention_minutes'])

        # Ensure boolean values are booleans
        config['Bot']['context_history_enabled'] = bool(config['Bot']['context_history_enabled'])
        config['Bot']['debug_logging_enabled'] = bool(config['Bot']['debug_logging_enabled'])

        logging.info(f"Loaded configuration from {CONFIG_FILE}")
        return config
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {CONFIG_FILE}: {e}. Please fix or delete it.")
        return None
    except (TypeError, ValueError) as e:
        logging.error(f"Invalid value in config file {CONFIG_FILE}: {e}. Please fix or delete it.")
        return None
    except Exception as e:
        logging.error(f"Error reading config file {CONFIG_FILE}: {e}. Please fix or delete it.")
        return None


def save_config(structured_config_data):
    # Ensure all default keys are present before saving
    config_to_save = json.loads(json.dumps(DEFAULT_CONFIG)) # Deep copy
    config_to_save = _deep_update(config_to_save, structured_config_data)

    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as configfile:
            json.dump(config_to_save, configfile, indent=4)
        logging.info(f"Configuration saved to {CONFIG_FILE}")
    except IOError as e:
        logging.error(f"Error saving configuration to {CONFIG_FILE}: {e}")