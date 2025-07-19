import sys
import time
import signal
import json # For parsing weather JSON (if used, but OpenWeatherMap doesn't need it directly here)
import logging
import math # Added for uptime calculation
import os
import webbrowser
import wx
import threading # Added for GUI threading
import configparser # Added for configuration
import random # For the random delay, welcome messages
import re

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    print("Warning: requests library not found.")
    print("Please install it using: pip install requests")
    print("Weather features will be disabled.")
    REQUESTS_AVAILABLE = False

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    print("Warning: google-generativeai library not found.")
    print("Please install it using: pip install google-generativeai")
    print("Gemini features will be disabled.")
    GEMINI_AVAILABLE = False

try:
    from TeamTalk5 import (
        TeamTalk, TeamTalkError, ClientEvent, TextMsgType, User, Channel,
        ClientErrorMsg, ServerProperties, RemoteFile, UserAccount, BannedUser, BanType,
        ServerStatistics, MediaFileInfo, SoundDevice, TextMessage, UserRight,
        Subscription, StreamType, AudioBlock,
        ttstr, buildTextMessage, TT_LOCAL_USERID,
        ClientError, ClientFlags, TT_STRLEN # Import TT_STRLEN
    )
    GEMINI_SAFETY_SETTINGS = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    ]
except ImportError:
    print("FATAL ERROR: Could not import TeamTalk5 wrapper.")
    print("Ensure TeamTalk5.py is in the same directory or Python path.")
    sys.exit(1)


# --- Constants ---
CONFIG_FILE = "config.ini"
DEFAULT_CONFIG = {
    'Connection': {
        'host': 'localhost',
        'port': '10333',
        'username': 'guest',
        'password': '',
        'nickname': 'PyBot+',
        'channel': '/',
        'channel_password': ''
    },
    'Bot': {
        'client_name': 'New TeamTalk Bot v2.6', # Version bump!
        'admin_usernames': '',
        'gemini_api_key': '',
        'status_message': '', # Added default for status message
        'reconnect_delay_min': '5', # Seconds
        'reconnect_delay_max': '15', # Seconds
        'weather_api_key': '', # For OpenWeatherMap or similar
        'filtered_words': ''   # Comma-separated list
    }
}

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Configuration Functions ---
def load_config():
    """Loads configuration from CONFIG_FILE."""
    config = configparser.ConfigParser()
    if not os.path.exists(CONFIG_FILE):
        logging.warning(f"{CONFIG_FILE} not found. Will prompt for setup.")
        return None # Indicate no config loaded

    try:
        config.read(CONFIG_FILE)
        # Basic validation (check if sections exist)
        if not config.has_section('Connection') or not config.has_section('Bot'):
             logging.error(f"Config file {CONFIG_FILE} is missing required sections ('Connection', 'Bot'). Please delete it or fix it.")
             return None # Treat as invalid
        logging.info(f"Loaded configuration from {CONFIG_FILE}")
        return config
    except configparser.Error as e:
        logging.error(f"Error reading config file {CONFIG_FILE}: {e}. Please delete it or fix it.")
        return None # Treat as invalid

def save_config(structured_config_data):
    """
    Saves structured configuration data (dict of dicts) to CONFIG_FILE.
    """
    config = configparser.ConfigParser()

    # Ensure sections exist even if empty
    conn_data = structured_config_data.get('Connection', {})
    bot_data = structured_config_data.get('Bot', {})

    # Populate Connection section
    config['Connection'] = {
        'host': conn_data.get('host', DEFAULT_CONFIG['Connection']['host']),
        'port': str(conn_data.get('port', DEFAULT_CONFIG['Connection']['port'])), # Ensure port is string
        'username': conn_data.get('username', DEFAULT_CONFIG['Connection']['username']),
        'password': conn_data.get('password', ''), # Save password
        'nickname': conn_data.get('nickname', DEFAULT_CONFIG['Connection']['nickname']),
        'channel': conn_data.get('channel', DEFAULT_CONFIG['Connection']['channel']),
        'channel_password': conn_data.get('channel_password', '')
    }

    # Populate Bot section
    config['Bot'] = {
        'client_name': bot_data.get('client_name', DEFAULT_CONFIG['Bot']['client_name']),
        'admin_usernames': bot_data.get('admin_usernames', ''),
        'gemini_api_key': bot_data.get('gemini_api_key', ''), # Save API key
        'status_message': bot_data.get('status_message', ''), # Save status message
        'reconnect_delay_min': str(bot_data.get('reconnect_delay_min', DEFAULT_CONFIG['Bot']['reconnect_delay_min'])),
        'reconnect_delay_max': str(bot_data.get('reconnect_delay_max', DEFAULT_CONFIG['Bot']['reconnect_delay_max'])),
        'weather_api_key': bot_data.get('weather_api_key', ''),
        'filtered_words': bot_data.get('filtered_words', '')
        # Note: welcome_message_mode is not saved to config by default
    }

    try:
        with open(CONFIG_FILE, 'w') as configfile:
            config.write(configfile)
        logging.info(f"Configuration saved to {CONFIG_FILE}")
    except IOError as e:
        logging.error(f"Error saving configuration to {CONFIG_FILE}: {e}")
    except Exception as e:
        logging.error(f"Unexpected error saving configuration: {e}", exc_info=True)

# --- Initial Setup Dialog ---
class ConfigDialog(wx.Dialog):
    def __init__(self, parent, title, defaults):
        super(ConfigDialog, self).__init__(parent, title=title, size=(550, 460)) # Slightly taller for weather key

        self.config_data = defaults.copy() # Store defaults to return if needed

        panel = wx.Panel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        grid = wx.GridBagSizer(5, 5) # Use GridBagSizer for better alignment

        row = 0
        # Server Host
        lbl_host = wx.StaticText(panel, label="Server Host:")
        grid.Add(lbl_host, pos=(row, 0), flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=10)
        self.tcHost = wx.TextCtrl(panel, value=defaults.get('host', ''))
        grid.Add(self.tcHost, pos=(row, 1), span=(1, 3), flag=wx.EXPAND | wx.RIGHT, border=10)
        row += 1

        # Server Port
        lbl_port = wx.StaticText(panel, label="Server Port:")
        grid.Add(lbl_port, pos=(row, 0), flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=10)
        self.tcPort = wx.TextCtrl(panel, value=str(defaults.get('port', '10333'))) # Port as string
        grid.Add(self.tcPort, pos=(row, 1), span=(1, 1), flag=wx.EXPAND) # Smaller span
        row += 1

        # Username
        lbl_user = wx.StaticText(panel, label="Bot Username:")
        grid.Add(lbl_user, pos=(row, 0), flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=10)
        self.tcUser = wx.TextCtrl(panel, value=defaults.get('username', ''))
        grid.Add(self.tcUser, pos=(row, 1), span=(1, 3), flag=wx.EXPAND | wx.RIGHT, border=10)
        row += 1

        # Password
        lbl_pass = wx.StaticText(panel, label="Bot Password:")
        grid.Add(lbl_pass, pos=(row, 0), flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=10)
        self.tcPass = wx.TextCtrl(panel, style=wx.TE_PASSWORD, value=defaults.get('password', ''))
        grid.Add(self.tcPass, pos=(row, 1), span=(1, 3), flag=wx.EXPAND | wx.RIGHT, border=10)
        row += 1

        # Nickname
        lbl_nick = wx.StaticText(panel, label="Bot Nickname:")
        grid.Add(lbl_nick, pos=(row, 0), flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=10)
        self.tcNick = wx.TextCtrl(panel, value=defaults.get('nickname', ''))
        grid.Add(self.tcNick, pos=(row, 1), span=(1, 3), flag=wx.EXPAND | wx.RIGHT, border=10)
        row += 1

        # Initial Status Message (Optional)
        lbl_status = wx.StaticText(panel, label="Initial Status Msg:")
        grid.Add(lbl_status, pos=(row, 0), flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=10)
        self.tcStatus = wx.TextCtrl(panel, value=defaults.get('status_message', ''))
        grid.Add(self.tcStatus, pos=(row, 1), span=(1, 3), flag=wx.EXPAND | wx.RIGHT, border=10)
        row += 1

        # Admin Usernames
        lbl_admin = wx.StaticText(panel, label="Admin Usernames (comma-separated):")
        grid.Add(lbl_admin, pos=(row, 0), flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=10)
        self.tcAdmin = wx.TextCtrl(panel, value=defaults.get('admin_usernames', ''))
        grid.Add(self.tcAdmin, pos=(row, 1), span=(1, 3), flag=wx.EXPAND | wx.RIGHT, border=10)
        row += 1

        # Gemini API Key
        lbl_api = wx.StaticText(panel, label="Gemini API Key:")
        grid.Add(lbl_api, pos=(row, 0), flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=10)
        self.tcApiKey = wx.TextCtrl(panel, style=wx.TE_PASSWORD, value=defaults.get('gemini_api_key', ''))
        grid.Add(self.tcApiKey, pos=(row, 1), span=(1, 3), flag=wx.EXPAND | wx.RIGHT, border=10)
        row += 1

        # Weather API Key
        lbl_weather_api = wx.StaticText(panel, label="Weather API Key (OpenWeatherMap):")
        grid.Add(lbl_weather_api, pos=(row, 0), flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=10)
        self.tcWeatherApiKey = wx.TextCtrl(panel, style=wx.TE_PASSWORD, value=defaults.get('weather_api_key', ''))
        grid.Add(self.tcWeatherApiKey, pos=(row, 1), span=(1, 3), flag=wx.EXPAND | wx.RIGHT, border=10)
        row += 1


        # Reconnect Delay
        lbl_delay = wx.StaticText(panel, label="Reconnect Delay (min/max sec):")
        grid.Add(lbl_delay, pos=(row, 0), flag=wx.LEFT | wx.ALIGN_CENTER_VERTICAL, border=10)
        delay_hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.tcDelayMin = wx.TextCtrl(panel, value=str(defaults.get('reconnect_delay_min', '5')), size=(50,-1))
        delay_hbox.Add(self.tcDelayMin, 0, wx.RIGHT, 5)
        delay_hbox.Add(wx.StaticText(panel, label="/"), 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        self.tcDelayMax = wx.TextCtrl(panel, value=str(defaults.get('reconnect_delay_max', '15')), size=(50,-1))
        delay_hbox.Add(self.tcDelayMax, 0)
        grid.Add(delay_hbox, pos=(row, 1), flag=wx.LEFT, border=0) # Align left
        row += 1


        # Make column 1 expandable
        grid.AddGrowableCol(1)

        vbox.Add(grid, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)
        vbox.Add((-1, 15)) # Spacer

        # Buttons
        hbox3 = wx.BoxSizer(wx.HORIZONTAL)
        self.btnGetKey = wx.Button(panel, label="Get Gemini API Key")
        self.btnSave = wx.Button(panel, label="Save and Connect", id=wx.ID_OK) # Map Save to OK
        self.btnCancel = wx.Button(panel, label="Cancel", id=wx.ID_CANCEL)
        self.btnSave.SetDefault()

        hbox3.Add(self.btnGetKey)
        hbox3.AddStretchSpacer()
        hbox3.Add(self.btnCancel, flag=wx.RIGHT, border=5)
        hbox3.Add(self.btnSave)
        vbox.Add(hbox3, flag=wx.ALIGN_RIGHT | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        panel.SetSizer(vbox)

        # Bind Events
        self.btnGetKey.Bind(wx.EVT_BUTTON, self.OnGetApiKey)
        self.btnSave.Bind(wx.EVT_BUTTON, self.OnSave)
        # Cancel button already bound by ID_CANCEL
        self.Bind(wx.EVT_CLOSE, self.OnCloseDialog)

        self.CenterOnParent()

    def OnGetApiKey(self, event):
        """Opens the browser to the Gemini API key page."""
        try:
            webbrowser.open("https://aistudio.google.com/app/apikey")
        except Exception as e:
            wx.MessageBox(f"Could not open web browser: {e}", "Error", wx.OK | wx.ICON_ERROR)

    def OnSave(self, event):
        """Validates input, stores it, and closes the dialog with OK status."""
        host = self.tcHost.GetValue().strip()
        port_str = self.tcPort.GetValue().strip()
        user = self.tcUser.GetValue().strip()
        # Password can be empty for guest
        nick = self.tcNick.GetValue().strip()
        status_msg = self.tcStatus.GetValue() # Allow empty, don't strip leading/trailing spaces? User choice.
        admins = self.tcAdmin.GetValue().strip()
        key = self.tcApiKey.GetValue().strip() # API key can be empty
        weather_key = self.tcWeatherApiKey.GetValue().strip() # Weather API key can be empty
        delay_min_str = self.tcDelayMin.GetValue().strip()
        delay_max_str = self.tcDelayMax.GetValue().strip()


        if not host:
            wx.MessageBox("Server Host cannot be empty.", "Input Error", wx.OK | wx.ICON_WARNING)
            self.tcHost.SetFocus()
            return
        try:
            port = int(port_str)
            if not (0 < port < 65536): raise ValueError("Port out of range")
        except ValueError:
            wx.MessageBox("Server Port must be a valid number (1-65535).", "Input Error", wx.OK | wx.ICON_WARNING)
            self.tcPort.SetFocus()
            return
        if not user:
            wx.MessageBox("Bot Username cannot be empty.", "Input Error", wx.OK | wx.ICON_WARNING)
            self.tcUser.SetFocus()
            return
        if not nick:
             wx.MessageBox("Bot Nickname cannot be empty.", "Input Error", wx.OK | wx.ICON_WARNING)
             self.tcNick.SetFocus()
             return

        try:
            delay_min = int(delay_min_str)
            delay_max = int(delay_max_str)
            if delay_min < 0 or delay_max < 0: raise ValueError("Delay cannot be negative")
            if delay_min > delay_max: raise ValueError("Min delay cannot be greater than max delay")
        except ValueError as e:
            wx.MessageBox(f"Invalid Reconnect Delay: {e}. Must be non-negative numbers (min <= max).", "Input Error", wx.OK | wx.ICON_WARNING)
            self.tcDelayMin.SetFocus()
            return


        self.config_data['host'] = host
        self.config_data['port'] = port # Store as int here
        self.config_data['username'] = user
        self.config_data['password'] = self.tcPass.GetValue() # Get password directly
        self.config_data['nickname'] = nick
        self.config_data['status_message'] = status_msg # Store status
        self.config_data['admin_usernames'] = admins
        self.config_data['gemini_api_key'] = key
        self.config_data['weather_api_key'] = weather_key # Store weather key
        self.config_data['reconnect_delay_min'] = delay_min
        self.config_data['reconnect_delay_max'] = delay_max
        # Keep channel/channel_password/client_name/filtered_words from defaults if not edited

        self.EndModal(wx.ID_OK) # Signal success

    def OnCloseDialog(self, event):
        """Handles closing the dialog via the 'X' button."""
        self.EndModal(wx.ID_CANCEL) # Signal cancellation

    def GetConfigData(self):
        """
        Returns the dictionary with collected/default data.
        This dictionary is structured for direct use in save_config.
        """
        # Structure it like the final config dict
        structured_data = {
             'Connection': {
                 'host': self.config_data.get('host'),
                 'port': self.config_data.get('port'),
                 'username': self.config_data.get('username'),
                 'password': self.config_data.get('password'),
                 'nickname': self.config_data.get('nickname'),
                 'channel': self.config_data.get('channel', '/'),
                 'channel_password': self.config_data.get('channel_password', '')
             },
             'Bot': {
                  'client_name': self.config_data.get('client_name', DEFAULT_CONFIG['Bot']['client_name']),
                  'admin_usernames': self.config_data.get('admin_usernames'),
                  'gemini_api_key': self.config_data.get('gemini_api_key'),
                  'status_message': self.config_data.get('status_message'), # Include status
                  'reconnect_delay_min': self.config_data.get('reconnect_delay_min', DEFAULT_CONFIG['Bot']['reconnect_delay_min']),
                  'reconnect_delay_max': self.config_data.get('reconnect_delay_max', DEFAULT_CONFIG['Bot']['reconnect_delay_max']),
                  'weather_api_key': self.config_data.get('weather_api_key', DEFAULT_CONFIG['Bot']['weather_api_key']), # Use get()
                  'filtered_words': self.config_data.get('filtered_words', DEFAULT_CONFIG['Bot']['filtered_words'])   # Use get()
             }
        }
        return structured_data

class MainBotWindow(wx.Frame):
    def __init__(self, parent, title, bot_instance_ref):
        super(MainBotWindow, self).__init__(parent, title=title, size=(850, 550)) # Wider window

        self.bot_instance_ref = bot_instance_ref
        self.feature_map = {} # To map list index to feature key

        panel = wx.Panel(self)
        main_hbox = wx.BoxSizer(wx.HORIZONTAL) # Horizontal layout for log and features

        # --- Left Side: Log Display ---
        log_vbox = wx.BoxSizer(wx.VERTICAL)
        log_label = wx.StaticText(panel, label="Bot Log:")
        log_vbox.Add(log_label, 0, wx.LEFT | wx.TOP, 5)
        self.logDisplay = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        log_vbox.Add(self.logDisplay, 1, wx.EXPAND | wx.ALL, 5)
        main_hbox.Add(log_vbox, 1, wx.EXPAND) # Log area takes half the space

        # --- Right Side: Features & Controls ---
        features_vbox = wx.BoxSizer(wx.VERTICAL)

        # Feature List
        feature_label = wx.StaticText(panel, label="Bot Features (Double-click to toggle):")
        features_vbox.Add(feature_label, 0, wx.LEFT | wx.TOP, 5)
        self.feature_list = wx.ListCtrl(panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES)
        self.feature_list.InsertColumn(0, "Feature", width=200)
        self.feature_list.InsertColumn(1, "Status", width=100)
        features_vbox.Add(self.feature_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        # Input Controls
        controls_hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.channel_msg_input = wx.TextCtrl(panel, size=(200, -1), style=wx.TE_PROCESS_ENTER)
        self.send_channel_msg_btn = wx.Button(panel, label="Send Channel Msg")
        controls_hbox.Add(self.channel_msg_input, 1, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        controls_hbox.Add(self.send_channel_msg_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        features_vbox.Add(controls_hbox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        controls_hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        self.broadcast_input = wx.TextCtrl(panel, size=(200, -1), style=wx.TE_PROCESS_ENTER)
        self.send_broadcast_btn = wx.Button(panel, label="Send Broadcast")
        controls_hbox2.Add(self.broadcast_input, 1, wx.RIGHT | wx.ALIGN_CENTER_VERTICAL, 5)
        controls_hbox2.Add(self.send_broadcast_btn, 0, wx.ALIGN_CENTER_VERTICAL)
        features_vbox.Add(controls_hbox2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)


        main_hbox.Add(features_vbox, 1, wx.EXPAND) # Features area takes other half

        # --- Bottom: Disconnect Button ---
        bottom_vbox = wx.BoxSizer(wx.VERTICAL)
        bottom_vbox.Add(main_hbox, 1, wx.EXPAND | wx.ALL, 5) # Add the main horizontal box

        self.btnDisconnect = wx.Button(panel, label="Disconnect and Exit")
        bottom_vbox.Add(self.btnDisconnect, 0, wx.ALIGN_CENTER | wx.BOTTOM | wx.TOP, 10)

        panel.SetSizer(bottom_vbox)

        # Bind Events
        self.btnDisconnect.Bind(wx.EVT_BUTTON, self.OnDisconnect)
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        self.feature_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnFeatureToggle)
        self.send_channel_msg_btn.Bind(wx.EVT_BUTTON, self.OnSendChannelMessage)
        self.channel_msg_input.Bind(wx.EVT_TEXT_ENTER, self.OnSendChannelMessage) # Allow Enter key
        self.send_broadcast_btn.Bind(wx.EVT_BUTTON, self.OnSendBroadcast)
        self.broadcast_input.Bind(wx.EVT_TEXT_ENTER, self.OnSendBroadcast) # Allow Enter key


        self.Center()
        # self.Show() # Show is called later after successful login

    def log_message(self, message):
        """Appends a message to the log display (thread-safe)."""
        # Check if logDisplay still exists (window might be closing)
        if self.logDisplay:
            wx.CallAfter(self.logDisplay.AppendText, message + "\n")

    def update_feature_list(self):
        """Updates the feature list based on current bot state (thread-safe)."""
        wx.CallAfter(self._update_feature_list_internal)

    def _update_feature_list_internal(self):
        """Internal method to update the list control (runs on GUI thread)."""
        # Check if the list control still exists
        if not self.feature_list:
            return

        current_bot = self.bot_instance_ref[0]
        if not current_bot:
            # Clear list if bot is not running/available
            self.feature_list.DeleteAllItems()
            self.feature_map.clear()
            # Maybe disable input fields too
            if self.channel_msg_input: self.channel_msg_input.Enable(False)
            if self.send_channel_msg_btn: self.send_channel_msg_btn.Enable(False)
            if self.broadcast_input: self.broadcast_input.Enable(False)
            if self.send_broadcast_btn: self.send_broadcast_btn.Enable(False)
            return

        # Enable controls now that bot is potentially running
        if self.channel_msg_input: self.channel_msg_input.Enable(True)
        if self.send_channel_msg_btn: self.send_channel_msg_btn.Enable(True)
        if self.broadcast_input: self.broadcast_input.Enable(True)
        if self.send_broadcast_btn: self.send_broadcast_btn.Enable(True)


        # Define features to display
        features = {
            "ch_msg": "Channel Messages",
            "broadcast": "Broadcast Messages",
            "welcome": "Join/Leave Announce",
            "gemini_pm": "Gemini AI (PM)",
            "gemini_chan": "Gemini AI (Channel /c)",
            "filter": "Word Filter", # Added Filter Status
            "locked": "Bot Locked (Reduced Func)"
            # Note: Welcome Message Mode is not shown in this list (command only toggle)
        }

        # Get current state from bot
        states = {
            "ch_msg": getattr(current_bot, 'allow_channel_messages', False),
            "broadcast": getattr(current_bot, 'allow_broadcast', False),
            "welcome": getattr(current_bot, 'announce_join_leave', False),
            "gemini_pm": getattr(current_bot, 'allow_gemini_pm', False),
            "gemini_chan": getattr(current_bot, 'allow_gemini_channel', False),
            "filter": getattr(current_bot, 'filter_enabled', False), # Get Filter State
            "locked": getattr(current_bot, 'bot_locked', False)
        }

        self.feature_list.DeleteAllItems()
        self.feature_map.clear() # Reset map

        idx = 0
        for key, name in features.items():
            status_str = "ON" if states.get(key, False) else "OFF"
            self.feature_list.InsertItem(idx, name)
            self.feature_list.SetItem(idx, 1, status_str)
            self.feature_map[idx] = key # Map list index back to feature key
            idx += 1

    def OnFeatureToggle(self, event):
        """Handles double-clicking a feature in the list."""
        idx = event.GetIndex()
        feature_key = self.feature_map.get(idx)
        current_bot = self.bot_instance_ref[0]

        if not current_bot or not feature_key:
            self.log_message("[GUI Error] Cannot toggle feature - bot instance or feature key missing.")
            return

        self.log_message(f"[GUI Action] Toggling feature: {feature_key}")

        # Call a toggle method on the bot instance
        # These methods exist in the bot class now
        toggle_method_name = f"toggle_{feature_key}"
        if feature_key == "locked": # Specific name for lock toggle
            toggle_method_name = "toggle_bot_lock"
        elif feature_key == "filter": # Specific name for filter toggle
             toggle_method_name = "toggle_filter"
        elif feature_key == "welcome": # GUI toggle for welcome (maps to jcl)
             toggle_method_name = "toggle_announce_join_leave"
        elif feature_key == "ch_msg":
             toggle_method_name = "toggle_allow_channel_messages"
        elif feature_key == "broadcast":
             toggle_method_name = "toggle_allow_broadcast"
        elif feature_key == "gemini_pm":
             toggle_method_name = "toggle_allow_gemini_pm"
        elif feature_key == "gemini_chan":
             toggle_method_name = "toggle_allow_gemini_channel"


        toggle_method = getattr(current_bot, toggle_method_name, None)

        if toggle_method and callable(toggle_method):
            toggle_method()
            # This ensures the list reflects the new state confirmed by the bot logic
            self.update_feature_list()
        else:
             self.log_message(f"[GUI Error] Unknown or non-callable feature toggle method '{toggle_method_name}' for key '{feature_key}'.")
             return


    def OnSendChannelMessage(self, event):
        """Sends the text from the channel message input box."""
        current_bot = self.bot_instance_ref[0]
        message = self.channel_msg_input.GetValue().strip()
        if not current_bot:
            self.log_message("[GUI Error] Cannot send channel message - bot not running.")
            return
        if not message:
             return

        # Check bot state if needed (e.g., if locked or feature disabled)
        if not getattr(current_bot, 'allow_channel_messages', False):
            self.log_message("[GUI Error] Cannot send: Channel messages are disabled in bot.")
            return
        if getattr(current_bot, 'bot_locked', False):
             self.log_message("[GUI Error] Cannot send: Bot is locked.")
             return


        if not current_bot._in_channel or current_bot._target_channel_id <= 0:
             self.log_message("[GUI Error] Cannot send: Bot is not in a channel.")
             return

        self.log_message(f"[GUI Send Chan] {message}")
        # Prefixing with [GUI] to differentiate from user commands
        success = current_bot._send_channel_message(current_bot._target_channel_id, f"{message}")
        if success:
            if self.channel_msg_input: self.channel_msg_input.SetValue("") # Clear input on success
        else:
             self.log_message("[GUI Error] Failed to send channel message (check bot log).")


    def OnSendBroadcast(self, event):
        """Sends the text from the broadcast input box."""
        current_bot = self.bot_instance_ref[0]
        message = self.broadcast_input.GetValue().strip()
        if not current_bot:
            self.log_message("[GUI Error] Cannot send broadcast - bot not running.")
            return
        if not message:
             return

        # Check bot state
        if not getattr(current_bot, 'allow_broadcast', False):
            self.log_message("[GUI Error] Cannot send: Broadcasts are disabled in bot.")
            return
        if getattr(current_bot, 'bot_locked', False):
            self.log_message("[GUI Error] Cannot send: Bot is locked.")
            return

        self.log_message(f"[GUI Send Broadcast] {message}")
        success = current_bot._send_broadcast(f"{message}")
        if success:
            if self.broadcast_input: self.broadcast_input.SetValue("") # Clear input on success
        else:
             self.log_message("[GUI Error] Failed to send broadcast (check permissions/bot log).")


    def OnDisconnect(self, event):
        """Handles the Disconnect button click."""
        self.log_message("Disconnect button clicked. Stopping bot...")
        current_bot = self.bot_instance_ref[0] # Get current bot from the mutable list/ref
        if current_bot and hasattr(current_bot, 'stop') and callable(current_bot.stop):
            current_bot._mark_stopped_intentionally() # Add a flag to prevent auto-reconnect race
            current_bot.stop()
        self.Close() # Close the GUI window

    def OnCloseWindow(self, event):
        """Handles closing the window (e.g., via 'X')."""
        self.log_message("Main window closing. Stopping bot...")
        current_bot = self.bot_instance_ref[0] # Get current bot from the mutable list/ref
        if current_bot and hasattr(current_bot, 'stop') and callable(current_bot.stop):
            current_bot._mark_stopped_intentionally() # Mark stop as intentional
            current_bot.stop()
        self.Destroy()


# --- TeamTalk Bot Class (Single Corrected Definition) ---
class MyTeamTalkBot(TeamTalk):
    """
    TeamTalk bot with config, GUI logging, admin commands, and Gemini integration.
    Includes saving nickname/status, restart command, auto-reconnect, PM Gemini, Welcome Msg, etc.
    ** NEW: Feature toggles, GUI interaction, command blocking, weather, polls, filter (Regex + Toggle), Gemini Welcome **
    """
    def __init__(self, config_dict): # Takes structured config dictionary
        super().__init__()
        self.config = config_dict # Store the structured config
        conn_conf = self.config.get('Connection', {})
        bot_conf = self.config.get('Bot', {})

        self.host = ttstr(conn_conf.get('host', ''))
        self.tcp_port = int(conn_conf.get('port', 10333)) # Ensure integer
        self.udp_port = self.tcp_port # Use same port for UDP unless specified differently
        self.nickname = ttstr(conn_conf.get('nickname', ''))
        self.status_message = ttstr(bot_conf.get('status_message', '')) # Load initial status
        self.username = ttstr(conn_conf.get('username', ''))
        self.password = ttstr(conn_conf.get('password', ''))
        self.target_channel_path = ttstr(conn_conf.get('channel', '/'))
        self.channel_password = ttstr(conn_conf.get('channel_password', ''))
        self.client_name = ttstr(bot_conf.get('client_name', ''))

        # --- Load New Feature Config ---
        self.weather_api_key = bot_conf.get('weather_api_key', '')
        # Filter setup
        filter_str = bot_conf.get('filtered_words', '')
        self.filtered_words = {word.strip().lower() for word in filter_str.split(',') if word.strip()}
        self.filter_enabled = bool(self.filtered_words) # Enable filter only if words are defined

        self._weather_enabled = REQUESTS_AVAILABLE and bool(self.weather_api_key)
        if REQUESTS_AVAILABLE and not self.weather_api_key:
            logging.warning("Weather API key missing in config. Weather feature disabled.")

        admin_str = bot_conf.get('admin_usernames', '')
        self.admin_usernames_config = [name.strip().lower() for name in admin_str.split(',') if name.strip()]
        self.gemini_api_key = bot_conf.get('gemini_api_key', '') # Store key locally

        # Reconnect delays
        try: self.reconnect_delay_min = int(bot_conf.get('reconnect_delay_min', 5))
        except ValueError: self.reconnect_delay_min = 5
        try: self.reconnect_delay_max = int(bot_conf.get('reconnect_delay_max', 15))
        except ValueError: self.reconnect_delay_max = 15
        if self.reconnect_delay_min < 0: self.reconnect_delay_min = 0
        if self.reconnect_delay_max < self.reconnect_delay_min: self.reconnect_delay_max = self.reconnect_delay_min

        # --- Core Bot State ---
        self._logged_in = False
        self._in_channel = False
        self._my_user_id = -1
        self._target_channel_id = -1
        self.my_rights = UserRight.USERRIGHT_NONE
        self.admin_user_ids = set()
        self._start_time = 0
        self._running = True
        self._intentional_stop = False # Flag to prevent auto-reconnect on manual stop/quit
        self._join_cmd_id = 0
        self._text_message_buffer = {}
        self.main_window = None # Reference to the MainBotWindow instance

        # --- Feature Specific State ---
        self.polls = {} # Stores active polls {poll_id: {'q': '...', 'opts': [...], 'votes': {user_id: vote_idx}}}
        self.next_poll_id = 1
        self.warning_counts = {} # Stores warning counts {user_id: count}

        # ** NEW: Feature state variables (Toggles) **
        self.announce_join_leave = True
        self.allow_channel_messages = True # Initial state, updated on login based on rights
        self.allow_broadcast = True # Initial state, updated on login based on rights
        self.allow_gemini_pm = True # Initial state, updated on Gemini init/toggle
        self.allow_gemini_channel = True # Initial state, updated on Gemini init/toggle
        self.bot_locked = False
        self.welcome_message_mode = "template" # Options: "template", "gemini"
        # self.filter_enabled is set above based on config

        self.blocked_commands = set()
        # Define commands that *cannot* be blocked
        self.UNBLOCKABLE_COMMANDS = {'h', 'q', 'rs', 'block', 'unblock', 'info', 'whoami', 'rights', 'lock', '!tfilter', '!tgmmode'}

        # --- Gemini Initialization ---
        self._gemini_enabled = False # Set to False initially
        self.gemini_model = None
        if not GEMINI_AVAILABLE:
            logging.warning("Gemini library not available, features disabled.")
        elif not self.gemini_api_key: # Use locally stored key
             logging.warning("Gemini API Key is missing in config. Gemini features will be disabled.")
        else:
            self._init_gemini(self.gemini_api_key) # Use helper method

        # Log feature status
        if not self._weather_enabled:
             logging.info("Weather feature is disabled (requests library missing or no API key).")
        else:
            logging.info("Weather feature is enabled.")

        if not self.filtered_words:
            logging.info("Word filter is inactive (no words defined in config). Filter globally disabled.")
        elif not self.filter_enabled:
            logging.info(f"Word filter has {len(self.filtered_words)} words, but is disabled.")
        else:
            logging.info(f"Word filter active and enabled with {len(self.filtered_words)} words.")


    def _init_gemini(self, api_key):
        """Helper to initialize or re-initialize Gemini"""
        if not GEMINI_AVAILABLE:
            self._gemini_enabled = False
            self.allow_gemini_pm = False # Also disable feature flags
            self.allow_gemini_channel = False
            self.gemini_model = None
            return False

        if not api_key:
            logging.warning("Attempted to initialize Gemini without API key.")
            self._gemini_enabled = False
            self.allow_gemini_pm = False
            self.allow_gemini_channel = False
            self.gemini_model = None
            return False

        try:
            genai.configure(api_key=api_key)
            # Try gemini-1.5-flash first, fall back if needed
            try:
                self.gemini_model = genai.GenerativeModel('gemini-1.5-flash-latest')
                logging.info("Gemini 1.5 Flash model initialized successfully.")
            except Exception:
                logging.warning("Failed to initialize gemini-1.5-flash, trying gemini-pro...")
                self.gemini_model = genai.GenerativeModel('gemini-pro')
                logging.info("Gemini Pro model initialized successfully.")

            # Successfully initialized model, check if feature flags were manually disabled
            # Don't automatically enable toggles here, let the existing state or login process handle it.
            self._gemini_enabled = True
            return True

        except Exception as e:
            logging.error(f"Failed to initialize Gemini: {e}. Gemini features will be disabled.", exc_info=True)
            self.gemini_model = None
            self._gemini_enabled = False
            self.allow_gemini_pm = False
            self.allow_gemini_channel = False
            return False


    def set_main_window(self, window):
        """Sets the reference to the main GUI window."""
        self.main_window = window
        self._log_to_gui("Main GUI window linked.")

    def _log_to_gui(self, message):
        """Safely logs a message to the GUI window if available."""
        if self.main_window and self.main_window.logDisplay: # Check if display exists
            # Ensure this runs on the main GUI thread
            wx.CallAfter(self.main_window.log_message, message)
        else:
            # Fallback to console if GUI not ready/linked
            logging.info(f"[GUI LOG FALLBACK] {message}")

    # --- Helper Functions ---
    def _send_pm(self, recipient_id: int, message: str):
        if not message or recipient_id <= 0: return
        # Basic check: Bot should be logged in to send PMs
        if not self._logged_in or self._my_user_id <= 0:
             logging.warning(f"Attempted to send PM to {recipient_id} while not logged in.")
             return

        formatted_message = ttstr(message)
        log_preview = formatted_message[:120] + ('...' if len(formatted_message) > 120 else '')
        # self._log_to_gui(f"--> PM to {recipient_id}: {log_preview}") # Can be noisy

        response_msgs = buildTextMessage(formatted_message, TextMsgType.MSGTYPE_USER, nToUserID=recipient_id)
        for msg in response_msgs:
            cmd_id = self.doTextMessage(msg)
            if cmd_id == 0:
                log_msg = f"Failed to send private text message part command to user {recipient_id}."
                logging.error(log_msg)
                self._log_to_gui(f"[Error] {log_msg}")
                break

    def _send_channel_message(self, channel_id: int, message: str):
        if not message or channel_id <= 0: return False
        if not self._logged_in or self._my_user_id <= 0:
             logging.warning(f"Attempted to send channel msg to {channel_id} while not logged in.")
             return False

        if not self.allow_channel_messages: # Check feature toggle
            log_msg = f"Channel message to {channel_id} blocked by feature toggle."
            logging.info(log_msg)
            # Don't log to GUI, maybe PM sender if triggered by user?
            return False
        if self.bot_locked: # Check lock state
             log_msg = f"Channel message to {channel_id} blocked because bot is locked."
             logging.info(log_msg)
             return False

        if not (self.my_rights & UserRight.USERRIGHT_TEXTMESSAGE_CHANNEL):
            log_msg = f"Attempted to send to channel {channel_id}, but bot lacks USERRIGHT_TEXTMESSAGE_CHANNEL."
            logging.warning(log_msg)
            self._log_to_gui(f"[Warning] {log_msg}")
            return False

        formatted_message = ttstr(message)
        log_preview = formatted_message[:120] + ('...' if len(formatted_message) > 120 else '')
        # self._log_to_gui(f"--> Chan {channel_id}: {log_preview}") # Can be noisy

        channel_msgs = buildTextMessage(formatted_message, TextMsgType.MSGTYPE_CHANNEL, nChannelID=channel_id)
        success = True
        for msg in channel_msgs:
             cmd_id = self.doTextMessage(msg)
             if cmd_id == 0:
                  log_msg = f"Failed to send channel text message part to channel {channel_id}."
                  logging.error(log_msg)
                  self._log_to_gui(f"[Error] {log_msg}")
                  success = False
                  break
        return success

    def _send_broadcast(self, message: str):
        if not message: return False
        if not self._logged_in or self._my_user_id <= 0:
             logging.warning(f"Attempted to send broadcast while not logged in.")
             return False

        if not self.allow_broadcast: # Check feature toggle
            log_msg = "Broadcast blocked by feature toggle."
            logging.info(log_msg)
            return False
        if self.bot_locked: # Check lock state
             log_msg = "Broadcast blocked because bot is locked."
             logging.info(log_msg)
             return False

        if not (self.my_rights & UserRight.USERRIGHT_TEXTMESSAGE_BROADCAST):
             log_msg = "Attempted to send broadcast, but bot lacks USERRIGHT_TEXTMESSAGE_BROADCAST."
             logging.warning(log_msg)
             self._log_to_gui(f"[Warning] {log_msg}")
             return False

        formatted_message = ttstr(message)
        log_preview = formatted_message[:120] + ('...' if len(formatted_message) > 120 else '')
        # self._log_to_gui(f"--> Broadcast: {log_preview}")

        broadcast_msgs = buildTextMessage(formatted_message, TextMsgType.MSGTYPE_BROADCAST)
        success = True
        for msg in broadcast_msgs:
             cmd_id = self.doTextMessage(msg)
             if cmd_id == 0:
                  log_msg = "Failed to send broadcast text message part."
                  logging.error(log_msg)
                  self._log_to_gui(f"[Error] {log_msg}")
                  success = False
                  break
        return success

    def _is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_user_ids

    def _format_uptime(self, seconds: float) -> str:
        if seconds < 0: return "N/A"
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        mins, secs = divmod(rem, 60)
        parts = []
        if days >= 1: parts.append(f"{int(days)}days")
        if hours >= 1: parts.append(f"{int(hours)}hours")
        if mins >= 1: parts.append(f"{int(mins)}minutes")
        parts.append(f"{int(secs)}seconds")
        return " ".join(parts) if parts else "0s"

    def _find_user_by_nick(self, nickname: str) -> User | None:
        target_nick_lower = ttstr(nickname).lower()
        try:
            # Ensure we are connected before trying to get users
            if not (self.getFlags() & ClientFlags.CLIENT_CONNECTED):
                 logging.warning("Attempted user lookup but not connected.")
                 return None
            all_users = self.getServerUsers()
            if all_users:
                for user in all_users:
                    if user and user.nUserID > 0 and ttstr(user.szNickname).lower() == target_nick_lower:
                        return user
            else:
                 # This can happen briefly during connection/disconnection, might not be an error
                 logging.debug("getServerUsers returned None or empty during nickname lookup.")
        except TeamTalkError as e:
             # Ignore "Not logged in" error if it happens during shutdown race condition
             if e.errnum != ClientError.CMDERR_NOT_LOGGEDIN:
                 logging.error(f"SDK error getting server users for nickname lookup: {e}")
        except Exception as e:
            logging.error(f"Unexpected error getting server users for nickname lookup: {e}")
        return None

    def _save_runtime_config(self, save_gemini_key=False):
        """Updates the internal config dict and saves it to file."""
        if not self.config:
            logging.error("Cannot save runtime config, internal config dictionary is missing.")
            return

        log_msg = "Saving updated runtime configuration..."
        logging.info(log_msg)
        self._log_to_gui(log_msg)

        # Update the dictionary directly (ensure sections exist)
        if 'Connection' not in self.config: self.config['Connection'] = {}
        if 'Bot' not in self.config: self.config['Bot'] = {}
        self.config['Bot']['filtered_words'] = ','.join(sorted(list(self.filtered_words)))
        self.config['Connection']['nickname'] = ttstr(self.nickname) # Use current internal nickname
        self.config['Bot']['status_message'] = ttstr(self.status_message) # Use current internal status
        if save_gemini_key:
             self.config['Bot']['gemini_api_key'] = self.gemini_api_key # Save updated key
             log_msg = "Saving Gemini API key to config file."
             logging.info(log_msg)
             self._log_to_gui(log_msg)


        # Call the global save function with the updated structured data
        save_config(self.config)

    def _mark_stopped_intentionally(self):
        """Flags that the stop was initiated by user/admin action."""
        self._intentional_stop = True

    def _handle_poll_command(self, args_str, user_id):
        # Quick parsing: split by ", look for >= 3 parts (cmd, question, opt1, opt2...)
        try:
            parts = [p.strip() for p in args_str.split('"') if p.strip()]
            if len(parts) < 3: # Need question + at least 2 options
                self._send_pm(user_id, 'Usage: !poll "Question" "Option A" "Option B" ...')
                return

            question = parts[0]
            options = parts[1:]
            if len(options) > 10: # Limit options maybe?
                 self._send_pm(user_id, "Error: Maximum 10 options allowed.")
                 return

            poll_id = self.next_poll_id
            self.next_poll_id += 1

            self.polls[poll_id] = {
                'q': question,
                'opts': options,
                'votes': {} # user_id: option_index (0-based)
            }

            poll_msg = [f"--- Poll #{poll_id} Created ---"]
            poll_msg.append(f"Q: {question}")
            for i, opt in enumerate(options):
                poll_msg.append(f" {i+1}. {opt}")
            poll_msg.append(f"To vote, PM me: !vote {poll_id} <option_number>")
            poll_msg.append(f"To see results, PM me: !results {poll_id}")

            # Announce in channel if bot is in one, otherwise just PM creator
            if self._in_channel and self._target_channel_id > 0:
                self._send_channel_message(self._target_channel_id, "\n".join(poll_msg))
                self._send_pm(user_id, f"Poll #{poll_id} created and announced in the channel.")
            else:
                self._send_pm(user_id, "\n".join(poll_msg))
                self._send_pm(user_id, "(Poll created via PM as I'm not in a channel)")

        except Exception as e:
            logging.error(f"Error creating poll: {e}")
            self._send_pm(user_id, f"Error creating poll. Use double quotes: !poll \"Q\" \"A\" \"B\"")

    def _handle_vote_command(self, args_str, user_id):
        parts = args_str.split(maxsplit=1)
        if len(parts) != 2:
            self._send_pm(user_id, "Usage: !vote <poll_id> <option_number>")
            return

        try:
            poll_id = int(parts[0])
            vote_num = int(parts[1]) # User votes 1-based

            if poll_id not in self.polls:
                self._send_pm(user_id, f"Error: Poll #{poll_id} not found or has ended.")
                return

            poll_data = self.polls[poll_id]
            num_options = len(poll_data['opts'])

            if not (1 <= vote_num <= num_options):
                self._send_pm(user_id, f"Error: Invalid option number. Choose between 1 and {num_options}.")
                return

            vote_idx = vote_num - 1 # Store 0-based index
            poll_data['votes'][user_id] = vote_idx
            self._send_pm(user_id, f"Your vote for option {vote_num} ('{poll_data['opts'][vote_idx]}') in Poll #{poll_id} has been recorded.")

        except ValueError:
            self._send_pm(user_id, "Error: Poll ID and option number must be numbers.")
        except Exception as e:
            logging.error(f"Error processing vote: {e}")
            self._send_pm(user_id, "An error occurred while processing your vote.")

    def _handle_results_command(self, args_str, user_id):
        try:
            poll_id_str = args_str.strip()
            if not poll_id_str: # Handle case where no ID is given - maybe show list of active polls?
                active_polls = list(self.polls.keys())
                if not active_polls:
                    self._send_pm(user_id, "There are no active polls.")
                else:
                    self._send_pm(user_id, f"Active Poll IDs: {', '.join(map(str, active_polls))}\nUsage: !results <poll_id>")
                return

            poll_id = int(poll_id_str)
            if poll_id not in self.polls:
                self._send_pm(user_id, f"Error: Poll #{poll_id} not found or has ended.")
                return

            poll_data = self.polls[poll_id]
            total_votes = len(poll_data['votes'])
            results = [0] * len(poll_data['opts']) # Initialize counts for each option

            for voter_id, vote_idx in poll_data['votes'].items():
                if 0 <= vote_idx < len(results):
                    results[vote_idx] += 1

            result_msg = [f"--- Poll #{poll_id} Results ---"]
            result_msg.append(f"Q: {poll_data['q']}")
            result_msg.append(f"Total Votes: {total_votes}")

            for i, opt_text in enumerate(poll_data['opts']):
                count = results[i]
                percent = (count / total_votes * 100) if total_votes > 0 else 0
                result_msg.append(f" {i+1}. {opt_text} - {count} votes ({percent:.1f}%)")

            self._send_pm(user_id, "\n".join(result_msg))

        except ValueError:
            self._send_pm(user_id, "Usage: !results <poll_id>")
        except Exception as e:
            logging.error(f"Error getting poll results: {e}")
            self._send_pm(user_id, "An error occurred while getting poll results.")

    # --- Weather Feature Helper ---
    def _handle_weather_command(self, location, channel_id, user_id):
        # Determines where to send the response based on channel_id/user_id
        if not self._weather_enabled:
            err_msg = "[Bot] Weather feature is disabled (check API key/library)."
            if channel_id: self._send_channel_message(channel_id, err_msg)
            elif user_id: self._send_pm(user_id, err_msg)
            return

        api_key = self.weather_api_key
        base_url = "http://api.openweathermap.org/data/2.5/weather?"
        complete_url = base_url + "appid=" + api_key + "&q=" + location + "&units=metric" # Use metric units

        try:
            response = requests.get(complete_url, timeout=10) # Add timeout
            response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
            data = response.json()

            if data["cod"] != 200 and data["cod"] != "200": # Check API's own status code
                error_msg = data.get("message", "Unknown API error")
                reply = f"[Weather Error] {error_msg} for '{location}'."
                logging.warning(f"OpenWeatherMap API error for '{location}': {error_msg}")
            else:
                main = data.get("main", {})
                weather = data.get("weather", [{}])[0]
                wind = data.get("wind", {})
                sys_info = data.get("sys", {})

                temp = main.get("temp", "N/A")
                feels_like = main.get("feels_like", "N/A")
                humidity = main.get("humidity", "N/A")
                description = weather.get("description", "N/A").capitalize()
                wind_speed = wind.get("speed", "N/A") # meters/sec
                city_name = data.get("name", location)
                country = sys_info.get("country", "")

                # Convert m/s to km/h roughly
                wind_kmh = "N/A"
                if isinstance(wind_speed, (int, float)):
                    wind_kmh = f"{wind_speed * 3.6:.1f} km/h"

                reply = (f"Weather in {city_name}, {country}: {description}. "
                         f"Temp: {temp}°C (Feels like: {feels_like}°C). "
                         f"Humidity: {humidity}%. Wind: {wind_kmh}.")

        except requests.exceptions.Timeout:
             reply = f"[Weather Error] Request timed out for '{location}'."
             logging.error(f"Timeout getting weather for {location}")
        except requests.exceptions.RequestException as e:
            reply = f"[Weather Error] Could not fetch weather for '{location}'. Check location or API key."
            logging.error(f"Error getting weather for {location}: {e}")
        except Exception as e:
             reply = f"[Weather Error] An unexpected error occurred processing weather for '{location}'."
             logging.error(f"Unexpected weather error for {location}: {e}", exc_info=True)


        # Send reply
        if channel_id:
            self._send_channel_message(channel_id, reply)
        elif user_id:
            self._send_pm(user_id, reply)

    # --- Filter Management Helper ---
    def _handle_filter_command(self, args_str, user_id):
        parts = args_str.split(maxsplit=1)
        sub_command = parts[0].lower() if parts else ""
        word = parts[1].strip().lower() if len(parts) > 1 else ""

        if sub_command == "add":
            if not word:
                self._send_pm(user_id, "Usage: !filter add <word_to_filter>")
                return
            if word in self.filtered_words:
                self._send_pm(user_id, f"Word '{word}' is already in the filter list.")
            else:
                self.filtered_words.add(word)
                self.filter_enabled = True # Ensure filter is enabled when adding a word
                self._save_runtime_config() # Save changes
                self._send_pm(user_id, f"Word '{word}' added to the filter list. Filter automatically enabled.")
                self._log_to_gui(f"[Filter] Admin added '{word}' to filter list. Filter enabled.")
                logging.info(f"Admin (ID: {user_id}) added '{word}' to filter list. Filter enabled.")

        elif sub_command == "remove":
            if not word:
                self._send_pm(user_id, "Usage: !filter remove <word_to_remove>")
                return
            if word in self.filtered_words:
                self.filtered_words.discard(word) # Use discard, no error if not found
                if not self.filtered_words: # If list becomes empty, disable filter
                    self.filter_enabled = False
                    logging.info("Filter list became empty, disabling filter globally.")
                    self._log_to_gui("[Filter] Filter list empty, filter disabled.")
                self._save_runtime_config() # Save changes
                self._send_pm(user_id, f"Word '{word}' removed from the filter list.")
                self._log_to_gui(f"[Filter] Admin removed '{word}' from filter list.")
                logging.info(f"Admin (ID: {user_id}) removed '{word}' from filter list.")
            else:
                self._send_pm(user_id, f"Word '{word}' was not found in the filter list.")

        elif sub_command == "list":
            if not self.filtered_words:
                self._send_pm(user_id, "The filter list is currently empty.")
            else:
                filter_list_str = ", ".join(sorted(list(self.filtered_words)))
                status = "ENABLED" if self.filter_enabled else "DISABLED"
                self._send_pm(user_id, f"Filtered Words ({status}): {filter_list_str}")
        else:
            self._send_pm(user_id, "Usage: !filter <add|remove|list> [word]")

    # --- Control Functions ---
    def stop(self):
        """Signals the bot to stop and performs cleanup."""
        if not self._running:
            return
        log_msg = "Stop requested."
        logging.info(log_msg)
        self._log_to_gui(log_msg)
        self._running = False # Set the flag first

        # Short delay to allow event loop to potentially exit naturally
        time.sleep(0.1)

        try:
            # Check if the TeamTalk instance object (_tt) still exists and is valid
            if self._tt is None or not hasattr(self, 'getFlags') or not callable(self.getFlags):
                 logging.warning("TeamTalk instance is invalid or getFlags not available during stop, cannot perform clean disconnect/logout.")
                 return # Skip disconnect/logout if instance is bad

            flags = 0
            try:
               flags = self.getFlags()
               logging.debug(f"Current flags during stop: {flags:#x}")
            except TeamTalkError as e:
                # Ignore "Not connected" or "Not logged in" errors during shutdown flag check
                if e.errnum not in [ClientError.CMDERR_NOT_CONNECTED, ClientError.CMDERR_NOT_LOGGEDIN]:
                    logging.warning(f"Could not get flags during shutdown: {e}. Assuming not connected.")
            except Exception as e:
                logging.warning(f"Unexpected error getting flags during shutdown: {e}. Assuming not connected.")


            # Attempt logout/disconnect only if connected/connecting
            if flags & (ClientFlags.CLIENT_CONNECTING | ClientFlags.CLIENT_CONNECTED):
                if self._logged_in:
                    logging.info("Logging out...")
                    self._log_to_gui("Logging out...")
                    if hasattr(self, 'doLogout') and callable(self.doLogout):
                        try:
                            res = self.doLogout()
                            if res == 0: logging.error("Failed to send logout command.")
                            else: logging.info(f"Logout command sent (CmdID: {res}).")
                            time.sleep(0.2) # Give time for command processing
                        except TeamTalkError as e:
                             if e.errnum != ClientError.CMDERR_NOT_LOGGEDIN: # Ignore if already logged out
                                 logging.error(f"TeamTalk SDK Error during doLogout: {e}")
                        except Exception as e:
                            logging.error(f"Unexpected error during doLogout: {e}")

                    else:
                        logging.error("doLogout method not found or not callable during stop.")

                logging.info("Disconnecting...")
                self._log_to_gui("Disconnecting...")
                if hasattr(self, 'disconnect') and callable(self.disconnect):
                    try:
                        disconnected = self.disconnect()
                        if not disconnected: logging.error("Failed to send disconnect command.")
                        else: logging.info("Disconnect command sent successfully.")
                        time.sleep(0.3) # Give time for potential network close
                    except TeamTalkError as e:
                         if e.errnum != ClientError.CMDERR_NOT_CONNECTED: # Ignore if already disconnected
                             logging.error(f"TeamTalk SDK Error during disconnect: {e}")
                    except Exception as e:
                        logging.error(f"Unexpected error during disconnect: {e}")
                else:
                     logging.error("disconnect method not found or not callable during stop.")

            else:
                 logging.info("Not connected or connecting, skipping logout/disconnect commands.")

        except TeamTalkError as e:
            logging.error(f"TeamTalk SDK Error during stop sequence (outside specific calls): {e}")
        except Exception as e:
            logging.error(f"Unexpected error during stop sequence (outside specific calls): {e}", exc_info=True)
        finally:
             # Final cleanup: Close the TeamTalk instance regardless of connection state
             try:
                 if self._tt is not None and hasattr(self, 'closeTeamTalk') and callable(self.closeTeamTalk):
                    log_msg = "Closing TeamTalk SDK instance..."
                    logging.info(log_msg)
                    # Don't log to GUI here as it might already be closed
                    self.closeTeamTalk() # This will invalidate self._tt
                    log_msg = "TeamTalk SDK closed."
                    logging.info(log_msg)
                 elif self._tt is None:
                    logging.debug("TeamTalk instance was already None before final close.")
                 else:
                     logging.error("closeTeamTalk method not found or not callable during final cleanup.")
             except Exception as e:
                  logging.error(f"Error closing TeamTalk instance during final cleanup: {e}")
             finally:
                 self._tt = None # Explicitly set to None after attempting close

    def start(self):
        """Connects to the server and starts the event loop."""
        log_msg = f"Initializing TeamTalk Bot Session..."
        logging.info(log_msg)
        self._log_to_gui(log_msg) # Log to GUI if available
        self._start_time = time.time()
        self._intentional_stop = False # Reset intentional stop flag on new start
        self._running = True # Ensure running flag is set

        connect_msg = f"Attempting to connect to {ttstr(self.host)}:{self.tcp_port}..."
        logging.info(connect_msg)
        self._log_to_gui(connect_msg)

        try:
            # Check if the underlying _tt instance is valid *after* super().__init__()
            # TeamTalk5 wrapper might initialize _tt=None until connect is called
            # If connect itself fails below, it will be handled.
            if self._tt is None:
                logging.debug("TeamTalk instance (_tt) is None before connect, proceeding...")

            connected = self.connect(self.host, self.tcp_port, self.udp_port, 0, 0, bEncrypted=False)
            if not connected:
                log_msg = "Initial connection attempt failed immediately (connect returned false)."
                logging.error(log_msg)
                self._log_to_gui(f"[Error] {log_msg}")
                # Don't call stop() here, let the onConnectFailed handler trigger restart logic if needed
                # Set running false if connect fails right away, so it doesn't loop?
                self._running = False # Signal loop should not run
                return

            log_msg = "Connection process started. Entering event loop."
            logging.info(log_msg)
            self._log_to_gui(log_msg)

            while self._running:
                # Check stop flag at the start of the loop
                if not self._running:
                     log_msg = "Event loop detected stop flag. Exiting loop."
                     logging.info(log_msg)
                     self._log_to_gui(log_msg)
                     break
                try:
                    # Check _tt validity inside the loop as well
                    if self._tt is None:
                         log_msg = "TeamTalk instance became None during event loop. Exiting loop."
                         logging.error(log_msg)
                         self._log_to_gui(f"[Error] {log_msg}")
                         self._running = False # Ensure loop terminates
                         break

                    # Run the event loop for a short duration
                    self.runEventLoop(nWaitMSec=100)

                except TeamTalkError as e:
                    log_msg = f"TeamTalk SDK Error in event loop: {e.errnum} - {e.errmsg}"
                    logging.error(log_msg)
                    self._log_to_gui(f"[SDK Error] {log_msg}")
                    # Decide whether to stop or let onConnectionLost handle it
                    # If it's a critical error, maybe stop. If connection related, let handler try reconnect.
                    # For now, let's assume most SDK errors here are connection related or temporary
                    # Let onConnectionLost or onCmdError handle it if they trigger.
                    # We might need a small sleep to avoid tight looping on persistent errors.
                    time.sleep(0.5)
                    # If the error persists causing fast looping, consider setting self._running = False
                    # Or check specific error codes (e.g., if it's CMDERR_NOT_CONNECTED, let onConnectionLost handle)

                except Exception as e:
                    log_msg = f"An unexpected error occurred in the event loop: {e}"
                    logging.error(log_msg, exc_info=True)
                    self._log_to_gui(f"[Fatal Error] {log_msg}")
                    self._running = False # Stop on unexpected errors
                    break # Exit inner loop

            log_msg = "Exited event loop (running flag is false)."
            logging.info(log_msg)
            self._log_to_gui(log_msg)

        except TeamTalkError as sdk_e:
             # This likely catches errors from the initial self.connect call
             log_msg = f"TeamTalk SDK Error during connection phase: {sdk_e.errnum} - {sdk_e.errmsg}"
             logging.critical(log_msg)
             self._log_to_gui(f"[SDK Critical] {log_msg}")
             self._running = False # Ensure loop doesn't start if connect fails critically
        except Exception as start_e:
             log_msg = f"Unexpected error during bot start/connect phase: {start_e}"
             logging.critical(log_msg, exc_info=True)
             self._log_to_gui(f"[Fatal Error] {log_msg}")
             self._running = False
        finally:
            # This finally block runs after the loop exits or if an exception occurred during start
            log_msg = "Start method finishing, ensuring cleanup via stop()..."
            logging.info(log_msg)
            # Don't log to GUI in finally, it might be gone
            self.stop() # Call stop to ensure resources are released


    # --- Override Event Handlers (Add GUI Logging, Save Nick/Status, Auto-Reconnect) ---

    def onConnectSuccess(self):
        log_msg = "Successfully connected to the server."
        logging.info(log_msg)
        self._log_to_gui(log_msg)

        login_msg = f"Attempting login as '{ttstr(self.username)}' with nickname '{ttstr(self.nickname)}'..."
        logging.info(login_msg)
        self._log_to_gui(login_msg)
        try:
            cmd_id = self.doLogin(self.nickname, self.username, self.password, self.client_name)
            if cmd_id == 0:
                log_msg = "Failed to send login command (doLogin returned 0)."
                logging.error(log_msg)
                self._log_to_gui(f"[Error] {log_msg}")
                self._mark_stopped_intentionally() # Prevent reconnect loop on immediate login failure
                self.stop()
        except TeamTalkError as e:
            log_msg = f"SDK Error sending login command: {e.errnum} - {e.errmsg}"
            logging.error(log_msg)
            self._log_to_gui(f"[SDK Error] {log_msg}")
            self._mark_stopped_intentionally()
            self.stop()
        except Exception as e:
            log_msg = f"Unexpected error sending login command: {e}"
            logging.error(log_msg, exc_info=True)
            self._log_to_gui(f"[Fatal Error] {log_msg}")
            self._mark_stopped_intentionally()
            self.stop()

    def onConnectFailed(self):
        log_msg = "Connection failed."
        logging.error(log_msg)
        self._log_to_gui(f"[Error] {log_msg}")

        # Don't attempt reconnect if stop was intentional or already stopped
        if self._running and not self._intentional_stop:
            delay = random.randint(self.reconnect_delay_min, self.reconnect_delay_max)
            recon_msg = f"Connection failed. Attempting reconnect in {delay} seconds..."
            logging.info(recon_msg)
            self._log_to_gui(recon_msg)
            time.sleep(delay)
            # Check again if running before scheduling restart (user might have quit during sleep)
            if self._running and not self._intentional_stop:
                wx.CallAfter(self._initiate_restart)
            else:
                 logging.info("Reconnect aborted, bot was stopped during delay.")
        else:
            log_stop_msg = "Connection failed, not reconnecting (bot stopped or intentional)."
            logging.info(log_stop_msg)
            self._log_to_gui(log_stop_msg)
            # Ensure stop is called to clean up if necessary, though start() might already handle it
            self.stop()


    def onConnectionLost(self):
        log_msg = "Connection lost."
        logging.error(log_msg)
        self._log_to_gui(f"[Error] {log_msg}")

        # Reset state immediately
        was_logged_in = self._logged_in
        self._logged_in = False
        self._in_channel = False
        self._my_user_id = -1
        self.admin_user_ids.clear()
        self.my_rights = UserRight.USERRIGHT_NONE
        self.blocked_commands.clear() # Clear blocks on disconnect
        self.polls.clear() # Clear polls on disconnect
        self.warning_counts.clear() # Clear warnings on disconnect

        # Update GUI to reflect disconnected state
        if self.main_window:
             wx.CallAfter(self.main_window.update_feature_list) # Clears/updates the list

        # Attempt reconnect only if previously logged in and not intentionally stopped
        if self._running and not self._intentional_stop and was_logged_in:
             delay = random.randint(self.reconnect_delay_min, self.reconnect_delay_max)
             recon_msg = f"Connection lost. Attempting automatic reconnect in {delay} seconds..."
             logging.info(recon_msg)
             self._log_to_gui(recon_msg)
             time.sleep(delay) # Wait before scheduling restart
             # Check running state again after sleep
             if self._running and not self._intentional_stop:
                 wx.CallAfter(self._initiate_restart) # Schedule restart on main thread
             else:
                 logging.info("Reconnect aborted, bot was stopped during delay.")
        else:
             log_msg_stop = "Connection lost, but not attempting reconnect (stopped, intentional, or never logged in)."
             logging.info(log_msg_stop)
             self._log_to_gui(log_msg_stop)
             # No need to call stop() here, as the event loop in start() will exit and call stop()
             # self.stop() # Avoid calling stop here, let the main loop handle it


    def onCmdError(self, cmdId: int, errmsg: ClientErrorMsg):
        error_msg_str = ttstr(errmsg.szErrorMsg)
        log_msg = f"Command Error for CmdID {cmdId}: {errmsg.nErrorNo} - {error_msg_str}"
        logging.error(log_msg)
        self._log_to_gui(f"[Cmd Error {cmdId}] {errmsg.nErrorNo} - {error_msg_str}")

        # --- Handle Critical Errors that should stop the bot ---
        critical_errors = [
            ClientError.CMDERR_INVALID_ACCOUNT,
            ClientError.CMDERR_ALREADY_LOGGEDIN,
            ClientError.CMDERR_SERVER_BANNED,
            # ClientError.CMDERR_INVALID_CLIENT_VERSION, # Assuming this exists
            # Add other potentially fatal errors here
        ]

        if errmsg.nErrorNo in critical_errors:
            error_reason = {
                ClientError.CMDERR_INVALID_ACCOUNT: "Invalid username or password.",
                ClientError.CMDERR_ALREADY_LOGGEDIN: "Account may already be logged in elsewhere.",
                ClientError.CMDERR_SERVER_BANNED: "This IP or account is banned from the server.",
                # ClientError.CMDERR_INVALID_CLIENT_VERSION: "Client version is incompatible with the server."
            }.get(errmsg.nErrorNo, f"Critical Error {errmsg.nErrorNo}")

            self._log_to_gui(f"Login/Connection failed: {error_reason}")
            self._mark_stopped_intentionally() # Prevent reconnect loops on these errors
            # Don't call stop() directly here, let the calling context or main loop handle termination
            # Setting the flag is enough to prevent reconnects and signal shutdown
            return # Stop further processing for this error

        # --- Handle Channel Join Errors ---
        if cmdId == self._join_cmd_id:
             join_error_reason = {
                 ClientError.CMDERR_CHANNEL_NOT_FOUND: f"Channel '{ttstr(self.target_channel_path)}' not found.",
                 ClientError.CMDERR_INCORRECT_CHANNEL_PASSWORD: f"Incorrect password for '{ttstr(self.target_channel_path)}'.",
                 ClientError.CMDERR_CHANNEL_BANNED: f"Banned from '{ttstr(self.target_channel_path)}'.",
                 ClientError.CMDERR_MAX_CHANNEL_USERS_EXCEEDED: f"Channel '{ttstr(self.target_channel_path)}' is full.",
             }.get(errmsg.nErrorNo, error_msg_str) # Default to the SDK message

             self._log_to_gui(f"Failed to join channel: {join_error_reason}")
             # Maybe attempt to join Root if the target channel fails?
             # Or just log the error and stay where it is (likely Root if login succeeded).
             # For now, just log.


    def onCmdMyselfLoggedIn(self, userid: int, useraccount: UserAccount):
        self._logged_in = True
        self._my_user_id = userid
        self.my_rights = useraccount.uUserRights
        log_msg = f"Successfully logged in! My UserID: {self._my_user_id}"
        logging.info(log_msg)
        self._log_to_gui(log_msg)
        self._log_to_gui(f"Username: {ttstr(useraccount.szUsername)}, UserType: {useraccount.uUserType}")
        self._log_to_gui(f"My Rights: {self.my_rights:#010x}")

        # Set initial feature states based on rights and Gemini status
        self.allow_channel_messages = bool(self.my_rights & UserRight.USERRIGHT_TEXTMESSAGE_CHANNEL)
        self.allow_broadcast = bool(self.my_rights & UserRight.USERRIGHT_TEXTMESSAGE_BROADCAST)
        self.allow_gemini_pm = self._gemini_enabled # Gemini PM allowed if init was successful
        self.allow_gemini_channel = self._gemini_enabled # Gemini Channel allowed if init was successful



        # --- Show Main Window & Update Features ---
        if self.main_window:
            wx.CallAfter(self.main_window.Show) # Make GUI visible
            wx.CallAfter(self.main_window.SetTitle, f"TeamTalk Bot - {ttstr(self.nickname)} @ {ttstr(self.host)}")
            wx.CallAfter(self.main_window.update_feature_list) # Populate features list
        # -------------------------------------------

        # --- Set Initial Status Message ---
        if self.status_message:
            status_log = f"Setting initial status message from config: '{ttstr(self.status_message)}'"
            logging.info(status_log)
            self._log_to_gui(status_log)
            try:
                cmd_id = self.doChangeStatus(0, self.status_message)
                if cmd_id == 0:
                    logging.error("Failed to send initial status change command.")
                    self._log_to_gui("[Error] Failed setting initial status.")
            except TeamTalkError as e:
                 logging.error(f"SDK Error setting initial status: {e.errnum} - {e.errmsg}")
                 self._log_to_gui(f"[SDK Error] Failed setting initial status: {e.errmsg}")
            except Exception as e:
                 logging.error(f"Unexpected error setting initial status: {e}", exc_info=True)
                 self._log_to_gui("[Fatal Error] Failed setting initial status.")
        # -------------------------------

        # --- Resolve admin usernames ---
        self.admin_user_ids.clear()
        logging.info(f"Looking for admin users (configured): {self.admin_usernames_config}")
        self._log_to_gui(f"Configured Admins: {', '.join(self.admin_usernames_config) if self.admin_usernames_config else 'None'}")
        if self.admin_usernames_config:
            try:
                # Ensure we use a valid TeamTalk instance (_tt)
                if self._tt is None: raise TeamTalkError("TeamTalk instance is None during admin lookup.")

                all_users = self.getServerUsers()
                if all_users:
                    for user in all_users:
                        if not user or user.nUserID <= 0: continue
                        username_lower = ttstr(user.szUsername).lower()
                        if username_lower in self.admin_usernames_config:
                            self.admin_user_ids.add(user.nUserID)
                            logging.info(f"  Found admin: {ttstr(user.szNickname)} (ID: {user.nUserID}, User: {ttstr(user.szUsername)})")
                else:
                     # This might happen, log as debug/warning
                     logging.warning("getServerUsers returned None or empty while resolving admin IDs.")
            except TeamTalkError as e:
                 logging.error(f"SDK error retrieving server users to identify admins: {e.errnum} - {e.errmsg}")
            except Exception as e:
                logging.error(f"Error retrieving server users to identify admins: {e}")

        my_username_lower = ttstr(self.username).lower()
        if my_username_lower in self.admin_usernames_config:
             if self._my_user_id not in self.admin_user_ids:
                self.admin_user_ids.add(self._my_user_id)
                logging.info(f"  Bot account '{ttstr(self.nickname)}' is configured as admin.")

        admin_ids_str = ', '.join(map(str, self.admin_user_ids)) if self.admin_user_ids else 'None'
        self._log_to_gui(f"Resolved Admin User IDs: {admin_ids_str}")
        # ------------------------------------

        # --- Join Target Channel ---
        join_log = f"Attempting to join target channel '{ttstr(self.target_channel_path)}'..."
        logging.info(join_log)
        self._log_to_gui(join_log)
        target_id_on_login = -1

        try:
             if self._tt is None: raise TeamTalkError("TeamTalk instance is None during channel join.")

             target_id_on_login = self.getChannelIDFromPath(self.target_channel_path)

             if target_id_on_login <= 0:
                 logging.warning(f"Target channel '{ttstr(self.target_channel_path)}' not found by path. Attempting to join Root.")
                 self._log_to_gui(f"Warning: Channel '{ttstr(self.target_channel_path)}' not found, trying Root.")
                 target_id_on_login = self.getRootChannelID()
                 if target_id_on_login > 0:
                     self.target_channel_path = ttstr("/") # Update path
                     self.channel_password = ttstr("") # Clear password if joining root
                 else:
                      logging.error("Could not even find Root channel ID!")
                      self._log_to_gui("[Error] Could not find Root channel to join.")

             if target_id_on_login > 0:
                 self._target_channel_id = target_id_on_login # Store the ID we are attempting to join
                 logging.info(f"Joining channel ID: {self._target_channel_id} ('{ttstr(self.target_channel_path)}')")
                 self._join_cmd_id = self.doJoinChannelByID(self._target_channel_id, self.channel_password)
                 if self._join_cmd_id == 0:
                     log_msg = "Failed to send join channel command immediately (doJoinChannelByID returned 0)."
                     logging.error(log_msg)
                     self._log_to_gui(f"[Error] {log_msg}")
             else:
                  log_msg = "Could not determine a valid channel ID to join (Target or Root). Staying put."
                  logging.error(log_msg)
                  self._log_to_gui(f"[Error] {log_msg}")

        except TeamTalkError as e:
             log_msg = f"SDK Error resolving/joining channel: {e.errnum} - {e.errmsg}"
             logging.error(log_msg)
             self._log_to_gui(f"[SDK Error] {log_msg}")
        except Exception as e:
             log_msg = f"Unexpected error resolving/joining channel: {e}"
             logging.error(log_msg, exc_info=True)
             self._log_to_gui(f"[Fatal Error] {log_msg}")
        # --------------------------

    def onCmdMyselfLoggedOut(self):
        log_msg = "Logged out."
        logging.info(log_msg)
        self._log_to_gui(log_msg)
        self._logged_in = False
        self._in_channel = False
        self._my_user_id = -1
        self.admin_user_ids.clear()
        self.my_rights = UserRight.USERRIGHT_NONE
        self.blocked_commands.clear() # Clear blocks
        self.polls.clear() # Clear polls
        self.warning_counts.clear() # Clear warnings
        # Update GUI to reflect disconnected state
        if self.main_window:
            wx.CallAfter(self.main_window.update_feature_list)

    def onCmdUserJoinedChannel(self, user: User):
        if not user or user.nUserID <= 0: return
        channel_id = user.nChannelID
        user_id = user.nUserID
        user_nick = ttstr(user.szNickname) if user.szNickname else f"UserID_{user_id}"
        channel_path = f"ID {channel_id}" # Default path
        try:
            # Ensure _tt is valid before calling getChannelPath
            if self._tt is not None and hasattr(self, 'getChannelPath') and callable(self.getChannelPath):
                 channel_path = ttstr(self.getChannelPath(channel_id))
        except TeamTalkError as e:
            # Log error getting path but continue
            logging.warning(f"SDK Error getting path for joined channel {channel_id}: {e.errmsg}")
        except Exception as e:
             logging.warning(f"Unexpected error getting path for joined channel {channel_id}: {e}")


        if user_id == self._my_user_id:
            # This confirms the bot successfully joined *a* channel.
            # Update the target ID and path to where it actually landed.
            self._target_channel_id = channel_id
            self.target_channel_path = channel_path
            self._in_channel = True
            log_msg = f"Successfully joined channel: {channel_path} (ID: {channel_id})"
            logging.info(log_msg)
            self._log_to_gui(log_msg)

            # Re-check rights after joining, as channel rights might differ
            # (Though UserAccount rights on login are usually server-wide)
            if not (self.my_rights & UserRight.USERRIGHT_TEXTMESSAGE_CHANNEL):
                warn_msg = f"Warning: Bot joined {channel_path}, but lacks USERRIGHT_TEXTMESSAGE_CHANNEL."
                logging.warning(warn_msg)
                self._log_to_gui(warn_msg)
                self.allow_channel_messages = False # Reflect lack of rights in feature state
                if self.main_window: wx.CallAfter(self.main_window.update_feature_list)
            else:
                 # Ensure allow_channel_messages is true if rights exist and wasn't disabled manually
                 if not self.allow_channel_messages:
                      logging.info(f"Bot has channel message rights in {channel_path}, but feature was toggled off.")
                 # Don't automatically re-enable it here, respect the toggle state.

        else:
            # Another user joined a channel
            log_msg = f"User '{user_nick}' (ID: {user_id}) joined channel {channel_path} (ID: {channel_id})"
            logging.info(log_msg)
            self._log_to_gui(log_msg)

            # Check if this newly joined user is an admin based on config
            username_lower = ttstr(user.szUsername).lower()
            if username_lower in self.admin_usernames_config and user_id not in self.admin_user_ids:
                 self.admin_user_ids.add(user_id)
                 logging.info(f"  Recognized joining user '{user_nick}' as admin.")
                 self._log_to_gui(f"Recognized joining user '{user_nick}' as admin.")

            # --- Welcome Message Feature (Check toggle and if it's the bot's channel) ---
            if self._in_channel and channel_id == self._target_channel_id and self.announce_join_leave:
                welcome_message = ""

                # Check the mode
                if self.welcome_message_mode == "gemini":
                    if self._gemini_enabled and self.gemini_model:
                        logging.info(f"Attempting Gemini welcome for {user_nick}...")
                        prompt = "give me 1 welcome message to say welcome for people in a channel, just go with the welcome message. dont say this is bla bla bla or anything. you can say anything to welcome the user, dont just hello everyone. the style is casual. and remember, you're saying is completely random, just go with that thing overtime"
                        try:
                            response = self.gemini_model.generate_content(prompt, stream=False, safety_settings=GEMINI_SAFETY_SETTINGS)
                            # Safely extract text
                            if hasattr(response, 'text'):
                                welcome_message = response.text
                            elif hasattr(response, 'parts') and response.parts:
                                welcome_message = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                            elif hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                                logging.warning(f"Gemini welcome message blocked: {response.prompt_feedback.block_reason.name}")
                                welcome_message = "" # Fallback below
                            else:
                                logging.warning("Gemini welcome returned empty/unexpected response.")
                                welcome_message = "" # Fallback below

                            if not welcome_message.strip():
                                logging.warning("Gemini welcome resulted in empty text.")
                                welcome_message = "" # Fallback below

                        except Exception as e:
                            logging.error(f"Error calling Gemini for welcome message: {e}")
                            welcome_message = "" # Fallback below
                    else:
                        logging.warning("Welcome mode is Gemini, but Gemini is not enabled/ready. Falling back to template.")
                        welcome_message = "" # Fallback below

                # Fallback to template if mode is template, or if Gemini failed/returned empty
                if not welcome_message:
                    template_messages = [
                        "Hey {nick}, welcome!", "Welcome aboard, {nick}!", "Good to see you, {nick}!",
                        "Hi {nick}, pull up a chair!", "Greetings, {nick}!", "Howdy, {nick}!",
                    ]
                    welcome_message = random.choice(template_messages).format(nick=user_nick)

                # Send the final message (template or Gemini)
                logging.info(f"Sending welcome message ({self.welcome_message_mode} mode) to {user_nick} in {channel_path}.")
                self._send_channel_message(channel_id, welcome_message)
            # --- End Welcome Message ---


    def onCmdUserLeftChannel(self, channelid: int, user: User):
         if not user or user.nUserID <= 0: return
         user_id = user.nUserID
         user_nick = ttstr(user.szNickname) if user.szNickname else f"UserID_{user_id}"
         channel_path = f"ID {channelid}" # Default path
         try:
             if self._tt is not None and hasattr(self, 'getChannelPath') and callable(self.getChannelPath):
                  channel_path = ttstr(self.getChannelPath(channelid))
         except Exception as e:
              logging.warning(f"Error getting path for left channel {channelid}: {e}")


         if user_id == self._my_user_id:
              log_msg = f"Left channel {channel_path} (ID: {channelid})."
              logging.info(log_msg)
              self._log_to_gui(log_msg)
              self._in_channel = False
              # If we left the channel we thought was our target, reset target
              if channelid == self._target_channel_id:
                   self._target_channel_id = -1
                   self.target_channel_path = ttstr("")
         else:
              # Another user left a channel
              log_msg = f"User '{user_nick}' (ID: {user_id}) left channel {channel_path} (ID: {channelid})"
              # Log leave message only if announce is on AND it's the bot's current channel
              if self._in_channel and channelid == self._target_channel_id and self.announce_join_leave:
                   logging.info(log_msg)
                   self._log_to_gui(log_msg)
                   # Could add a leave message here too if desired
                   # leave_message = f"Goodbye, {user_nick}!"
                   # self._send_channel_message(channelid, leave_message)
              else:
                   logging.debug(f"User left (announcements off or different channel): {log_msg}") # Log less verbosely


    # --- onCmdUserTextMessage (Includes Command Blocking and Feature Checks) ---
    def onCmdUserTextMessage(self, textmessage: TextMessage):
        if not textmessage: return

        msg_from_id = textmessage.nFromUserID
        msg_type = textmessage.nMsgType
        msg_text_part = ttstr(textmessage.szMessage)
        is_more = textmessage.bMore
        msg_channel_id = textmessage.nChannelID

        # --- Buffer multi-part messages ---
        # Key uniquely identifies the source and destination (channel or user)
        buffer_key = (msg_from_id, msg_type, msg_channel_id if msg_type == TextMsgType.MSGTYPE_CHANNEL else 0)
        current_buffer = self._text_message_buffer.get(buffer_key, "")
        current_buffer += msg_text_part
        self._text_message_buffer[buffer_key] = current_buffer

        # If more parts are coming, wait for them
        if is_more: return

        # Last part received, process the full message
        full_message_text = self._text_message_buffer.pop(buffer_key, "")
        if not full_message_text:
            logging.debug(f"Empty message after buffering from key {buffer_key}")
            return

        # --- Ignore messages from self or if not logged in ---
        if not self._logged_in or msg_from_id == self._my_user_id or msg_from_id <= 0:
            return

        # --- Get Sender Info ---
        sender_nick = f"UserID_{msg_from_id}"
        sender_user = None
        try:
            if self._tt is not None and hasattr(self, 'getUser') and callable(self.getUser):
                sender_user = self.getUser(msg_from_id)
                if sender_user and sender_user.nUserID == msg_from_id:
                    sender_nick = ttstr(sender_user.szNickname)
        except Exception as e:
            logging.warning(f"Error getting user info for ID {msg_from_id}: {e}")


        # --- Log Received Message ---
        log_prefix = ""
        process_commands = False # Flag to control command processing

        if msg_type == TextMsgType.MSGTYPE_CHANNEL:
            chan_path = f"ID:{msg_channel_id}"
            try:
                 if self._tt is not None and hasattr(self, 'getChannelPath') and callable(self.getChannelPath):
                     chan_path = ttstr(self.getChannelPath(msg_channel_id))
            except Exception as e: logging.warning(f"Error getting channel path for msg log {msg_channel_id}: {e}")

            log_prefix = f"[{chan_path}]"
            # Log all received channel messages for debugging/audit purposes
            log_full = f"{log_prefix} <{sender_nick}> {full_message_text}"
            logging.info(log_full) # Log full message to file/console
            self._log_to_gui(log_full) # Log full message to GUI

            # Only process commands/AI if it's in the bot's current target channel
            if self._in_channel and msg_channel_id == self._target_channel_id:
                process_commands = True

        elif msg_type == TextMsgType.MSGTYPE_USER:
            log_prefix = f"[PM from {sender_nick}({msg_from_id})]"
            log_full = f"{log_prefix} {full_message_text}"
            logging.info(log_full) # Log full message to file/console
            self._log_to_gui(log_full) # Log full message to GUI
            process_commands = True # Process all PMs for commands

        elif msg_type == TextMsgType.MSGTYPE_BROADCAST:
            log_prefix = f"[Broadcast from {sender_nick}]"
            log_full = f"{log_prefix} {full_message_text}"
            logging.info(log_full) # Log full message to file/console
            self._log_to_gui(log_full) # Log full message to GUI
            # Ignore commands in broadcast for simplicity
            return

        # Check if filter is enabled *and* words exist *and* message needs processing
        if self.filter_enabled and process_commands and msg_type == TextMsgType.MSGTYPE_CHANNEL and self.filtered_words:
            msg_lower = full_message_text.lower() # Case-insensitive message check
            found_bad_word = None
            for word in self.filtered_words:
                # Use word boundaries to avoid filtering parts of words
                pattern = r'\b' + re.escape(word) + r'\b'
                if re.search(pattern, msg_lower, re.IGNORECASE):
                    found_bad_word = word
                    break # Found one, stop checking

            if found_bad_word:
                self._log_to_gui(f"[Filter] User '{sender_nick}' used filtered word '{found_bad_word}' in channel {msg_channel_id}")
                logging.info(f"User '{sender_nick}' (ID: {msg_from_id}) used filtered word '{found_bad_word}' in channel {msg_channel_id}")

                # Increment warning count
                current_warnings = self.warning_counts.get(msg_from_id, 0) + 1
                self.warning_counts[msg_from_id] = current_warnings

                warning_msg = f"Warning {current_warnings}/3 for {sender_nick}: Please avoid inappropriate language ('{found_bad_word}')."
                self._send_channel_message(msg_channel_id, warning_msg) # Warn in the channel

                if current_warnings >= 3:
                    self._log_to_gui(f"[Filter] Kicking user '{sender_nick}' after 3 warnings.")
                    logging.warning(f"Kicking user '{sender_nick}' (ID: {msg_from_id}) from channel {msg_channel_id} after 3 language warnings.")
                    if self.my_rights & UserRight.USERRIGHT_KICK_USERS:
                         try:
                             kick_cmd_id = self.doKickUser(msg_from_id, msg_channel_id)
                             if kick_cmd_id == 0:
                                 err_kick = f"Failed to send kick command for {sender_nick}."
                                 logging.error(err_kick)
                                 self._log_to_gui(f"[Error] {err_kick}")
                                 self._send_channel_message(msg_channel_id, f"[Bot Error] Failed to automatically kick {sender_nick}.")
                             else:
                                 self._send_channel_message(msg_channel_id, f"User {sender_nick} automatically kicked after 3 warnings.")
                         except Exception as e:
                              logging.error(f"Error executing kick for {sender_nick}: {e}")
                              self._log_to_gui(f"[Error] Could not kick {sender_nick}: {e}")
                    else:
                        no_kick_perm = f"Cannot automatically kick {sender_nick} (Bot lacks kick permission)."
                        logging.warning(no_kick_perm)
                        self._log_to_gui(f"[Warning] {no_kick_perm}")
                        self._send_channel_message(msg_channel_id, f"[Bot Notice] User {sender_nick} reached 3 warnings, but bot cannot kick.")

                    # Reset warnings after kick attempt or notice
                    self.warning_counts[msg_from_id] = 0

                # IMPORTANT: Stop processing this message further if a word was filtered
                return # Don't process commands or AI if filtered
        # --- End Word Filter ---


        # --- Command Processing ---
        if not process_commands:
            return # Don't process commands if not in target channel or not a PM

        # --- Split Command and Args ---
        parts = full_message_text.strip().split(maxsplit=1)
        command_word = parts[0].lower() if parts else ""
        args_str = parts[1] if len(parts) > 1 else ""

        # Handle channel specific commands (/c, /w)
        is_channel_ai_cmd = msg_type == TextMsgType.MSGTYPE_CHANNEL and command_word == "/c"
        is_channel_weather_cmd = msg_type == TextMsgType.MSGTYPE_CHANNEL and command_word == "/w"

        if is_channel_ai_cmd:
             # Override command/args for specific handling
             command_word = "/c"
             args_str = full_message_text[len("/c"):].strip() # Get args after "/c" (allows no space)
        elif is_channel_weather_cmd:
             command_word = "/w"
             args_str = full_message_text[len("/w"):].strip() # Get args after "/w"

        # Ignore empty commands (e.g., just whitespace)
        if not command_word: return

        # --- Command Blocking Check ---
        # Allow 'block'/'unblock' itself even if others are blocked for admins
        is_blocking_cmd = command_word in ["block", "unblock"] # 'unblock' is handled within 'block' logic
        is_admin_sender = self._is_admin(msg_from_id)

        if command_word in self.blocked_commands and not (is_blocking_cmd and is_admin_sender):
            log_block = f"Command '{command_word}' from {sender_nick} blocked."
            logging.info(log_block)
            # Only notify user via PM to avoid channel spam
            if msg_type == TextMsgType.MSGTYPE_USER:
                 self._send_pm(msg_from_id, f"Command '{command_word}' is currently blocked by an admin.")
            # Don't log to GUI here to avoid clutter if it's a channel message
            return

        # --- Bot Locked Check ---
        # Define commands allowed even when locked (mostly admin essentials + help/info)
        LOCKED_ALLOWED_COMMANDS = {'h', 'q', 'rs', 'block', 'unblock', 'info', 'whoami', 'rights', 'lock', '!tfilter', '!tgmmode'}
        if self.bot_locked and command_word not in LOCKED_ALLOWED_COMMANDS:
             log_lock = f"Command '{command_word}' from {sender_nick} blocked because bot is locked."
             logging.info(log_lock)
             if msg_type == TextMsgType.MSGTYPE_USER:
                  self._send_pm(msg_from_id, f"Command '{command_word}' ignored; bot is currently locked by an admin.")
             # Don't log to GUI here
             return


        # --- Process Channel-Specific Commands (/c, /w) ---
        if is_channel_ai_cmd: # command_word is "/c"
            if not self.allow_gemini_channel:
                 logging.info(f"Channel AI request ignored from '{sender_nick}' (feature disabled).")
                 # Optionally send a message back? For now, ignore quietly.
                 # self._send_channel_message(msg_channel_id, "[Bot] Channel AI feature is currently disabled.")
                 return

            if not self._gemini_enabled or self.gemini_model is None:
                logging.warning(f"Channel AI request from '{sender_nick}' but Gemini not ready/enabled.")
                self._send_channel_message(msg_channel_id, "[Bot Error] Gemini AI is not available.")
                return

            prompt = args_str # Already extracted
            log_prompt = f"Processing Channel Gemini request from '{sender_nick}': '{prompt[:100]}...'"
            logging.info(log_prompt)
            self._log_to_gui(log_prompt)

            if not prompt:
                self._send_channel_message(msg_channel_id, f"Usage: /c <your question>")
                return

            try:
                self._send_channel_message(msg_channel_id, f"[Bot] Asking Gemini for {sender_nick}...") # Feedback
                response = self.gemini_model.generate_content(prompt, stream=False, safety_settings=GEMINI_SAFETY_SETTINGS)
                gemini_reply = ""

                # Extract response text safely
                if hasattr(response, 'text'):
                     gemini_reply = response.text
                elif hasattr(response, 'parts') and response.parts:
                     gemini_reply = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                elif hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                     gemini_reply = f"[Gemini Error] Request blocked: {response.prompt_feedback.block_reason.name}"
                     logging.warning(f"Gemini request blocked: {response.prompt_feedback.block_reason.name}. Prompt: '{prompt[:100]}...'")
                else:
                     gemini_reply = "[Gemini Error] Received an empty or unexpected response."
                     logging.warning(f"Gemini returned empty/unexpected response. Object: {response}")

                # Handle potential empty string after extraction
                if not gemini_reply.strip():
                     gemini_reply = "[Gemini] (Received an empty response)"
                     logging.warning(f"Gemini returned effectively empty text for prompt: '{prompt[:100]}...'")

                reply_text = f"answering to {sender_nick}: {gemini_reply}" # Prefix with sender nick
                self._send_channel_message(msg_channel_id, reply_text) # Use _send method

            except Exception as e:
                logging.error(f"Error during Channel Gemini API call: {e}", exc_info=True)
                self._send_channel_message(msg_channel_id, f"[Bot Error] Error contacting Gemini for {sender_nick}.")

            return # Handled channel AI command

        elif is_channel_weather_cmd: # command_word is "/w"
            logging.info(f"Processing '/w' command from {sender_nick} in channel {msg_channel_id}")
            location = args_str.strip()
            if not location:
                self._send_channel_message(msg_channel_id, "Usage: /w <location>")
                return
            # Call the handler, providing channel_id for the response
            self._handle_weather_command(location, msg_channel_id, None)
            return # Handled channel weather command

        # --- Process Private Messages (Commands) ---
        elif msg_type == TextMsgType.MSGTYPE_USER:
            # (command_word and args_str already extracted)

            if command_word == "h":
                logging.info(f"Processing 'h' command from {sender_nick}")
                # ** UPDATED HELP TEXT **
                help_text = """--- Bot Commands (Send via Private Message) ---
(Commands might be blocked by admins or if the bot is locked)

General Commands:
 h                  - Show this help message.
 ping               - Check if the bot is responding ("Pong!").
 info               - Display bot status, uptime, and server info.
 whoami             - Show your nickname, UserID, and username.
 rights             - Show the permissions the bot currently has.
 cn <new_nick>      - Change the bot's nickname (this change is saved).
 cs <new_status>    - Change the bot's status message (this is saved).
 w <location>       - Get weather for a location (via PM).

Communication Commands:
 ct <message>       - Send a message to the bot's current channel.
                      (e.g., "ct Hello everyone!") (If feature enabled)
 bm <message>       - Send a broadcast message to all users on the server.
                      (Requires bot permission & feature enabled).

Poll Commands:
 !poll "Q" "A" "B"  - Create a new poll (use quotes!). Min 2 options.
 !vote <id> <num>   - Vote in a poll (e.g., !vote 1 2).
 !results <id>      - Show results for a poll.

AI Commands (if Gemini is enabled & PM feature enabled):
 c <question>       - Ask the Gemini AI a question via PM.
                      (e.g., "c What's the weather like?")

--- Admin Only Commands (via PM) ---
(You must be listed in the bot's config as an admin)

Bot Control:
 lock               - Toggle locking the bot (restricts most commands).
 block <cmd>        - Block or unblock a specific command for all users.
                      Example: block ct (Toggles block for 'ct' command)
                      Cannot block essential commands (h, q, rs, lock, block, info, !tfilter, !tgmmode).
 jc <path>[|<pass>] - Make the bot join a different channel.
 jcl                - Toggle user join/leave announcements ON/OFF.
 tg_chanmsg         - Toggle allowing bot to send channel messages ON/OFF.
 tg_broadcast       - Toggle allowing bot to send broadcasts ON/OFF.
 tg_gemini_pm       - Toggle allowing Gemini AI responses in PM ON/OFF.
 tg_gemini_chan     - Toggle allowing Gemini AI responses via /c ON/OFF.
 !tgmmode           - Toggle welcome message mode (Template vs Gemini).
 !tfilter           - Toggle the channel word filter ON/OFF globally.
 !filter <add|remove|list> [word] - Manage the channel word filter list.
 gapi <api_key>     - Set the Gemini API key and save it to config.
 rs                 - Restart the bot completely.
 q                  - Disconnect and shut down the bot.

User Management (Requires bot permissions):
 listusers [ch_path]- List users in the bot's current channel or specified path.
 listchannels       - List all channels on the server with their IDs.
 move <nick> <ch>   - Move a user (by nickname) to another channel (by path).
 kick <nick>        - Kick a user (by nickname) from the bot's current channel.
 ban <nick>         - Ban a user's account (by nickname).
 unban <username>   - Unban a user's account (by username).

--- Channel Only Commands ---
(Send in the bot's channel, not PM)
 /c <question>      - Ask Gemini AI a question (if enabled).
 /w <location>      - Get weather for a location (if enabled).
"""
                self._send_pm(msg_from_id, help_text)

            elif command_word == "ping":
                 logging.info(f"Processing 'ping' command from {sender_nick}")
                 self._send_pm(msg_from_id, "Pong!")

            elif command_word == "info":
                 logging.info(f"Processing 'info' command from {sender_nick}")
                 uptime_str = self._format_uptime(time.time() - self._start_time if self._start_time > 0 else -1)

                 # Gemini Status
                 gemini_status = "N/A"
                 if GEMINI_AVAILABLE:
                    if self._gemini_enabled and self.gemini_model:
                        g_pm = "PM:ON" if self.allow_gemini_pm else "PM:OFF"
                        g_ch = "Chan:ON" if self.allow_gemini_channel else "Chan:OFF"
                        gemini_status = f"ENABLED ({g_pm}, {g_ch})"
                    elif self.gemini_api_key:
                         gemini_status = "DISABLED (Init Failed?)"
                    else:
                         gemini_status = "DISABLED (No API Key)"
                 else:
                      gemini_status = "DISABLED (Library Missing)"

                 # Other Bot Info
                 bot_id_str = str(self._my_user_id) if self._my_user_id > 0 else "N/A"
                 bot_rights_str = f"{self.my_rights:#010x}"
                 current_chan_str = "Not in a channel"
                 if self._in_channel and self._target_channel_id > 0:
                     current_chan_str = f"{ttstr(self.target_channel_path)} (ID: {self._target_channel_id})"

                 # Server Info (with error handling)
                 server_name, server_version = "N/A", "N/A"
                 user_count_str, channel_count_str = "N/A", "N/A"
                 try:
                     if self._tt is not None:
                         server_props = self.getServerProperties()
                         if server_props:
                             server_name = ttstr(server_props.szServerName)
                             server_version = ttstr(server_props.szServerVersion)
                         users = self.getServerUsers(); user_count_str = str(len(users)) if users is not None else "Error"
                         channels = self.getServerChannels(); channel_count_str = str(len(channels)) if channels is not None else "Error"
                 except TeamTalkError as e:
                     logging.error(f"Error getting server/user/channel info: {e.errmsg}")
                     server_name, server_version = f"Error: {e.errmsg}", ""
                     user_count_str, channel_count_str = "Error", "Error"
                 except Exception as e:
                      logging.error(f"Unexpected error getting server/user/channel info: {e}")
                      server_name, server_version = "Unexpected Error", ""
                      user_count_str, channel_count_str = "Error", "Error"

                 # Feature Status
                 announce_status = "ON" if self.announce_join_leave else "OFF"
                 chan_msg_status = "ON" if self.allow_channel_messages else "OFF"
                 broadcast_status = "ON" if self.allow_broadcast else "OFF"
                 weather_status = "ON" if self._weather_enabled else "OFF"
                 lock_status = "ON" if self.bot_locked else "OFF"
                 blocked_cmds_str = ', '.join(sorted(list(self.blocked_commands))) if self.blocked_commands else 'None'
                 # Filter Status (Toggle + Word Count)
                 filter_status_toggle = "ON" if self.filter_enabled else "OFF"
                 filter_words_count = f"({len(self.filtered_words)} words)" if self.filtered_words else "(No words)"
                 filter_status = f"{filter_status_toggle} {filter_words_count}"
                 # Welcome Message Mode
                 welcome_mode_status = self.welcome_message_mode.capitalize()


                 info_lines = [
                     f"--- Bot Info ---",
                     f"Name: {ttstr(self.nickname)} ({ttstr(self.client_name)})",
                     f"Status: {ttstr(self.status_message)}",
                     f"UserID: {bot_id_str}",
                     f"Uptime: {uptime_str}",
                     f"Current Channel: {current_chan_str}",
                     f"Assigned Rights: {bot_rights_str}",
                     f"Bot Locked: {lock_status}",
                     f"Blocked Commands: {blocked_cmds_str}",
                     f"--- Features Status ---",
                     f"Channel Msgs: {chan_msg_status}",
                     f"Broadcasts: {broadcast_status}",
                     f"Join/Leave Announce: {announce_status}",
                     f"Welcome Msg Mode: {welcome_mode_status}", # Added Welcome Mode
                     f"Gemini AI: {gemini_status}",
                     f"Weather: {weather_status}",
                     f"Word Filter: {filter_status}",
                     f"--- Server Info ({ttstr(self.host)}) ---",
                     f"Name: {server_name}",
                     f"Version: {server_version}",
                     f"Users Online: {user_count_str}",
                     f"Total Channels: {channel_count_str}"
                 ]
                 self._send_pm(msg_from_id, "\n".join(info_lines))

            elif command_word == "whoami":
                logging.info(f"Processing 'whoami' command from {sender_nick}")
                if not sender_user or sender_user.nUserID != msg_from_id:
                     # Try getting user info again if initial attempt failed
                     try:
                         if self._tt is not None: sender_user = self.getUser(msg_from_id)
                     except Exception: pass # Ignore errors here

                if not sender_user or sender_user.nUserID != msg_from_id:
                    self._send_pm(msg_from_id, "Error: Could not get your user info.")
                else:
                    admin_status = "Yes" if self._is_admin(msg_from_id) else "No"
                    self._send_pm(msg_from_id, f"Nick: {sender_nick}\nID: {sender_user.nUserID}\nUser: {ttstr(sender_user.szUsername)}\nAdmin: {admin_status}")

            elif command_word == "rights":
                 logging.info(f"Processing 'rights' command from {sender_nick}")
                 rights_map = { # Using a dictionary for easier lookup
                     UserRight.USERRIGHT_MULTI_LOGIN: "Multiple Logins", UserRight.USERRIGHT_VIEW_ALL_USERS: "View All Users",
                     UserRight.USERRIGHT_CREATE_TEMPORARY_CHANNEL: "Create Temp Channels", UserRight.USERRIGHT_MODIFY_CHANNELS: "Modify Channels",
                     UserRight.USERRIGHT_TEXTMESSAGE_BROADCAST: "Send Broadcast Messages", UserRight.USERRIGHT_KICK_USERS: "Kick Users",
                     UserRight.USERRIGHT_BAN_USERS: "Ban Users", UserRight.USERRIGHT_MOVE_USERS: "Move Users",
                     UserRight.USERRIGHT_OPERATOR_ENABLE: "Become Channel Operator", UserRight.USERRIGHT_UPLOAD_FILES: "Upload Files",
                     UserRight.USERRIGHT_DOWNLOAD_FILES: "Download Files", UserRight.USERRIGHT_UPDATE_SERVERPROPERTIES: "Update Server Properties",
                     UserRight.USERRIGHT_TRANSMIT_VOICE: "Transmit Voice", UserRight.USERRIGHT_TRANSMIT_VIDEOCAPTURE: "Transmit Video Capture",
                     UserRight.USERRIGHT_TRANSMIT_DESKTOP: "Transmit Desktop", UserRight.USERRIGHT_TRANSMIT_DESKTOPINPUT: "Transmit Desktop Input",
                     UserRight.USERRIGHT_TRANSMIT_MEDIAFILE_AUDIO: "Transmit Media Audio", UserRight.USERRIGHT_TRANSMIT_MEDIAFILE_VIDEO: "Transmit Media Video",
                     UserRight.USERRIGHT_RECORD_VOICE: "Record Voice Streams", UserRight.USERRIGHT_VIEW_HIDDEN_CHANNELS: "View Hidden Channels",
                     UserRight.USERRIGHT_TEXTMESSAGE_USER: "Send Private Messages", UserRight.USERRIGHT_TEXTMESSAGE_CHANNEL: "Send Channel Messages",
                 }
                 output = [f"My Permissions ({self.my_rights:#010x}):"]
                 current_rights = self.my_rights
                 found_rights = False
                 # Sort rights by value for consistent order (optional)
                 # sorted_rights = sorted(rights_map.items(), key=lambda item: item[0])
                 # for right_flag, description in sorted_rights:
                 for right_flag, description in rights_map.items():
                     if current_rights & right_flag:
                         output.append(f"- {description}")
                         found_rights = True

                 if not found_rights: output.append("(None of the mapped rights assigned)")
                 self._send_pm(msg_from_id, "\n".join(output))

            elif command_word == "cn":
                 logging.info(f"Processing 'cn' (change nick) command from {sender_nick}")
                 if not args_str: self._send_pm(msg_from_id, "Usage: cn <new_nickname>"); return
                 new_nick = ttstr(args_str)
                 if not new_nick or len(new_nick) > TT_STRLEN:
                     self._send_pm(msg_from_id, f"Error: New nickname cannot be empty or too long (max {TT_STRLEN} bytes)."); return
                 logging.info(f"Attempting to change nickname to '{new_nick}' requested by {sender_nick}")
                 try:
                     cmd_id = self.doChangeNickname(new_nick)
                     if cmd_id == 0: self._send_pm(msg_from_id, f"Error: Failed to send nickname change command (returned 0).")
                     else: self._send_pm(msg_from_id, f"Nickname change command sent to '{new_nick}'.") # Confirmation comes via onCmdUserUpdate
                 except TeamTalkError as e:
                     logging.error(f"SDK Error changing nickname: {e.errmsg}")
                     self._send_pm(msg_from_id, f"Error changing nickname: {e.errmsg}")
                 except Exception as e:
                     logging.error(f"Unexpected error changing nickname: {e}", exc_info=True)
                     self._send_pm(msg_from_id, f"Unexpected error changing nickname.")


            elif command_word == "cs":
                 logging.info(f"Processing 'cs' (change status) command from {sender_nick}")
                 new_status_msg = ttstr(args_str) # Allow empty status
                 if len(new_status_msg) > TT_STRLEN:
                      self._send_pm(msg_from_id, f"Error: New status message too long (max {TT_STRLEN} bytes)."); return
                 status_mode = 0 # 0 usually means available/online
                 logging.info(f"Attempting to change status message to '{new_status_msg}' requested by {sender_nick}")
                 try:
                     cmd_id = self.doChangeStatus(status_mode, new_status_msg)
                     if cmd_id == 0: self._send_pm(msg_from_id, f"Error: Failed to send status change command (returned 0).")
                     else: self._send_pm(msg_from_id, f"Status change command sent.") # Confirmation via onCmdUserUpdate
                 except TeamTalkError as e:
                     logging.error(f"SDK Error changing status: {e.errmsg}")
                     self._send_pm(msg_from_id, f"Error changing status: {e.errmsg}")
                 except Exception as e:
                     logging.error(f"Unexpected error changing status: {e}", exc_info=True)
                     self._send_pm(msg_from_id, f"Unexpected error changing status.")

            elif command_word == "w": # PM Weather command
                 logging.info(f"Processing 'w' command from {sender_nick}")
                 location = args_str.strip()
                 if not location:
                    self._send_pm(msg_from_id, "Usage: w <location>")
                    return
                 # Call the handler, providing user_id for the response
                 self._handle_weather_command(location, None, msg_from_id)

            elif command_word == "ct":
                 logging.info(f"Processing 'ct' command from {sender_nick}")
                 if not self._in_channel or self._target_channel_id <= 0:
                     self._send_pm(msg_from_id, "Error: Bot is not currently in a channel.")
                 elif not args_str:
                     self._send_pm(msg_from_id, "Usage: ct <message>")
                 else:
                     # The _send method handles the rights check, feature toggle, and lock
                     success = self._send_channel_message(self._target_channel_id, f"<{sender_nick}> {args_str}")
                     if success:
                        self._send_pm(msg_from_id, "Message sent to channel.")
                     else:
                         # Provide feedback based on known failure reasons
                         if self.bot_locked: pm_feedback = "Error sending: Bot is locked."
                         elif not self.allow_channel_messages: pm_feedback = "Error sending: Channel messages are disabled by bot settings."
                         elif not (self.my_rights & UserRight.USERRIGHT_TEXTMESSAGE_CHANNEL): pm_feedback = "Error sending: Bot lacks permission to send channel messages."
                         else: pm_feedback = f"Error sending message to channel {self._target_channel_id} (check logs)."
                         self._send_pm(msg_from_id, pm_feedback)

            elif command_word == "bm":
                 logging.info(f"Processing 'bm' command from {sender_nick}")
                 if not args_str:
                    self._send_pm(msg_from_id, "Usage: bm <message>")
                 else:
                    # The _send method handles rights check, feature toggle, and lock
                    success = self._send_broadcast(ttstr(args_str))
                    if success:
                         self._send_pm(msg_from_id, "Broadcast message sent.")
                    else:
                         if self.bot_locked: pm_feedback = "Error sending: Bot is locked."
                         elif not self.allow_broadcast: pm_feedback = "Error sending: Broadcasts are disabled by bot settings."
                         elif not (self.my_rights & UserRight.USERRIGHT_TEXTMESSAGE_BROADCAST): pm_feedback = "Error sending: Bot lacks permission to send broadcast messages."
                         else: pm_feedback = "Error sending broadcast (check logs)."
                         self._send_pm(msg_from_id, pm_feedback)

            elif command_word == "c": # PM AI Command
                 logging.info(f"Processing 'c' (PM Gemini) command from {sender_nick}")
                 if not self.allow_gemini_pm: # Check feature toggle
                     logging.info(f"PM Gemini request ignored from '{sender_nick}' (feature disabled).")
                     self._send_pm(msg_from_id, "[Bot] Gemini AI (PM) responses are currently disabled.")
                     return
                 if not self._gemini_enabled or self.gemini_model is None:
                     logging.warning(f"PM Gemini request from '{sender_nick}' but Gemini not ready/enabled.")
                     self._send_pm(msg_from_id, "[Bot Error] Gemini AI is not available.")
                     return

                 prompt = args_str.strip()
                 log_prompt = f"Processing PM Gemini request from '{sender_nick}': '{prompt[:100]}...'"
                 logging.info(log_prompt)
                 self._log_to_gui(log_prompt)

                 if not prompt:
                     self._send_pm(msg_from_id, f"Usage: c <your question>")
                     return

                 try:
                     self._send_pm(msg_from_id, "[Bot] Asking Gemini...") # Give feedback
                     response = self.gemini_model.generate_content(prompt, stream=False, safety_settings=GEMINI_SAFETY_SETTINGS)
                     gemini_reply = ""

                     # Extract response text safely
                     if hasattr(response, 'text'):
                         gemini_reply = response.text
                     elif hasattr(response, 'parts') and response.parts:
                         gemini_reply = "".join(part.text for part in response.parts if hasattr(part, 'text'))
                     elif hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                         gemini_reply = f"[Gemini Error] Request blocked: {response.prompt_feedback.block_reason.name}"
                         logging.warning(f"PM Gemini request blocked: {response.prompt_feedback.block_reason.name}. Prompt: '{prompt[:100]}...'")
                     else:
                         gemini_reply = "[Gemini Error] Received an empty or unexpected response."
                         logging.warning(f"PM Gemini returned empty/unexpected response. Object: {response}")

                     # Handle potential empty string after extraction
                     if not gemini_reply.strip():
                         gemini_reply = "[Gemini] (Received an empty response)"
                         logging.warning(f"PM Gemini returned effectively empty text for prompt: '{prompt[:100]}...'")

                     reply_text = f"{gemini_reply}" # Don't prefix PMs with "[Gemini]"? Or keep it? Let's remove it.
                     self._send_pm(msg_from_id, reply_text)

                 except Exception as e:
                     logging.error(f"Error during PM Gemini API call: {e}", exc_info=True)
                     self._send_pm(msg_from_id, "[Bot Error] Error contacting Gemini.")

            # --- Poll Commands ---
            elif command_word == "!poll":
                 logging.info(f"Processing '!poll' command from {sender_nick}")
                 self._handle_poll_command(args_str, msg_from_id)

            elif command_word == "!vote":
                logging.info(f"Processing '!vote' command from {sender_nick}")
                self._handle_vote_command(args_str, msg_from_id)

            elif command_word == "!results":
                logging.info(f"Processing '!results' command from {sender_nick}")
                self._handle_results_command(args_str, msg_from_id)


            # --- Admin Only Commands ---
            # Define admin commands set for easier checking
            ADMIN_COMMANDS = {
                "!filter", "!tfilter", "lock", "block", "unblock", "jc", "jcl",
                "tg_chanmsg", "tg_broadcast", "tg_gemini_pm", "tg_gemini_chan", "!tgmmode", # Specific toggles
                "gapi", "rs", "listusers", "listchannels", "move", "kick", "ban", "unban", "q"
            }

            if command_word in ADMIN_COMMANDS:
                if not self._is_admin(msg_from_id):
                    warn_msg = f"Unauthorized admin command '{command_word}' by {sender_nick} (ID: {msg_from_id})."
                    logging.warning(warn_msg)
                    self._log_to_gui(f"[Security] {warn_msg}")
                    self._send_pm(msg_from_id, f"Error: You are not authorized to use '{command_word}'.")
                    return # Stop processing if not admin

                # --- Process Admin Commands ---
                # Wrap admin commands in try-except for robustness
                try:
                    if command_word == "!filter":
                        logging.info(f"Processing '!filter' command from admin {sender_nick}")
                        self._handle_filter_command(args_str, msg_from_id)

                    elif command_word == "!tfilter": # TOGGLE FILTER
                        logging.info(f"Processing '!tfilter' command from admin {sender_nick}")
                        self.toggle_filter() # Use internal toggle
                        new_state = "ON" if self.filter_enabled else "OFF"
                        feedback = f"Word filter is now {new_state}."
                        self._log_to_gui(f"[Admin] {feedback}")
                        self._send_pm(msg_from_id, feedback)
                        if self.main_window: wx.CallAfter(self.main_window.update_feature_list) # Update GUI

                    elif command_word == "!tgmmode": # TOGGLE WELCOME MESSAGE MODE
                         logging.info(f"Processing '!tgmmode' command from admin {sender_nick}")
                         if self.welcome_message_mode == "template":
                             # Before switching to Gemini, check if it's usable
                             if not self._gemini_enabled:
                                 self._send_pm(msg_from_id, "Error: Cannot switch to Gemini mode. Gemini AI is not available/configured.")
                             else:
                                 self.welcome_message_mode = "gemini"
                                 feedback = "Welcome message mode set to: Gemini (using AI)."
                                 self._log_to_gui(f"[Admin] {feedback}")
                                 self._send_pm(msg_from_id, feedback)
                         else: # Currently Gemini, switch to Template
                             self.welcome_message_mode = "template"
                             feedback = "Welcome message mode set to: Template (using built-in messages)."
                             self._log_to_gui(f"[Admin] {feedback}")
                             self._send_pm(msg_from_id, feedback)
                         # Note: No GUI list update for this mode currently

                    elif command_word == "lock":
                         logging.info(f"Processing 'lock' command from admin {sender_nick}")
                         self.toggle_bot_lock() # Use internal toggle
                         new_state = "ON" if self.bot_locked else "OFF"
                         feedback = f"Bot lock is now {new_state}."
                         self._log_to_gui(f"[Admin] {feedback}")
                         self._send_pm(msg_from_id, feedback)
                         if self.main_window: wx.CallAfter(self.main_window.update_feature_list) # Update GUI

                    elif command_word in ["block", "unblock"]: # COMMAND BLOCKING
                         logging.info(f"Processing '{command_word}' command from admin {sender_nick}")
                         cmd_to_toggle = args_str.strip().lower()
                         if not cmd_to_toggle:
                             self._send_pm(msg_from_id, "Usage: block <command_to_toggle>")
                             blocked_cmds_str = ', '.join(sorted(list(self.blocked_commands))) if self.blocked_commands else 'None'
                             self._send_pm(msg_from_id, f"Currently blocked: {blocked_cmds_str}")
                             return

                         if cmd_to_toggle in self.UNBLOCKABLE_COMMANDS:
                             self._send_pm(msg_from_id, f"Error: Command '{cmd_to_toggle}' cannot be blocked.")
                             return
                         # Optional: Check if cmd_to_toggle is a known command?

                         feedback = ""
                         if cmd_to_toggle in self.blocked_commands:
                             self.blocked_commands.remove(cmd_to_toggle)
                             feedback = f"Command '{cmd_to_toggle}' has been UNBLOCKED."
                             logging.info(f"Admin {sender_nick} unblocked command '{cmd_to_toggle}'.")
                         else:
                             self.blocked_commands.add(cmd_to_toggle)
                             feedback = f"Command '{cmd_to_toggle}' has been BLOCKED."
                             logging.info(f"Admin {sender_nick} blocked command '{cmd_to_toggle}'.")

                         self._log_to_gui(f"[Admin] {feedback}")
                         self._send_pm(msg_from_id, feedback)


                    elif command_word == "jc": # JOIN CHANNEL
                         logging.info(f"Processing 'jc' (join channel) command from admin {sender_nick}")
                         if not args_str: self._send_pm(msg_from_id, "Usage: jc <channel_path>[|optional_password]"); return
                         jc_parts = args_str.split('|', 1)
                         target_jc_path = ttstr(jc_parts[0].strip())
                         target_jc_pass = ttstr(jc_parts[1]) if len(jc_parts) > 1 else ttstr("")
                         if not target_jc_path: self._send_pm(msg_from_id, "Error: Channel path cannot be empty."); return

                         target_jc_id = self.getChannelIDFromPath(target_jc_path)
                         if target_jc_id <= 0: self._send_pm(msg_from_id, f"Error: Channel '{target_jc_path}' not found."); return

                         # Update internal targets before attempting join
                         self.target_channel_path = target_jc_path
                         self.channel_password = target_jc_pass
                         self._target_channel_id = target_jc_id # Store intended target

                         log_jc = f"Admin {sender_nick} requested bot join '{target_jc_path}' (ID: {target_jc_id})"
                         logging.info(log_jc); self._log_to_gui(f"[Admin] {log_jc}")

                         self._join_cmd_id = self.doJoinChannelByID(target_jc_id, target_jc_pass)
                         if self._join_cmd_id == 0:
                              self._send_pm(msg_from_id, f"Error: Failed to send join command for '{target_jc_path}'.")
                              # Reset target_id if send failed immediately? Maybe not, wait for onCmdError.
                         else:
                              self._send_pm(msg_from_id, f"Join command sent for '{target_jc_path}'.")


                    elif command_word == "jcl": # TOGGLE JOIN/LEAVE ANNOUNCE
                         logging.info(f"Processing 'jcl' (toggle announce) command from admin {sender_nick}")
                         self.toggle_announce_join_leave() # Call internal toggle
                         new_state = "ON" if self.announce_join_leave else "OFF"
                         feedback = f"Channel join/leave announcements are now {new_state}."
                         self._log_to_gui(f"[Admin] {feedback}")
                         self._send_pm(msg_from_id, feedback)
                         if self.main_window: wx.CallAfter(self.main_window.update_feature_list) # Update GUI

                    # --- Specific Feature Toggles ---
                    elif command_word == "tg_chanmsg":
                         self.toggle_allow_channel_messages()
                         state = "ON" if self.allow_channel_messages else "OFF"
                         self._send_pm(msg_from_id, f"Allow Channel Messages toggled {state}.")
                         if self.main_window: wx.CallAfter(self.main_window.update_feature_list)
                    elif command_word == "tg_broadcast":
                        self.toggle_allow_broadcast()
                        state = "ON" if self.allow_broadcast else "OFF"
                        self._send_pm(msg_from_id, f"Allow Broadcast Messages toggled {state}.")
                        if self.main_window: wx.CallAfter(self.main_window.update_feature_list)
                    elif command_word == "tg_gemini_pm":
                        self.toggle_allow_gemini_pm()
                        state = "ON" if self.allow_gemini_pm else "OFF"
                        self._send_pm(msg_from_id, f"Allow Gemini (PM) toggled {state}.")
                        if self.main_window: wx.CallAfter(self.main_window.update_feature_list)
                    elif command_word == "tg_gemini_chan":
                        self.toggle_allow_gemini_channel()
                        state = "ON" if self.allow_gemini_channel else "OFF"
                        self._send_pm(msg_from_id, f"Allow Gemini (Channel /c) toggled {state}.")
                        if self.main_window: wx.CallAfter(self.main_window.update_feature_list)
                    # --- End Specific Feature Toggles ---


                    elif command_word == "gapi": # SET GEMINI API KEY
                         logging.info(f"Processing 'gapi' (set API key) command from admin {sender_nick}")
                         if not GEMINI_AVAILABLE: self._send_pm(msg_from_id, "Error: Cannot set API key, google-generativeai library not found."); return
                         if not args_str: self._send_pm(msg_from_id, "Usage: gapi <your_gemini_api_key>"); return
                         new_api_key = args_str.strip()
                         self.gemini_api_key = new_api_key
                         log_gapi = f"Admin {sender_nick} setting new Gemini API key."; logging.info(log_gapi); self._log_to_gui(f"[Admin] {log_gapi}")
                         if self._init_gemini(new_api_key):
                              # If init succeeds, potentially re-enable features if they were off due to no key
                              self.allow_gemini_pm = True # Reset toggle state on successful key init
                              self.allow_gemini_channel = True
                              feedback = "Gemini API key updated and initialized successfully. Features re-enabled."
                              self._save_runtime_config(save_gemini_key=True) # Save the new key
                         else:
                              feedback = "Gemini API key updated, but failed to initialize Gemini model. Check the key and logs. Features remain disabled."
                              self._save_runtime_config(save_gemini_key=True) # Save key even if init fails
                         self._send_pm(msg_from_id, feedback)
                         if self.main_window: wx.CallAfter(self.main_window.update_feature_list) # Update GUI


                    elif command_word == "rs": # RESTART COMMAND
                        log_rs = f"Restart requested by admin {sender_nick}. Initiating..."
                        logging.info(log_rs); self._log_to_gui(f"[Admin] {log_rs}")
                        self._send_pm(msg_from_id, "Acknowledged. Restarting bot...")
                        self._mark_stopped_intentionally()
                        # Schedule the restart on the main wx thread
                        wx.CallAfter(self._initiate_restart)


                    elif command_word == "listusers":
                         logging.info(f"Processing 'listusers' command from admin {sender_nick}")
                         target_list_channel_id = -1; channel_path_str = "Current Channel"
                         if args_str: # User specified a channel path
                             channel_path_str = args_str.strip()
                             target_list_channel_id = self.getChannelIDFromPath(ttstr(channel_path_str))
                             if target_list_channel_id <= 0: self._send_pm(msg_from_id, f"Error: Channel '{channel_path_str}' not found."); return
                         elif self._in_channel and self._target_channel_id > 0: # Use bot's current channel
                             target_list_channel_id = self._target_channel_id
                             channel_path_str = ttstr(self.target_channel_path)
                         else: # Bot not in a channel and none specified
                             self._send_pm(msg_from_id, "Error: Bot not in a channel. Specify path (e.g., listusers /)."); return

                         users = self.getChannelUsers(target_list_channel_id)
                         user_list = [f"Users in '{channel_path_str}' (ID: {target_list_channel_id}):"]
                         if not users:
                              user_list.append(" (No users found)")
                         else:
                             # Sort users by nickname (case-insensitive)
                             users_list = list(users) # Convert generator/sequence to list for sorting
                             users_list.sort(key=lambda u: ttstr(u.szNickname).lower() if u and u.szNickname else "")
                             for user in users_list:
                                  if user and user.nUserID > 0:
                                      nick = ttstr(user.szNickname) if user.szNickname else f"ID_{user.nUserID}"
                                      user_list.append(f"- {nick} (ID: {user.nUserID}, User: {ttstr(user.szUsername)})")
                         self._send_pm(msg_from_id, "\n".join(user_list))


                    elif command_word == "listchannels":
                         logging.info(f"Processing 'listchannels' command from admin {sender_nick}")
                         channels = self.getServerChannels()
                         channel_list = ["--- Server Channels ---"]
                         if not channels:
                              channel_list.append("(No channels found or error retrieving list)")
                         else:
                             channel_data = []
                             # Channels might be a sequence, convert to list first
                             channels_list = list(channels)
                             for chan in channels_list:
                                 if not chan or chan.nChannelID <= 0: continue
                                 try: path = ttstr(self.getChannelPath(chan.nChannelID))
                                 except Exception: path = f"(Error getting path for ID {chan.nChannelID})"
                                 channel_data.append({'path': path, 'id': chan.nChannelID})
                             # Sort channels by path (case-insensitive)
                             channel_data.sort(key=lambda x: x['path'].lower())
                             for chan_info in channel_data:
                                 channel_list.append(f"- {chan_info['path']} (ID: {chan_info['id']})")
                         self._send_pm(msg_from_id, "\n".join(channel_list))


                    elif command_word == "move":
                        logging.info(f"Processing 'move' command from admin {sender_nick}")
                        if not (self.my_rights & UserRight.USERRIGHT_MOVE_USERS): self._send_pm(msg_from_id, "Error: Bot lacks permission to move users."); return
                        move_parts = args_str.split(maxsplit=1)
                        if len(move_parts) < 2: self._send_pm(msg_from_id, "Usage: move <nickname> <target_channel_path>"); return
                        target_nick, target_channel_path_move = move_parts[0], move_parts[1].strip()

                        user_to_move = self._find_user_by_nick(target_nick)
                        if user_to_move is None or user_to_move.nUserID <= 0: self._send_pm(msg_from_id, f"Error: User '{target_nick}' not found online."); return
                        if user_to_move.nUserID == self._my_user_id: self._send_pm(msg_from_id, "Error: Cannot move myself."); return

                        target_move_channel_id = self.getChannelIDFromPath(ttstr(target_channel_path_move))
                        if target_move_channel_id <= 0: self._send_pm(msg_from_id, f"Error: Target channel '{target_channel_path_move}' not found."); return
                        if user_to_move.nChannelID == target_move_channel_id: self._send_pm(msg_from_id, f"Error: User '{target_nick}' is already in '{target_channel_path_move}'."); return

                        log_move = f"Attempting move of {target_nick} (ID: {user_to_move.nUserID}) to {target_channel_path_move} (ID: {target_move_channel_id}) by {sender_nick}"
                        logging.info(log_move); self._log_to_gui(f"[Admin] {log_move}")
                        cmd_id = self.doMoveUser(user_to_move.nUserID, target_move_channel_id)
                        if cmd_id == 0: self._send_pm(msg_from_id, f"Error sending move command for '{target_nick}'.")
                        else: self._send_pm(msg_from_id, f"Move command sent for '{target_nick}' to '{target_channel_path_move}'.")


                    elif command_word == "kick":
                        logging.info(f"Processing 'kick' command from admin {sender_nick}")
                        if not (self.my_rights & UserRight.USERRIGHT_KICK_USERS): self._send_pm(msg_from_id, "Error: Bot lacks permission to kick users."); return
                        if not self._in_channel or self._target_channel_id <= 0: self._send_pm(msg_from_id, "Error: Bot not in a channel to kick from."); return
                        if not args_str: self._send_pm(msg_from_id, "Usage: kick <nickname>"); return

                        target_nick_kick = args_str.strip(); target_user_kick_id = -1
                        # Find user specifically in the bot's current channel
                        channel_users = self.getChannelUsers(self._target_channel_id)
                        if channel_users:
                            channel_users_list = list(channel_users) # Convert to list
                            for user in channel_users_list:
                                if user and user.nUserID > 0 and ttstr(user.szNickname).lower() == target_nick_kick.lower():
                                    target_user_kick_id = user.nUserID
                                    break

                        if target_user_kick_id == -1:
                             self._send_pm(msg_from_id, f"Error: User '{target_nick_kick}' not found in bot's current channel ('{ttstr(self.target_channel_path)}').")
                        elif target_user_kick_id == self._my_user_id:
                             self._send_pm(msg_from_id, "Error: Cannot kick myself.")
                        else:
                             log_kick = f"Attempting kick of {target_nick_kick} (ID: {target_user_kick_id}) from {self._target_channel_id} by {sender_nick}"
                             logging.info(log_kick); self._log_to_gui(f"[Admin] {log_kick}")
                             cmd_id = self.doKickUser(target_user_kick_id, self._target_channel_id)
                             if cmd_id == 0: self._send_pm(msg_from_id, f"Error sending kick command for '{target_nick_kick}'.")
                             else: self._send_pm(msg_from_id, f"Kick command sent for '{target_nick_kick}'.")


                    elif command_word == "ban":
                        logging.info(f"Processing 'ban' command from admin {sender_nick}")
                        if not (self.my_rights & UserRight.USERRIGHT_BAN_USERS): self._send_pm(msg_from_id, "Error: Bot lacks permission to ban users."); return
                        if not args_str: self._send_pm(msg_from_id, "Usage: ban <nickname>"); return

                        target_nick_ban = args_str.strip(); user_to_ban = self._find_user_by_nick(target_nick_ban)
                        if user_to_ban is None or user_to_ban.nUserID <= 0 : self._send_pm(msg_from_id, f"Error: User '{target_nick_ban}' not found online."); return
                        if user_to_ban.nUserID == self._my_user_id: self._send_pm(msg_from_id, "Error: Cannot ban myself."); return

                        ban_username = ttstr(user_to_ban.szUsername)
                        if not ban_username: self._send_pm(msg_from_id, f"Error: Cannot ban '{target_nick_ban}', user account name is empty."); return

                        log_ban = f"Attempting account ban (Username: {ban_username}) of {target_nick_ban} (ID: {user_to_ban.nUserID}) by {sender_nick}"
                        logging.info(log_ban); self._log_to_gui(f"[Admin] {log_ban}")
                        # Ban by Username is generally more reliable than UserID if the user can relog
                        cmd_id = self.doBanUserEx(user_to_ban.nUserID, BanType.BANTYPE_USERNAME)
                        if cmd_id == 0: self._send_pm(msg_from_id, f"Error sending ban command for '{target_nick_ban}'.")
                        else: self._send_pm(msg_from_id, f"Account ban command sent for '{target_nick_ban}' (Username: '{ban_username}').")


                    elif command_word == "unban":
                        logging.info(f"Processing 'unban' command from admin {sender_nick}")
                        if not (self.my_rights & UserRight.USERRIGHT_BAN_USERS): self._send_pm(msg_from_id, "Error: Bot lacks permission to unban users."); return
                        if not args_str: self._send_pm(msg_from_id, "Usage: unban <username>"); return

                        target_username_unban = ttstr(args_str.strip())
                        # Create a BannedUser structure to pass to unban
                        ban_entry = BannedUser();
                        ban_entry.szUsername = target_username_unban;
                        ban_entry.uBanTypes = BanType.BANTYPE_USERNAME # Specify we are unbanning by username

                        log_unban = f"Attempting to unban username '{target_username_unban}' by {sender_nick}"
                        logging.info(log_unban); self._log_to_gui(f"[Admin] {log_unban}")
                        cmd_id = self.doUnBanUserEx(ban_entry)
                        if cmd_id == 0: self._send_pm(msg_from_id, f"Error sending unban command for '{target_username_unban}'.")
                        else: self._send_pm(msg_from_id, f"Unban command sent for username '{target_username_unban}'.")


                    elif command_word == "q": # QUIT
                        log_q = f"Quit requested by admin {sender_nick}. Stopping bot."
                        logging.info(log_q); self._log_to_gui(f"[Admin] {log_q}")
                        self._send_pm(msg_from_id, "Acknowledged. Quitting...")
                        self._mark_stopped_intentionally()
                        # Don't call stop() directly from event handler, schedule it
                        wx.CallAfter(self.stop)

                except TeamTalkError as e:
                     admin_cmd_err = f"SDK Error processing admin command '{command_word}': {e.errmsg}"
                     logging.error(admin_cmd_err)
                     self._log_to_gui(f"[Admin Error] {admin_cmd_err}")
                     self._send_pm(msg_from_id, f"Error executing command: {e.errmsg}")
                except Exception as e:
                     admin_cmd_err = f"Unexpected error processing admin command '{command_word}': {e}"
                     logging.error(admin_cmd_err, exc_info=True)
                     self._log_to_gui(f"[Admin Error] {admin_cmd_err}")
                     self._send_pm(msg_from_id, f"An unexpected error occurred executing '{command_word}'.")



    # --- Restart Logic ---
    def _initiate_restart(self):
        """Handles the restart process. MUST run on the main GUI thread."""
        global bot_thread, bot_instance_ref, final_config_data, main_gui_window

        log_msg = "--- BOT RESTART SEQUENCE INITIATED (Main Thread) ---"
        logging.info(log_msg)
        if main_gui_window: main_gui_window.log_message(log_msg)

        current_bot = bot_instance_ref[0]
        if current_bot is not None:
            logging.info("Restart: Stopping current bot instance...")
            if main_gui_window: main_gui_window.log_message("Restart: Stopping current bot...")
            # Ensure intentional stop flag is set before calling stop
            current_bot._mark_stopped_intentionally()
            current_bot.stop() # This should trigger cleanup and thread exit

            # Wait for the thread to finish
            if bot_thread and bot_thread.is_alive():
                logging.info("Restart: Waiting for current bot thread to terminate...")
                if main_gui_window: main_gui_window.log_message("Restart: Waiting for current bot thread...")
                bot_thread.join(timeout=10.0) # Wait up to 10 seconds
                if bot_thread.is_alive():
                    log_err = "Restart Error: Current bot thread did not terminate after stop! Aborting restart."
                    logging.error(log_err)
                    if main_gui_window: main_gui_window.log_message(f"[Error] {log_err}")
                    # Consider forceful exit or just aborting restart
                    return
                else:
                    logging.info("Restart: Current bot thread terminated.")
                    if main_gui_window: main_gui_window.log_message("Restart: Old bot thread finished.")
            else:
                logging.info("Restart: Current bot thread was already finished or None.")
            bot_instance_ref[0] = None # Clear the reference
        else:
            logging.warning("Restart: No current bot instance found to stop.")

        # --- Start New Bot ---
        logging.info("Restart: Starting new bot session...")
        if main_gui_window: main_gui_window.log_message("Restart: Starting new bot session...")

        # Ensure config data is still valid
        if not final_config_data:
             log_err = "Restart Error: Global configuration data is missing! Cannot start new bot."
             logging.critical(log_err)
             if main_gui_window: main_gui_window.log_message(f"[CRITICAL] {log_err}")
             return

        try:
            # Call the function that starts the bot thread
            start_new_bot_session(final_config_data)
            log_msg = "--- BOT RESTART SEQUENCE COMPLETED ---"
            logging.info(log_msg)
            if main_gui_window: main_gui_window.log_message(log_msg)
        except Exception as e:
             log_err = f"Restart Error: Failed to start new bot session: {e}"
             logging.critical(log_err, exc_info=True)
             if main_gui_window: main_gui_window.log_message(f"[CRITICAL] {log_err}")


    def onInternalError(self, clienterrormsg: ClientErrorMsg):
         error_no = clienterrormsg.nErrorNo
         error_msg = ttstr(clienterrormsg.szErrorMsg) if clienterrormsg.szErrorMsg else "Unknown internal error"
         log_msg = f"Internal SDK Error: {error_no} - {error_msg}"
         logging.critical(log_msg); self._log_to_gui(f"[SDK CRITICAL] {log_msg}")
         # Treat internal errors as fatal, stop the bot
         self._mark_stopped_intentionally() # Prevent automatic restart attempts
         self._running = False # Signal event loop to stop
         # Don't call self.stop() here, let the loop exit naturally and call stop() in finally block


    # --- Stubs for Other Events ---
    def onCmdUserUpdate(self, user: User):
        if user and user.nUserID > 0:
             # Log user updates less verbosely unless it's our own user
             if user.nUserID == self._my_user_id:
                 nickname_changed = False; status_changed = False
                 current_server_nick = ttstr(user.szNickname); current_server_status = ttstr(user.szStatusMsg)

                 # Check if nickname actually changed
                 if current_server_nick != self.nickname:
                      old_nick = self.nickname; self.nickname = current_server_nick; nickname_changed = True
                      nick_change_msg = f"My nickname changed from '{old_nick}' to '{self.nickname}' (Server confirmed)"
                      logging.info(nick_change_msg); self._log_to_gui(nick_change_msg)
                      if self.main_window: wx.CallAfter(self.main_window.SetTitle, f"TeamTalk Bot - {self.nickname} @ {ttstr(self.host)}")

                 # Check if status message actually changed
                 if current_server_status != self.status_message:
                     old_status = self.status_message; self.status_message = current_server_status; status_changed = True
                     status_change_msg = f"My status message changed (Server confirmed): '{self.status_message}'"
                     logging.info(status_change_msg); self._log_to_gui(status_change_msg)

                 # Save config if relevant details changed
                 if nickname_changed or status_changed:
                     self._save_runtime_config(save_gemini_key=False)
             else:
                 # Log other user updates at debug level
                 log_msg = f"User Update: Nick={ttstr(user.szNickname)}, ID={user.nUserID}, State={user.uUserState:#x}, Status='{ttstr(user.szStatusMsg)}'"
                 logging.debug(log_msg)


    def onCmdChannelNew(self, channel: Channel):
        if channel and channel.nChannelID > 0:
            # Get channel path safely
            path_str = f"ID {channel.nChannelID}"
            try:
                 if self._tt is not None: path_str = ttstr(self.getChannelPath(channel.nChannelID))
            except Exception: pass # Ignore errors getting path here
            log_msg = f"New Channel: {ttstr(channel.szName)} ({path_str})"
            logging.info(log_msg); self._log_to_gui(log_msg)

    def onCmdChannelUpdate(self, channel: Channel):
         if channel and channel.nChannelID > 0:
             path_str = f"ID {channel.nChannelID}"
             try:
                  if self._tt is not None: path_str = ttstr(self.getChannelPath(channel.nChannelID))
             except Exception: pass
             log_msg = f"Channel Update: {ttstr(channel.szName)} ({path_str})"
             logging.info(log_msg); self._log_to_gui(log_msg)

    def onCmdChannelRemove(self, channel: Channel):
         if channel and channel.nChannelID > 0:
            # Use channel name from the event data as path might be invalid now
            log_msg = f"Channel Removed: {ttstr(channel.szName)} (ID: {channel.nChannelID})"
            logging.info(log_msg); self._log_to_gui(log_msg)
            # Check if the removed channel was our target channel
            if self._target_channel_id == channel.nChannelID:
                 warn_msg = f"My current channel (ID: {self._target_channel_id}) was removed!"
                 logging.warning(warn_msg); self._log_to_gui(warn_msg)
                 self._in_channel = False; self._target_channel_id = -1; self.target_channel_path = ttstr("")
                 # Attempt to rejoin Root channel
                 try:
                      if self._tt is not None:
                          root_id = self.getRootChannelID()
                          if root_id > 0:
                               logging.info("Current channel removed, attempting to rejoin Root...")
                               self._log_to_gui("Current channel removed, trying to join Root...")
                               self._join_cmd_id = self.doJoinChannelByID(root_id, "")
                               if self._join_cmd_id == 0: self._log_to_gui("[Error] Failed to send command to rejoin Root.")
                               else:
                                    # Update target path/id optimistically
                                    self.target_channel_path = ttstr("/")
                                    self._target_channel_id = root_id
                          else:
                               logging.error("Could not get Root ID after channel removal.")
                               self._log_to_gui("[Error] Could not find Root to rejoin.")
                 except TeamTalkError as e:
                      logging.error(f"Error trying to rejoin root after channel removal: {e.errmsg}"); self._log_to_gui(f"[Error] Could not rejoin Root: {e.errmsg}")
                 except Exception as e:
                      logging.error(f"Unexpected error rejoining root: {e}", exc_info=True); self._log_to_gui(f"[Error] Unexpected error rejoining Root.")

    def onUserStateChange(self, user: User):
         # This event fires frequently (speaking, etc.), log at debug level
         if user and user.nUserID > 0:
              log_msg = f"User State Change: Nick={ttstr(user.szNickname)}, ID={user.nUserID}, State={user.uUserState:#x}"
              logging.debug(log_msg)

    # --- Feature Toggle Methods (Called by GUI/Commands) ---
    def toggle_announce_join_leave(self):
        self.announce_join_leave = not self.announce_join_leave
        feedback = f"Join/Leave Announce toggled {'ON' if self.announce_join_leave else 'OFF'}"
        logging.info(feedback)
        self._log_to_gui(f"[Toggle] {feedback}")
        # No config save needed for toggles unless desired

    def toggle_allow_channel_messages(self):
        # Check rights before enabling
        if not self.allow_channel_messages and not (self.my_rights & UserRight.USERRIGHT_TEXTMESSAGE_CHANNEL):
             msg = "Cannot enable Channel Messages: Bot lacks permission (USERRIGHT_TEXTMESSAGE_CHANNEL)."
             self._log_to_gui(f"[Warning] {msg}")
             logging.warning(msg)
             return # Prevent enabling without rights
        self.allow_channel_messages = not self.allow_channel_messages
        feedback = f"Allow Channel Messages toggled {'ON' if self.allow_channel_messages else 'OFF'}"
        logging.info(feedback)
        self._log_to_gui(f"[Toggle] {feedback}")

    def toggle_allow_broadcast(self):
        # Check rights before enabling
        if not self.allow_broadcast and not (self.my_rights & UserRight.USERRIGHT_TEXTMESSAGE_BROADCAST):
             msg = "Cannot enable Broadcasts: Bot lacks permission (USERRIGHT_TEXTMESSAGE_BROADCAST)."
             self._log_to_gui(f"[Warning] {msg}")
             logging.warning(msg)
             return
        self.allow_broadcast = not self.allow_broadcast
        feedback = f"Allow Broadcasts toggled {'ON' if self.allow_broadcast else 'OFF'}"
        logging.info(feedback)
        self._log_to_gui(f"[Toggle] {feedback}")

    def toggle_allow_gemini_pm(self):
        # Check if Gemini itself is ready before enabling
        if not self.allow_gemini_pm and not self._gemini_enabled:
             msg = "Cannot enable Gemini PM: Gemini AI is not available/initialized (check API key/library)."
             self._log_to_gui(f"[Warning] {msg}")
             logging.warning(msg)
             return
        self.allow_gemini_pm = not self.allow_gemini_pm
        feedback = f"Allow Gemini AI (PM) toggled {'ON' if self.allow_gemini_pm else 'OFF'}"
        logging.info(feedback)
        self._log_to_gui(f"[Toggle] {feedback}")

    def toggle_allow_gemini_channel(self):
        # Check if Gemini itself is ready before enabling
        if not self.allow_gemini_channel and not self._gemini_enabled:
             msg = "Cannot enable Gemini Channel (/c): Gemini AI is not available/initialized."
             self._log_to_gui(f"[Warning] {msg}")
             logging.warning(msg)
             return
        self.allow_gemini_channel = not self.allow_gemini_channel
        feedback = f"Allow Gemini AI (Channel /c) toggled {'ON' if self.allow_gemini_channel else 'OFF'}"
        logging.info(feedback)
        self._log_to_gui(f"[Toggle] {feedback}")

    def toggle_bot_lock(self):
        """Toggles the bot lock state."""
        self.bot_locked = not self.bot_locked
        feedback = f"Bot Lock toggled {'ON' if self.bot_locked else 'OFF'}"
        logging.info(feedback)
        self._log_to_gui(f"[Toggle] {feedback}")

    def toggle_filter(self):
        """Toggles the word filter state."""
        # Prevent enabling if there are no words defined
        if not self.filter_enabled and not self.filtered_words:
            msg = "Cannot enable filter: No words are defined in the filter list (!filter add <word>)."
            self._log_to_gui(f"[Warning] {msg}")
            logging.warning(msg)
            return
        self.filter_enabled = not self.filter_enabled
        feedback = f"Word Filter toggled {'ON' if self.filter_enabled else 'OFF'}"
        logging.info(feedback)
        self._log_to_gui(f"[Toggle] {feedback}")

    # --- Add more event handler stubs as needed ---
    # def onCmdFileNew(self, remotefile: RemoteFile): pass
    # def onCmdFileRemove(self, remotefile: RemoteFile): pass
    # def onUserRecordMediaFile(self, userid: int, mediafileinfo: MediaFileInfo): pass
    # def onUserAccountNew(self, useraccount: UserAccount): pass
    # def onUserAccountRemove(self, useraccount: UserAccount): pass
    # def onUserAudioBlock(self, nUserID: int, nStreamType: StreamType): pass
    # def onStreamMediaFile(self, mediafileinfo: MediaFileInfo): pass
    # def onUserAccount(self, useraccount: UserAccount): pass
    # def onBannedUser(self, banneduser: BannedUser): pass
    # def onServerStatistics(self, serverstatistics: ServerStatistics): pass
    # def onSoundDeviceAdded(self, sounddevice: SoundDevice): pass
    # def onSoundDeviceRemoved(self, sounddevice: SoundDevice): pass
    # def onSoundDeviceUnplugged(self, sounddevice: SoundDevice): pass
    # def onSoundDeviceNewDefaultInput(self, sounddevice: SoundDevice): pass
    # def onSoundDeviceNewDefaultOutput(self, sounddevice: SoundDevice): pass
    # def onSoundDeviceNewDefaultInputComDevice(self, sounddevice: SoundDevice): pass
    # def onSoundDeviceNewDefaultOutputComDevice(self, sounddevice: SoundDevice): pass


# --- Global Variables ---
bot_instance_ref = [None] # Use a mutable list to hold the bot instance reference
main_gui_window = None
bot_thread = None
app_instance = None # wx.App instance
final_config_data = None # Holds the final structured configuration

# --- Signal Handler ---
def signal_handler(sig, frame):
    """Gracefully handle termination signals (SIGINT, SIGTERM)."""
    global bot_instance_ref, main_gui_window, app_instance
    print(' ') # Newline for cleaner console output
    try:
        signal_name = signal.Signals(sig).name
    except ValueError:
        signal_name = f'Signal {sig}'
    log_msg = f"Signal {signal_name} ({sig}) received, initiating shutdown..."
    logging.info(log_msg); print(log_msg) # Log to file and console

    # 1. Signal the bot thread to stop
    current_bot = bot_instance_ref[0]
    if current_bot is not None:
        if hasattr(current_bot, 'stop') and callable(current_bot.stop):
            print("Calling bot_instance.stop()...")
            current_bot._mark_stopped_intentionally() # Ensure it doesn't try to reconnect
            # Stop might take time, don't block signal handler excessively.
            # Let the main thread join handle waiting.
            # Schedule stop on main thread if possible? Maybe not necessary if stop is thread-safe.
            current_bot.stop()
        else:
            print("Bot instance found, but stop() method missing/not callable!")
    else:
        print("No active bot instance found.")

    # 2. Signal the GUI to close (must run on the main GUI thread)
    if main_gui_window is not None:
         if hasattr(main_gui_window, 'Close') and callable(main_gui_window.Close):
             print("Scheduling main_gui_window.Close()...")
             wx.CallAfter(main_gui_window.Close, True) # True forces close even if vetoed
         else:
              print("Main GUI window found, but Close method missing/not callable!")
    elif app_instance:
        # If no main window, try exiting the app instance directly
        print("Scheduling app_instance.ExitMainLoop()...")
        wx.CallAfter(app_instance.ExitMainLoop)

    print("Signal handler finished scheduling shutdown.")
    # Don't call sys.exit here, let the main loop terminate gracefully

# --- Bot Thread Function ---
def start_bot_thread(config_data_arg):
    """Function executed in the separate bot thread."""
    global bot_instance_ref, main_gui_window
    bot_instance_ref[0] = None # Clear previous instance if any
    try:
        logging.info("Bot thread started.")
        new_bot_instance = MyTeamTalkBot(config_data_arg)
        bot_instance_ref[0] = new_bot_instance # Store the reference

        # Check if SDK initialized correctly within the bot's __init__
        # The TeamTalk5 wrapper might not have _tt until connect is called.
        # We rely on the bot's start() method to handle connection errors.

        if main_gui_window:
            new_bot_instance.set_main_window(main_gui_window)
            logging.info("Bot linked with main GUI window.")
        else:
            logging.error("Main GUI window reference is missing when bot started!")

        # Start the bot's main connection and event loop
        new_bot_instance.start()

    except TeamTalkError as e:
        # Catch errors during bot initialization (e.g., SDK loading)
        logging.critical(f"Bot thread failed during init (SDK Error): {e.errnum} - {e.errmsg}")
        if main_gui_window: wx.CallAfter(main_gui_window.log_message, f"[CRITICAL] SDK Init Error: {e.errmsg}")
        bot_instance_ref[0] = None # Ensure ref is cleared on error
    except Exception as e:
        logging.critical(f"Bot thread failed with unhandled exception during init/start: {e}", exc_info=True)
        if main_gui_window: wx.CallAfter(main_gui_window.log_message, f"[CRITICAL] Unexpected Bot Thread Error: {e}")
        bot_instance_ref[0] = None # Ensure ref is cleared on error
    finally:
        # This block runs when the bot's start() method returns (normally or due to error)
        log_thread_end = "Bot thread finished execution."
        logging.info(log_thread_end)
        if main_gui_window: wx.CallAfter(main_gui_window.log_message, log_thread_end)
        # Ensure the reference is cleared if the thread stops unexpectedly
        bot_instance_ref[0] = None

# --- Helper to Start a Bot Session ---
def start_new_bot_session(config_to_use):
    """Creates and starts a new bot thread."""
    global bot_thread
    # Ensure previous thread is not running (should be joined by restart logic)
    if bot_thread and bot_thread.is_alive():
         logging.warning("Attempting to start new bot session while previous thread is still alive!")
         # Optionally wait for it again? Or just log and continue?
         bot_thread.join(timeout=2.0)
         if bot_thread.is_alive():
             logging.error("Previous bot thread did not exit before starting new one!")

    bot_thread = threading.Thread(target=start_bot_thread, args=(config_to_use,), daemon=True)
    bot_thread.start()
    logging.info(f"New bot thread started (ID: {bot_thread.ident}).")
    if main_gui_window: main_gui_window.log_message("New bot thread started.")

# --- Main Execution ---
if __name__ == "__main__":
    # Initialize wxPython App early
    app_instance = wx.App(False)

    # --- Configuration Loading/Setup ---
    loaded_config_parser = load_config()
    if loaded_config_parser:
        final_config_data = {}
        # Convert loaded configparser object to the nested dictionary structure
        try:
            # Connection Section
            if loaded_config_parser.has_section('Connection'):
                 final_config_data['Connection'] = dict(loaded_config_parser.items('Connection'))
                 # Convert port to int
                 port_str = final_config_data['Connection'].get('port', DEFAULT_CONFIG['Connection']['port'])
                 final_config_data['Connection']['port'] = int(port_str)
            else:
                 # Use defaults if section missing (though load_config should have caught this)
                 final_config_data['Connection'] = DEFAULT_CONFIG['Connection'].copy()
                 final_config_data['Connection']['port'] = int(final_config_data['Connection']['port'])

            # Bot Section
            if loaded_config_parser.has_section('Bot'):
                final_config_data['Bot'] = dict(loaded_config_parser.items('Bot'))
                # Convert reconnect delays to int
                try: final_config_data['Bot']['reconnect_delay_min'] = int(final_config_data['Bot'].get('reconnect_delay_min', DEFAULT_CONFIG['Bot']['reconnect_delay_min']))
                except (ValueError, KeyError): final_config_data['Bot']['reconnect_delay_min'] = int(DEFAULT_CONFIG['Bot']['reconnect_delay_min'])
                try: final_config_data['Bot']['reconnect_delay_max'] = int(final_config_data['Bot'].get('reconnect_delay_max', DEFAULT_CONFIG['Bot']['reconnect_delay_max']))
                except (ValueError, KeyError): final_config_data['Bot']['reconnect_delay_max'] = int(DEFAULT_CONFIG['Bot']['reconnect_delay_max'])
                # Ensure other keys exist, falling back to defaults if necessary
                final_config_data['Bot'].setdefault('weather_api_key', DEFAULT_CONFIG['Bot']['weather_api_key'])
                final_config_data['Bot'].setdefault('filtered_words', DEFAULT_CONFIG['Bot']['filtered_words'])

            else:
                 # Use defaults if section missing
                 final_config_data['Bot'] = DEFAULT_CONFIG['Bot'].copy()
                 final_config_data['Bot']['reconnect_delay_min'] = int(final_config_data['Bot']['reconnect_delay_min'])
                 final_config_data['Bot']['reconnect_delay_max'] = int(final_config_data['Bot']['reconnect_delay_max'])

            logging.info("Using configuration from existing file.")
        except (configparser.Error, ValueError, KeyError) as e:
             logging.error(f"Error processing loaded config file: {e}. Falling back to setup.")
             final_config_data = None; loaded_config_parser = None # Mark as invalid

    # If config failed to load or doesn't exist, run GUI setup
    if not final_config_data:
        logging.info("Running initial setup dialog...")
        # Prepare defaults for the dialog (use string values from DEFAULT_CONFIG where needed)
        dialog_defaults = {
            'host': DEFAULT_CONFIG['Connection']['host'], 'port': DEFAULT_CONFIG['Connection']['port'],
            'username': DEFAULT_CONFIG['Connection']['username'], 'password': DEFAULT_CONFIG['Connection']['password'],
            'nickname': DEFAULT_CONFIG['Connection']['nickname'], 'channel': DEFAULT_CONFIG['Connection']['channel'],
            'channel_password': DEFAULT_CONFIG['Connection']['channel_password'],
            'status_message': DEFAULT_CONFIG['Bot']['status_message'],
            'admin_usernames': DEFAULT_CONFIG['Bot']['admin_usernames'], 'gemini_api_key': DEFAULT_CONFIG['Bot']['gemini_api_key'],
            'client_name': DEFAULT_CONFIG['Bot']['client_name'],
            'reconnect_delay_min': DEFAULT_CONFIG['Bot']['reconnect_delay_min'],
            'reconnect_delay_max': DEFAULT_CONFIG['Bot']['reconnect_delay_max'],
            'weather_api_key': DEFAULT_CONFIG['Bot']['weather_api_key'],
            'filtered_words': DEFAULT_CONFIG['Bot']['filtered_words']
        }
        config_dialog = ConfigDialog(None, "TeamTalk Bot Initial Setup", dialog_defaults)
        dialog_result = config_dialog.ShowModal()

        if dialog_result == wx.ID_OK:
            final_config_data = config_dialog.GetConfigData() # Get structured data from dialog
            save_config(final_config_data) # Save the newly entered config
            logging.info("Configuration saved from GUI setup.")
        else:
            logging.info("Setup cancelled via GUI. Exiting.")
            config_dialog.Destroy()
            # Cleanly exit wxApp if setup is cancelled
            if app_instance and hasattr(app_instance, 'ExitMainLoop'):
                app_instance.ExitMainLoop()
            sys.exit(0)
        config_dialog.Destroy()

    # Final check if configuration is valid before proceeding
    if not final_config_data:
        logging.critical("Configuration data could not be loaded or set up. Exiting.")
        if app_instance and hasattr(app_instance, 'ExitMainLoop'): app_instance.ExitMainLoop()
        sys.exit(1)

    # --- Setup Signals ---
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # --- Initialize GUI and Start Bot Thread ---
    main_gui_window = MainBotWindow(None, "TeamTalk Bot - Initializing...", bot_instance_ref)
    main_gui_window.log_message("GUI Initialized.")

    # Start the bot logic in its own thread
    start_new_bot_session(final_config_data)

    # --- Run GUI Main Loop ---
    logging.info("Starting GUI main loop.")
    app_instance.MainLoop()

    # --- Cleanup after GUI Main Loop finishes ---
    logging.info("GUI main loop finished.")

    # Ensure bot thread is stopped and joined if it's still running
    current_bot = bot_instance_ref[0]
    if current_bot is not None and hasattr(current_bot, 'stop'):
        logging.info("Ensuring bot is stopped post-MainLoop...")
        current_bot._mark_stopped_intentionally()
        current_bot.stop()

    if bot_thread and bot_thread.is_alive():
        logging.warning("Bot thread still alive after GUI exit. Waiting to join...")
        bot_thread.join(timeout=5.0) # Wait a bit longer
        if bot_thread.is_alive():
             logging.error("Bot thread did not terminate gracefully after GUI exit!")
        else:
             logging.info("Bot thread joined successfully post-MainLoop.")

    logging.info("Bot script finished.")
    sys.exit(0)