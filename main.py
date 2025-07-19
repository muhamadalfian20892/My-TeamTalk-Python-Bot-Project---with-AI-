#this is the cly of the bot version

import sys, threading, signal, logging, argparse, time, json, codecs
from logging.handlers import RotatingFileHandler
from config_manager import load_config, save_config, DEFAULT_CONFIG
from bot import MyTeamTalkBot, TeamTalkError
from TeamTalk5 import ttstr

# This is the server-optimized entry point.
# For GUI, run main_gui.py

def setup_logging():
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_file = 'bot.log'
    # File handler should always use UTF-8
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=2, encoding='utf-8')
    file_handler.setFormatter(log_formatter)
    
    # Console handler needs to be explicitly told to use UTF-8, especially on Windows
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_formatter)
    # This line is the fix for the UnicodeEncodeError
    if sys.platform == "win32":
        console_handler.stream = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')


    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

class InteractiveShell(threading.Thread):
    def __init__(self, controller):
        super().__init__(daemon=True)
        self.controller = controller
        self.feature_map = {
            "jcl": "announce_join_leave",
            "chanmsg": "allow_channel_messages",
            "broadcast": "allow_broadcast",
            "geminipm": "allow_gemini_pm",
            "geminichan": "allow_gemini_channel",
            "filter": "filter_enabled",
            "lock": "bot_locked",
            "context_history": "context_history_enabled",
            "debug_logging": "debug_logging_enabled"
        }

    def run(self):
        time.sleep(2) # Wait for bot to likely be running
        print("""
Interactive shell started. Type 'help' for commands.""")
        while not self.controller.exit_event.is_set():
            try:
                cmd_line = input("> ").strip().lower()
                if not cmd_line: continue
                
                parts = cmd_line.split()
                command = parts[0]
                args = parts[1:]

                if command == "help":
                    self.show_help()
                elif command == "status":
                    self.show_status()
                elif command == "toggle":
                    self.toggle_feature(args)
                elif command == "set_retention":
                    self.set_retention(args)
                elif command in ["exit", "quit"]:
                    print("Shutdown requested from shell.")
                    self.controller.exit_event.set()
                    break
                else:
                    print(f"Unknown command: {command}")

            except (EOFError, KeyboardInterrupt):
                # This can happen if the main thread is interrupted
                break
            except Exception as e:
                print(f"Error in shell: {e}")
        print("Interactive shell stopped.")

    def show_help(self):
        print("""--- Bot Interactive Shell Help ---
status              - Show the current status of all features.
toggle <feature>    - Toggle a feature ON or OFF.
  Available features: jcl, chanmsg, broadcast, geminipm, geminichan, filter, lock, context_history, debug_logging
set_retention <minutes> - Set the context history retention period in minutes.
exit / quit         - Stop the bot and exit the application.
help                - Show this help message.""")

    def show_status(self):
        bot = self.controller.bot_instance
        if not bot:
            print("Bot is not currently running.")
            return
        
        print("""
--- Bot Feature Status ---""")
        for short_name, full_name in self.feature_map.items():
            status = "ON" if getattr(bot, full_name, False) else "OFF"
            print(f"{short_name:<15} | {full_name:<25} | {status}")
        print(f"Context Retention: {bot.context_history_manager.retention_minutes} minutes")
        print(f"Gemini Model:      {bot.gemini_service.model_name}")
        print()

    def toggle_feature(self, args):
        if not args:
            print("Usage: toggle <feature_name>")
            return
        
        short_name = args[0]
        feature_key = self.feature_map.get(short_name)
        bot = self.controller.bot_instance

        if not bot:
            print("Bot is not running, cannot toggle features.")
            return
        if not feature_key:
            print(f"Unknown feature: {short_name}. Type 'help' for options.")
            return

        # Special handling for debug logging as its method name is different
        if feature_key == 'debug_logging_enabled':
            toggle_method_name = 'toggle_debug_logging'
        else:
            toggle_method_name = f"toggle_{feature_key}"
            
        toggle_method = getattr(bot, toggle_method_name, None)

        if callable(toggle_method):
            print(f'Toggling "{feature_key}"...')
            toggle_method()
            # Show new status
            new_status = "ON" if getattr(bot, feature_key, False) else "OFF"
            print(f'Feature "{feature_key}" is now {new_status}.')
        else:
            print(f'Error: Could not find toggle method for "{feature_key}"')

    def set_retention(self, args):
        if not args or not args[0].isdigit():
            print("Usage: set_retention <minutes>")
            return
        
        try:
            minutes = int(args[0])
            if minutes < 0:
                print("Retention minutes cannot be negative.")
                return
            
            bot = self.controller.bot_instance
            if not bot:
                print("Bot is not running, cannot set retention.")
                return
            
            bot.context_history_manager.set_retention_minutes(minutes)
            bot.config['Bot']['context_history_retention_minutes'] = minutes
            bot._save_runtime_config()
            print(f"Context history retention set to {minutes} minutes.")
        except Exception as e:
            print(f"Error setting retention: {e}")


class ApplicationController:
    def __init__(self, nogui_mode):
        self.nogui = nogui_mode
        self.bot_instance = None
        self.bot_thread = None
        self.config = None
        self.app_instance = None
        self.main_gui_window = None
        self.exit_event = threading.Event()
        self.restart_requested = threading.Event()

    def start(self):
        # Try to load config first.
        self.config = load_config()

        # If no config, we need to prompt. The method depends on the mode.
        if not self.config:
            if self.nogui:
                # Handle console prompting
                self.config = self._prompt_for_config_console()
                if self.config:
                    save_config(self.config)
            else:
                # Handle GUI prompting.
                self.config = self._prompt_for_config_gui()
                if self.config:
                    save_config(self.config)

        # After attempting to load or create, check again.
        if not self.config:
            logging.critical("Configuration failed or was cancelled. Exiting.")
            return

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        if self.nogui:
            self._run_console_mode()
        else:
            self._run_gui_mode()

    def _prompt_for_config_console(self):
        print("Initial configuration not found. Please provide the following details:")
        # Start with a deep copy of defaults to preserve types and structure
        config = json.loads(json.dumps(DEFAULT_CONFIG)) 
        
        for section, settings in DEFAULT_CONFIG.items():
            print(f"--- {section} ---")
            for key, default_value in settings.items():
                # Skip booleans and complex types in the initial console setup
                if isinstance(default_value, (bool, list, dict)):
                    continue

                prompt_text = f"{key} [{default_value}]: "
                user_input = input(prompt_text).strip()
                
                if user_input:
                    # Try to preserve the type of the default value
                    try:
                        value_type = type(default_value)
                        config[section][key] = value_type(user_input)
                    except (ValueError, TypeError):
                        # Fallback to string if casting fails
                        config[section][key] = user_input
                # If user_input is empty, the default value from the deep copy is kept.
        
        print("\nConfiguration complete. You can edit config.json for advanced settings.")
        return config

    def _prompt_for_config_gui(self):
        try:
            import wx
            from gui.config_dialog import ConfigDialog
        except ImportError:
            logging.critical("wxPython or GUI modules not found. Cannot prompt for config in GUI mode.")
            return None

        # Create a temporary app to show the dialog
        app = wx.App(False)
        
        # Flatten the default config for the dialog
        flat_defaults = {**DEFAULT_CONFIG['Connection'], **DEFAULT_CONFIG['Bot']}

        dlg = ConfigDialog(None, "Initial Bot Configuration", flat_defaults)
        
        config_data = None
        if dlg.ShowModal() == wx.ID_OK:
            config_data = dlg.GetConfigData()
        
        dlg.Destroy()
        # The temporary app will be cleaned up by wxPython
        return config_data

    def _run_console_mode(self):
        logging.info("Starting bot in non-GUI mode. Press Ctrl+C or type 'exit' to stop.")
        
        shell = InteractiveShell(self)
        shell.start()

        while not self.exit_event.is_set():
            self.restart_requested.clear()
            self.start_bot_session()
            
            if self.bot_thread:
                self.bot_thread.join() # Wait for the bot thread to finish completely
            
            if self.exit_event.is_set():
                break

            # The on_bot_session_ended callback will have already logged the reason.
            # The loop continues, fulfilling the restart.
        
        self.shutdown()

    def _run_gui_mode(self):
        try:
            import wx
            from gui.main_window import MainBotWindow
        except ImportError:
            logging.critical("wxPython or GUI modules not found. Cannot run in GUI mode.")
            self.exit_event.set()
            return

        if not self.app_instance:
            self.app_instance = wx.App(False)
        self.main_gui_window = MainBotWindow(None, "TeamTalk Bot", self)
        self.main_gui_window.Show()
        self.start_bot_session()
        self.app_instance.MainLoop()
        # self.shutdown() # Shutdown is now called from OnCloseWindow event

    def start_bot_session(self):
        if self.bot_thread and self.bot_thread.is_alive():
            logging.warning("Attempted to start a bot session while one is already running.")
            return
        self.bot_thread = threading.Thread(target=self._bot_thread_func, daemon=True)
        self.bot_thread.start()
        logging.info("New bot session started.")

    def _bot_thread_func(self):
        try:
            self.bot_instance = MyTeamTalkBot(self.config, self)
            if not self.nogui:
                self.bot_instance.set_main_window(self.main_gui_window)
            self.bot_instance.start() # This is a blocking call that runs the bot's main loop
        except Exception as e:
            logging.critical(f"Bot thread failed with unhandled exception: {e}", exc_info=True)

    def _schedule_gui_restart(self, delay_ms=0):
        """A helper to safely schedule restarts on the GUI thread."""
        import wx
        if delay_ms > 0:
            # This function will run on the main thread and can safely create a CallLater object.
            def do_schedule():
                wx.CallLater(delay_ms, self.start_bot_session)
            wx.CallAfter(do_schedule)
        else:
            wx.CallAfter(self.start_bot_session)

    def on_bot_session_ended(self):
        """Callback executed by the bot thread right before it terminates."""
        if self.exit_event.is_set():
            return # Shutdown is in progress, do nothing.

        if self.restart_requested.is_set():
            logging.info("Bot session ended for a requested restart.")
            self.restart_requested.clear() # Reset the flag
            if not self.nogui:
                self._schedule_gui_restart()
        else:
            logging.warning("Bot session ended unexpectedly. Attempting to restart in 15 seconds.")
            if not self.nogui:
                self._schedule_gui_restart(delay_ms=15000)

    def request_restart(self):
        logging.info("Restart requested by bot or controller.")
        if not self.restart_requested.is_set():
            self.restart_requested.set()
            if self.bot_instance:
                self.bot_instance._mark_stopped_intentionally()
                self.bot_instance.stop()

    def _signal_handler(self, sig, frame):
        if self.exit_event.is_set():
            logging.warning("Shutdown already in progress.")
            return
        logging.info(f"Signal {sig} received, initiating shutdown...")
        self.request_shutdown()

    def request_shutdown(self):
        logging.info("Shutdown requested.")
        if not self.exit_event.is_set():
            self.exit_event.set()
            if self.bot_instance:
                self.bot_instance._mark_stopped_intentionally()
                self.bot_instance.stop()
            if not self.nogui and self.main_gui_window:
                import wx
                # Use CallAfter to ensure this runs on the main GUI thread
                wx.CallAfter(self.main_gui_window.Close, True)

    def shutdown(self):
        logging.info("Shutdown sequence started.")
        self.exit_event.set()

        if self.bot_instance:
            self.bot_instance._mark_stopped_intentionally()
            self.bot_instance.stop()
        if self.bot_thread and self.bot_thread.is_alive():
            logging.info("Waiting for bot thread to terminate...")
            self.bot_thread.join(5.0)
        
        if not self.nogui and self.app_instance:
            # If we're in GUI mode, ensure the main loop exits.
            # This might be redundant if called from OnCloseWindow, but it's safe.
            self.app_instance.ExitMainLoop()

        logging.info("Cleanup complete. Exiting.")

    # --- New methods to bridge GUI actions to the bot ---

    def join_channel(self, channel_id, password):
        if self.bot_instance and self.bot_instance._logged_in:
            self.bot_instance._target_channel_id = channel_id
            self.bot_instance.target_channel_path = ttstr(self.bot_instance.getChannelPath(channel_id))
            self.bot_instance.doJoinChannelByID(channel_id, ttstr(password))
        else:
            logging.warning("GUI: Cannot join channel, bot is not connected.")

    def send_pm(self, user_id, message):
        if self.bot_instance and self.bot_instance._logged_in:
            self.bot_instance._send_pm(user_id, message)
        else:
            logging.warning("GUI: Cannot send PM, bot is not connected.")

    def kick_user(self, user_id):
        if self.bot_instance and self.bot_instance._logged_in and self.bot_instance._in_channel:
            # Kicking is relative to the bot's current channel
            self.bot_instance.doKickUser(user_id, self.bot_instance._target_channel_id)
        else:
            logging.warning("GUI: Cannot kick user, bot is not in a channel.")

    def move_user(self, user_id, target_channel_id):
        if self.bot_instance and self.bot_instance._logged_in:
            self.bot_instance.doMoveUser(user_id, target_channel_id)
        else:
            logging.warning("GUI: Cannot move user, bot is not connected.")


if __name__ == "__main__":
    setup_logging()
    controller = ApplicationController(nogui_mode=True)
    controller.start()
    sys.exit(0)