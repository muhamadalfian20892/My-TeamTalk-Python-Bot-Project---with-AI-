
import sys, time, logging, random, re, wx
from TeamTalk5 import (
    TeamTalk, TeamTalkError, TextMsgType, UserRight, Subscription,
    ttstr, ClientError, ClientFlags, TT_STRLEN, TextMessage, Channel
)
from config_manager import save_config
from handlers import command_handler
from services.gemini_service import GeminiService
from services.weather_service import WeatherService
from services.time_service import TimeService
from services.news_service import NewsService
from services.url_shortener_service import URLShortenerService
from services.reminder_service import ReminderService
from services.data_service import DataService
from context_history_manager import ContextHistoryManager

class MyTeamTalkBot(TeamTalk):
    def __init__(self, config_dict, controller=None):
        super().__init__()
        self.config = config_dict
        self.controller = controller
        conn_conf, bot_conf = self.config.get('Connection', {}), self.config.get('Bot', {})
        db_conf = self.config.get('Database', {})

        self.host, self.tcp_port = ttstr(conn_conf.get('host')), int(conn_conf.get('port'))
        self.udp_port, self.nickname = self.tcp_port, ttstr(conn_conf.get('nickname'))
        self.status_message, self.username = ttstr(bot_conf.get('status_message')), ttstr(conn_conf.get('username'))
        self.password, self.channel_password = ttstr(conn_conf.get('password')), ttstr(conn_conf.get('channel_password'))
        self.client_name = ttstr(bot_conf.get('client_name'))
        
        # Use new initial channel path from Bot section
        self.initial_channel_path = ttstr(bot_conf.get('initial_channel_path', '/'))
        self.target_channel_path = self.initial_channel_path

        self.reconnect_delay_min = int(bot_conf.get('reconnect_delay_min'))
        self.reconnect_delay_max = int(bot_conf.get('reconnect_delay_max'))

        self.filtered_words = {w.strip().lower() for w in bot_conf.get('filtered_words','').split(',') if w.strip()}
        self.admin_usernames_config = [n.strip().lower() for n in bot_conf.get('admin_usernames','').split(',') if n.strip()]

        self._logged_in = self._running = self._intentional_stop = self.bot_locked = False
        self._my_user_id = self._target_channel_id = self._join_cmd_id = -1
        self._start_time = 0; self.my_rights = UserRight.USERRIGHT_NONE
        
        self._in_channel_ids = set() 
        
        self._user_cache = {}
        self.admin_user_ids, self.blocked_commands = set(), set()
        
        self._text_message_buffer, self.polls, self.warning_counts = {}, {}, {}
        self.next_poll_id = 1; self.main_window = None

        self.announce_join_leave = self.allow_channel_messages = self.allow_broadcast = True
        self.allow_gemini_pm = self.allow_gemini_channel = True
        self.welcome_message_mode, self.filter_enabled = "template", bool(self.filtered_words)
        self.UNBLOCKABLE_COMMANDS = {'h','q','rs','block','unblock','info','whoami','rights','lock','!tfilter','!tgmmode', 'health', 'afk', 'seen'}

        self.context_history_enabled = bot_conf.get('context_history_enabled', True)
        self.debug_logging_enabled = bot_conf.get('debug_logging_enabled', False)
        
        # Initialize services
        self.data_service = DataService(db_conf.get('file'))

        gemini_system_instruction = bot_conf.get('gemini_system_instruction', 'You are a helpful assistant.')
        gemini_model_name = bot_conf.get('gemini_model_name', 'gemini-1.5-flash-latest')
        self.gemini_service = GeminiService(bot_conf.get('gemini_api_key'), self.context_history_enabled, gemini_system_instruction, gemini_model_name)
        
        self.weather_service = WeatherService(bot_conf.get('weather_api_key'))
        self.news_service = NewsService(bot_conf.get('news_api_key'))
        self.time_service = TimeService()
        self.url_shortener_service = URLShortenerService()
        self.reminder_service = ReminderService(self)
        self.context_history_manager = ContextHistoryManager(bot_conf.get('context_history_retention_minutes', 60))
        if not self.gemini_service.is_enabled(): self.allow_gemini_pm = self.allow_gemini_channel = False
        self._apply_debug_logging_setting()

    @property
    def _in_channel(self):
        return self._target_channel_id in self._in_channel_ids

    def set_main_window(self, window): self.main_window = window; self._log_to_gui("GUI window linked.")
    def _log_to_gui(self, msg):
        if self.main_window and hasattr(wx, 'CallAfter'):
            wx.CallAfter(self.main_window.log_message, msg)
        else:
            logging.info(f"[Bot] {msg}")

    def _send_pm(self, to_id, msg): self._send_text_message(msg, TextMsgType.MSGTYPE_USER, nToUserID=to_id)
    def _send_channel_message(self, chan_id, msg): return self._send_text_message(msg, TextMsgType.MSGTYPE_CHANNEL, nChannelID=chan_id)
    def _send_broadcast(self, msg): return self._send_text_message(msg, TextMsgType.MSGTYPE_BROADCAST)

    def _send_text_message(self, message: str, msg_type: int, **kwargs) -> bool:
        if not message: return False
        is_chan = msg_type == TextMsgType.MSGTYPE_CHANNEL
        if (is_chan and (self.bot_locked or not self.allow_channel_messages)) or \
           (msg_type == TextMsgType.MSGTYPE_BROADCAST and (self.bot_locked or not self.allow_broadcast)):
            return False
        
        user_id = None
        if msg_type == TextMsgType.MSGTYPE_USER and 'nToUserID' in kwargs:
            user_id = str(kwargs['nToUserID'])
        elif msg_type == TextMsgType.MSGTYPE_CHANNEL and 'nChannelID' in kwargs:
            user_id = str(kwargs['nChannelID'])
        
        chunk_size = TT_STRLEN - 1
        message_chunks = [message[i:i + chunk_size] for i in range(0, len(message), chunk_size)]

        for i, chunk in enumerate(message_chunks):
            textmsg = TextMessage()
            textmsg.nMsgType = msg_type
            textmsg.nToUserID = kwargs.get('nToUserID', 0)
            textmsg.nChannelID = kwargs.get('nChannelID', 0)
            textmsg.szMessage = ttstr(chunk)
            textmsg.bMore = (i < len(message_chunks) - 1)
            if self.doTextMessage(textmsg) == 0:
                self._log_to_gui(f"[Error] Failed to send message part."); return False
        
        if user_id:
            self.context_history_manager.add_message(user_id, message, is_bot=True)
        return True

    def _populate_user_cache(self):
        self._user_cache.clear()
        try:
            all_users = self.getServerUsers() or []
            for user in all_users:
                self._user_cache[user.nUserID] = user
            logging.info(f"User cache populated with {len(self._user_cache)} users.")
            self._update_admin_ids()
        except TeamTalkError as e:
            logging.error(f"Error populating user cache: {e}")

    def _update_admin_ids(self):
        self.admin_user_ids.clear()
        for user in self._user_cache.values():
            if ttstr(user.szUsername).lower() in self.admin_usernames_config:
                self.admin_user_ids.add(user.nUserID)
        if ttstr(self.username).lower() in self.admin_usernames_config:
            self.admin_user_ids.add(self._my_user_id)
        logging.debug(f"Admin IDs updated: {self.admin_user_ids or 'None'}")

    def _is_admin(self, user_id): return user_id in self.admin_user_ids
    
    def _find_user_by_nick(self, nick):
        target_nick = ttstr(nick).lower()
        for user in self._user_cache.values():
            if ttstr(user.szNickname).lower() == target_nick:
                return user
        return None

    def _save_runtime_config(self, save_gkey=False):
        self._log_to_gui("Saving runtime config...");
        self.config['Bot']['filtered_words'] = ','.join(sorted(list(self.filtered_words)))
        self.config['Connection']['nickname'] = ttstr(self.nickname)
        self.config['Bot']['status_message'] = ttstr(self.status_message)
        self.config['Bot']['initial_channel_path'] = ttstr(self.initial_channel_path)
        if save_gkey: self.config['Bot']['gemini_api_key'] = self.gemini_service.api_key
        self.config['Bot']['gemini_system_instruction'] = self.gemini_service.system_instruction
        self.config['Bot']['gemini_model_name'] = self.gemini_service.model_name
        save_config(self.config)
        
    def _mark_stopped_intentionally(self): self._intentional_stop = True

    def stop(self):
        if not self._running: return
        self._log_to_gui("Stop requested."); self._running = False; time.sleep(0.1)
        self.reminder_service.shutdown()
        self.data_service.close()
        try:
            if self.getFlags() & ClientFlags.CLIENT_CONNECTED:
                if self._logged_in: self.doLogout()
                self.disconnect()
        except TeamTalkError: pass
        finally:
            self.closeTeamTalk(); self._tt = None

    def start(self):
        self._log_to_gui(f"Initializing bot session..."); self._start_time = time.time()
        self._intentional_stop = False; self._running = True
        self.reminder_service.start()
        try:
            if not self.connect(self.host, self.tcp_port, self.udp_port): self._running = False; return
            self._log_to_gui("Connection started. Entering event loop.")
            while self._running: self.runEventLoop(100)
        except Exception as e:
            logging.error(f"Bot `start` method caught an exception: {e}", exc_info=True)
        finally:
            self.stop()
            if self.controller:
                self.controller.on_bot_session_ended()

    def _initiate_restart(self):
        self._log_to_gui("--- BOT RESTART SEQUENCE INITIATED ---")
        if self.controller:
            self.controller.request_restart()
        else:
            self._log_to_gui("[CRITICAL] No controller found! Cannot restart.")

    def _update_gui_channel_list(self):
        if not self.main_window: return
        try:
            channels_raw = self.getServerChannels() or []
            channels_data = []
            for chan in sorted(channels_raw, key=lambda c: ttstr(c.szName).lower()):
                path = ttstr(self.getChannelPath(chan.nChannelID))
                channels_data.append({'id': chan.nChannelID, 'path': path})
            self.main_window.update_channel_list(channels_data)
        except TeamTalkError as e:
            self._log_to_gui(f"[Error] Failed to get server channels: {e}")

    def _update_gui_user_list(self, channel_id):
        if not self.main_window or channel_id != self._target_channel_id:
            return
        try:
            users_raw = self.getChannelUsers(channel_id) or []
            users_data = []
            for user in sorted(users_raw, key=lambda u: ttstr(u.szNickname).lower()):
                users_data.append({
                    'id': user.nUserID,
                    'nick': ttstr(user.szNickname),
                    'user': ttstr(user.szUsername)
                })
            self.main_window.update_user_list(users_data)
        except TeamTalkError as e:
            self._log_to_gui(f"[Error] Failed to get users for channel {channel_id}: {e}")

    def onConnectSuccess(self): self._log_to_gui("Connected. Logging in..."); self.doLogin(self.nickname, self.username, self.password, self.client_name)
    def onConnectFailed(self): self._log_to_gui("[Error] Connection failed."); self._handle_reconnect()
    def onConnectionLost(self): 
        self._log_to_gui("[Error] Connection lost.")
        self._logged_in = False
        self._in_channel_ids.clear()
        if self.main_window:
            wx.CallAfter(self.main_window.update_channel_list, [])
            wx.CallAfter(self.main_window.update_user_list, [])
            wx.CallAfter(self.main_window.update_feature_list)
        self._handle_reconnect()

    def _handle_reconnect(self):
        if self._running and not self._intentional_stop:
            delay = random.randint(self.reconnect_delay_min, self.reconnect_delay_max)
            self._log_to_gui(f"Reconnecting in {delay}s..."); time.sleep(delay)
            if self._running and not self._intentional_stop:
                self._initiate_restart()

    def onCmdError(self, cmd_id, err):
        self._log_to_gui(f"[Cmd Error {cmd_id}] {err.nErrorNo} - {ttstr(err.szErrorMsg)}")
        if err.nErrorNo in [ClientError.CMDERR_INVALID_ACCOUNT, ClientError.CMDERR_SERVER_BANNED]: self._mark_stopped_intentionally()

    def onCmdMyselfLoggedIn(self, user_id, user_acc):
        self._logged_in, self._my_user_id = True, user_id
        self.my_rights = user_acc.uUserRights
        self._log_to_gui(f"Login success! My ID: {user_id}, Rights: {self.my_rights:#010x}")

        self.doSubscribe(0, Subscription.SUBSCRIBE_USER_MSG | Subscription.SUBSCRIBE_CHANNEL_MSG)
        self._populate_user_cache()
        
        # Update last seen for myself
        self.data_service.update_last_seen(user_id, ttstr(self.nickname), "logging in")

        if self.main_window:
            wx.CallAfter(self.main_window.Show)
            wx.CallAfter(self.main_window.SetTitle, f"Bot - {ttstr(self.nickname)}")
            wx.CallAfter(self._update_gui_channel_list)
            wx.CallAfter(self.main_window.update_user_list, []) # Clear user list initially
            wx.CallAfter(self.main_window.update_feature_list)

        if self.status_message: self.doChangeStatus(0, self.status_message)
        
        # --- MODIFIED: More robust initial channel join logic ---
        self.target_channel_path = self.initial_channel_path
        self._log_to_gui(f"Attempting to find initial channel: '{self.target_channel_path}'")
        
        chan_id = self.getChannelIDFromPath(self.target_channel_path)
        
        if chan_id <= 0:
            self._log_to_gui(f"Initial channel path not found immediately. Falling back to root channel.")
            chan_id = self.getRootChannelID()

        if chan_id > 0:
            self._log_to_gui(f"Found channel ID {chan_id}. Attempting to join.")
            self._target_channel_id = chan_id
            self._join_cmd_id = self.doJoinChannelByID(chan_id, self.channel_password)
        else:
            self._log_to_gui("[Error] Could not find a valid channel to join (not even root). No join action will be taken.")
    
    def onCmdMyselfLoggedOut(self):
        self._log_to_gui("Logged out.")
        self._logged_in = False
        self._user_cache.clear()
        self._in_channel_ids.clear()
        if self.main_window:
            wx.CallAfter(self.main_window.update_channel_list, [])
            wx.CallAfter(self.main_window.update_user_list, [])
            wx.CallAfter(self.main_window.update_feature_list)
    
    def onCmdUserLoggedIn(self, user):
        self._user_cache[user.nUserID] = user
        self._update_admin_ids()
        self.data_service.update_last_seen(user.nUserID, ttstr(user.szNickname), "logging in")
        logging.info(f"User logged in: {ttstr(user.szNickname)}. Cache updated.")

    def onCmdUserLoggedOut(self, user):
        cached_user_nick = "Unknown"
        if user.nUserID in self._user_cache:
            cached_user_nick = ttstr(self._user_cache[user.nUserID].szNickname)
            del self._user_cache[user.nUserID]
            self._update_admin_ids()
        
        self.data_service.update_last_seen(user.nUserID, cached_user_nick, "logging out")
        logging.info(f"User logged out: {cached_user_nick}. Cache updated.")
        if self.main_window and user.nChannelID == self._target_channel_id:
            self._update_gui_user_list(self._target_channel_id)
            
    def onCmdUserJoinedChannel(self, user):
        user_nick = ttstr(user.szNickname)
        self.data_service.update_last_seen(user.nUserID, user_nick, f"joining channel '{ttstr(self.getChannelPath(user.nChannelID))}'")

        if user.nUserID == self._my_user_id:
            self._in_channel_ids.add(user.nChannelID)
            self._log_to_gui(f"Joined channel ID: {user.nChannelID}. Currently in: {self._in_channel_ids}")
            if user.nChannelID == self._target_channel_id:
                self._update_gui_user_list(user.nChannelID)
                if self.main_window: wx.CallAfter(self.main_window.update_bot_controls_status)
            return
            
        if user.nUserID not in self._user_cache:
            logging.warning(f"User {user.nUserID} joined channel but not in cache yet. Refreshing cache.")
            self._populate_user_cache()
        
        if self.main_window and user.nChannelID == self._target_channel_id:
            self._update_gui_user_list(user.nChannelID)

        if self.announce_join_leave and user.nChannelID in self._in_channel_ids:
            cached_user = self._user_cache.get(user.nUserID)
            if cached_user:
                user_nick = ttstr(cached_user.szNickname)
                logging.info(f"Announcing join for user '{user_nick}' in channel {user.nChannelID}")
                welcome_msg = self.gemini_service.generate_welcome_message() if self.welcome_message_mode == "gemini" and self.gemini_service.is_enabled() else f"Welcome, {user_nick}!"
                self._send_channel_message(user.nChannelID, welcome_msg)
            else:
                logging.error(f"Could not announce join for UserID {user.nUserID}, not found in cache after refresh.")
    
    def onCmdUserLeftChannel(self, chan_id, user):
        user_nick = ttstr(user.szNickname)
        self.data_service.update_last_seen(user.nUserID, user_nick, f"leaving channel '{ttstr(self.getChannelPath(chan_id))}'")

        if user.nUserID == self._my_user_id:
            self._in_channel_ids.discard(chan_id)
            self._log_to_gui(f"Left channel ID: {chan_id}. Currently in: {self._in_channel_ids}")
            if chan_id == self._target_channel_id:
                if self.main_window: 
                    wx.CallAfter(self.main_window.update_user_list, [])
                    wx.CallAfter(self.main_window.update_bot_controls_status)
            return

        if self.main_window and chan_id == self._target_channel_id:
            self._update_gui_user_list(chan_id)

        if self.announce_join_leave and chan_id in self._in_channel_ids:
            logging.info(f"Announcing leave for user: {user_nick} from channel {chan_id}")
            self._send_channel_message(chan_id, f"Goodbye, {user_nick}.")

    def onCmdMyselfKickedFromChannel(self, channelid, user):
        self._in_channel_ids.discard(channelid)
        kicker_nick = ttstr(user.szNickname) if user else "Unknown"
        self.data_service.update_last_seen(self._my_user_id, ttstr(self.nickname), f"being kicked from channel by {kicker_nick}")
        self._log_to_gui(f"Kicked from channel ID {channelid} by {kicker_nick}. Currently in: {self._in_channel_ids}")
        if channelid == self._target_channel_id:
            if self.main_window:
                wx.CallAfter(self.main_window.update_user_list, [])
                wx.CallAfter(self.main_window.update_bot_controls_status)

    def onCmdChannelNew(self, channel: Channel):
        self._log_to_gui(f"New channel created: {ttstr(channel.szName)}")
        self._update_gui_channel_list()

    def onCmdChannelUpdate(self, channel: Channel):
        self._log_to_gui(f"Channel updated: {ttstr(channel.szName)}")
        self._update_gui_channel_list()

    def onCmdChannelRemove(self, channel: Channel):
        self._log_to_gui(f"Channel removed: {ttstr(channel.szName)}")
        self._update_gui_channel_list()

    def onCmdUserTextMessage(self, textmessage):
        if textmessage.nFromUserID == self._my_user_id or not self._logged_in: return
        key = (textmessage.nFromUserID, textmessage.nMsgType, textmessage.nChannelID)
        self._text_message_buffer[key] = self._text_message_buffer.get(key, "") + ttstr(textmessage.szMessage)
        if textmessage.bMore: return
        full_msg = self._text_message_buffer.pop(key, "")
        if not full_msg: return
        
        if textmessage.nMsgType == TextMsgType.MSGTYPE_USER:
            self.context_history_manager.add_message(str(textmessage.nFromUserID), full_msg, is_bot=False)
        elif textmessage.nMsgType == TextMsgType.MSGTYPE_CHANNEL:
            self.context_history_manager.add_message(str(textmessage.nChannelID), full_msg, is_bot=False)

        log_prefix = ""
        if textmessage.nMsgType == TextMsgType.MSGTYPE_CHANNEL: log_prefix=f"[{ttstr(self.getChannelPath(textmessage.nChannelID))}]"
        elif textmessage.nMsgType == TextMsgType.MSGTYPE_USER: log_prefix="[PM]"
        
        sender_nick = "Unknown"
        if textmessage.nFromUserID in self._user_cache:
            sender_nick = ttstr(self._user_cache[textmessage.nFromUserID].szNickname)
        self._log_to_gui(f"{log_prefix} <{sender_nick}> {full_msg}")
        
        command_handler.handle_message(self, textmessage, full_msg)

    def onCmdUserUpdate(self, user):
        user_nick = ttstr(user.szNickname)
        if user.nUserID in self._user_cache:
            old_nick = ttstr(self._user_cache[user.nUserID].szNickname)
            if old_nick.lower() != user_nick.lower():
                self.data_service.update_last_seen(user.nUserID, user_nick, f"changing nickname from '{old_nick}'")
            self._user_cache[user.nUserID] = user
            self._update_admin_ids()
        
        if user.nUserID == self._my_user_id:
            if user_nick != self.nickname or ttstr(user.szStatusMsg) != self.status_message:
                self.nickname = user_nick
                self.status_message = ttstr(user.szStatusMsg)
                self._log_to_gui(f"My info updated: Nick='{self.nickname}', Status='{self.status_message}'")
                self._save_runtime_config()
        
        if self.main_window and user.nChannelID == self._target_channel_id:
            self._update_gui_user_list(self._target_channel_id)

    def toggle_feature(self, attr_name, on_msg, off_msg):
        setattr(self, attr_name, not getattr(self, attr_name))
        new_state = getattr(self, attr_name)
        self._log_to_gui(f"[Toggle] {on_msg if new_state else off_msg}")
        return new_state
    def toggle_announce_join_leave(self): self.toggle_feature('announce_join_leave', "JCL ON", "JCL OFF")
    def toggle_allow_channel_messages(self): self.toggle_feature('allow_channel_messages', "Chan Msgs ON", "Chan Msgs OFF")
    def toggle_allow_broadcast(self): self.toggle_feature('allow_broadcast', "Broadcasts ON", "Broadcasts OFF")
    def toggle_allow_gemini_pm(self): self.toggle_feature('allow_gemini_pm', "Gemini PM ON", "Gemini PM OFF")
    def toggle_allow_gemini_channel(self): self.toggle_feature('allow_gemini_channel', "Gemini Chan ON", "Gemini Chan OFF")
    def toggle_bot_lock(self): self.toggle_feature('bot_locked', "Bot Lock ON", "Bot Lock OFF")
    def toggle_filter_enabled(self):
        if not self.filter_enabled and not self.filtered_words:
            self._log_to_gui("[Warn] Cannot enable filter: no words defined."); return
        self.toggle_feature('filter_enabled', "Filter ON", "Filter OFF")

    def toggle_context_history_enabled(self):
        self.toggle_feature('context_history_enabled', "Context History ON", "Context History OFF")

    def _apply_debug_logging_setting(self):
        root_logger = logging.getLogger()
        if self.debug_logging_enabled:
            root_logger.setLevel(logging.DEBUG)
            self._log_to_gui("Debug logging is now ON.")
        else:
            root_logger.setLevel(logging.INFO)
            self._log_to_gui("Debug logging is now OFF.")

    def toggle_debug_logging(self):
        self.debug_logging_enabled = not self.debug_logging_enabled
        self._apply_debug_logging_setting()
        self.config['Bot']['debug_logging_enabled'] = self.debug_logging_enabled
        self._save_runtime_config()