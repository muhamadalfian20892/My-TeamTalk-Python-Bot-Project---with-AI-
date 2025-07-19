import wx
from TeamTalk5 import ttstr, UserRight

class MainBotWindow(wx.Frame):
    def __init__(self, parent, title, controller):
        super(MainBotWindow, self).__init__(parent, title=title, size=(1024, 768))
        self.controller = controller
        self.channel_map = {}
        self.user_map = {}
        self.feature_map = {}
        self.selected_user_id = -1
        self.selected_user_nick = ""

        # --- Main Panel and Sizer ---
        panel = wx.Panel(self)
        main_vbox = wx.BoxSizer(wx.VERTICAL)

        # --- Splitter Window for dynamic layout ---
        splitter = wx.SplitterWindow(panel, style=wx.SP_LIVE_UPDATE)
        splitter.SetSashGravity(0.3) # Give the left panel 30% of the space initially

        # --- Left Panel (Channels and Users) ---
        left_panel = wx.Panel(splitter)
        left_vbox = wx.BoxSizer(wx.VERTICAL)

        channel_label = wx.StaticText(left_panel, label="&Server Channels (Double-click to join)")
        left_vbox.Add(channel_label, 0, wx.LEFT | wx.TOP, 5)
        self.channel_list = wx.ListCtrl(left_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES)
        self.channel_list.InsertColumn(0, "Channel Path", width=250)
        self.channel_list.SetHelpText("List of all channels on the server. Double-click to join a channel.")
        left_vbox.Add(self.channel_list, 1, wx.EXPAND | wx.ALL, 5)

        user_label = wx.StaticText(left_panel, label="&Users in Current Channel (Double-click for actions)")
        left_vbox.Add(user_label, 0, wx.LEFT, 5)
        self.user_list = wx.ListCtrl(left_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES)
        self.user_list.InsertColumn(0, "Nickname", width=150)
        self.user_list.InsertColumn(1, "Username", width=150)
        self.user_list.SetHelpText("List of users in the bot's current primary channel. Double-click a user for options.")
        left_vbox.Add(self.user_list, 1, wx.EXPAND | wx.ALL, 5)

        left_panel.SetSizer(left_vbox)

        # --- Right Panel (Notebook for Log and Features) ---
        right_panel = wx.Panel(splitter)
        right_vbox = wx.BoxSizer(wx.VERTICAL)
        notebook = wx.Notebook(right_panel)
        
        # --- Log Tab ---
        log_tab = wx.Panel(notebook)
        log_sizer = wx.BoxSizer(wx.VERTICAL)
        log_label = wx.StaticText(log_tab, label="Bot &Log:")
        log_sizer.Add(log_label, 0, wx.LEFT | wx.TOP, 5)
        self.logDisplay = wx.TextCtrl(log_tab, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2)
        log_sizer.Add(self.logDisplay, 1, wx.EXPAND | wx.ALL, 5)
        log_tab.SetSizer(log_sizer)
        notebook.AddPage(log_tab, "Log")

        # --- Features Tab ---
        features_tab = wx.Panel(notebook)
        features_sizer = self._create_features_panel(features_tab)
        features_tab.SetSizer(features_sizer)
        notebook.AddPage(features_tab, "Features")
        
        right_vbox.Add(notebook, 1, wx.EXPAND | wx.ALL, 5)
        right_panel.SetSizer(right_vbox)

        # --- Finalize Splitter and Main Layout ---
        splitter.SplitVertically(left_panel, right_panel, 300)
        main_vbox.Add(splitter, 1, wx.EXPAND | wx.ALL, 5)

        self.btnDisconnect = wx.Button(panel, label="&Disconnect and Exit")
        main_vbox.Add(self.btnDisconnect, 0, wx.ALIGN_CENTER | wx.BOTTOM | wx.TOP, 10)
        panel.SetSizer(main_vbox)

        # --- Bind Events ---
        self.btnDisconnect.Bind(wx.EVT_BUTTON, self.OnDisconnect)
        self.Bind(wx.EVT_CLOSE, self.OnCloseWindow)
        
        self.channel_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnChannelActivate)
        self.user_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnUserActivate)

        self.send_channel_msg_btn.Bind(wx.EVT_BUTTON, self.OnSendChannelMessage)
        self.channel_msg_input.Bind(wx.EVT_TEXT_ENTER, self.OnSendChannelMessage)
        self.send_broadcast_btn.Bind(wx.EVT_BUTTON, self.OnSendBroadcast)
        self.broadcast_input.Bind(wx.EVT_TEXT_ENTER, self.OnSendBroadcast)
        self.feature_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnFeatureToggle)

        self.Center()
        self.update_bot_controls_status()

    def _create_features_panel(self, parent_panel):
        """Helper to create the content of the 'Features' tab."""
        features_vbox = wx.BoxSizer(wx.VERTICAL)
        features_vbox.Add(wx.StaticText(parent_panel, label="Bot &Features (Double-click to toggle):"), 0, wx.LEFT | wx.TOP, 5)
        self.feature_list = wx.ListCtrl(parent_panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_VRULES)
        self.feature_list.InsertColumn(0, "Feature", width=200)
        self.feature_list.InsertColumn(1, "Status", width=100)
        features_vbox.Add(self.feature_list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        self.context_retention_label = wx.StaticText(parent_panel, label="Context Retention: N/A")
        features_vbox.Add(self.context_retention_label, 0, wx.LEFT | wx.BOTTOM, 5)
        
        self.channel_msg_input = wx.TextCtrl(parent_panel, style=wx.TE_PROCESS_ENTER)
        self.send_channel_msg_btn = wx.Button(parent_panel, label="Send C&hannel Msg")
        controls_hbox = wx.BoxSizer(wx.HORIZONTAL)
        controls_hbox.Add(self.channel_msg_input, 1, wx.RIGHT, 5)
        controls_hbox.Add(self.send_channel_msg_btn, 0)
        features_vbox.Add(controls_hbox, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

        self.broadcast_input = wx.TextCtrl(parent_panel, style=wx.TE_PROCESS_ENTER)
        self.send_broadcast_btn = wx.Button(parent_panel, label="Send &Broadcast")
        controls_hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        controls_hbox2.Add(self.broadcast_input, 1, wx.RIGHT, 5)
        controls_hbox2.Add(self.send_broadcast_btn, 0)
        features_vbox.Add(controls_hbox2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
        
        return features_vbox

    def log_message(self, message):
        if self.logDisplay:
            wx.CallAfter(self.logDisplay.AppendText, message + "\n")

    def update_bot_controls_status(self):
        """Enables/disables controls based on bot connection status."""
        current_bot = self.controller.bot_instance
        is_bot_running = current_bot is not None and current_bot._logged_in
        
        self.channel_msg_input.Enable(is_bot_running and current_bot._in_channel)
        self.send_channel_msg_btn.Enable(is_bot_running and current_bot._in_channel)
        self.broadcast_input.Enable(is_bot_running)
        self.send_broadcast_btn.Enable(is_bot_running)

    def update_channel_list(self, channels):
        wx.CallAfter(self._update_channel_list_internal, channels)

    def _update_channel_list_internal(self, channels):
        if not self.channel_list: return
        self.channel_list.DeleteAllItems()
        self.channel_map.clear()
        for idx, chan in enumerate(channels):
            self.channel_list.InsertItem(idx, chan['path'])
            self.channel_list.SetItemData(idx, chan['id'])
            self.channel_map[idx] = chan

    def update_user_list(self, users):
        wx.CallAfter(self._update_user_list_internal, users)

    def _update_user_list_internal(self, users):
        if not self.user_list: return
        self.user_list.DeleteAllItems()
        self.user_map.clear()
        for idx, user in enumerate(users):
            self.user_list.InsertItem(idx, user['nick'])
            self.user_list.SetItem(idx, 1, user['user'])
            self.user_list.SetItemData(idx, user['id'])
            self.user_map[idx] = user

    def update_feature_list(self):
        wx.CallAfter(self._update_feature_list_internal)

    def _update_feature_list_internal(self):
        if not self.feature_list: return
        current_bot = self.controller.bot_instance
        self.feature_list.DeleteAllItems()
        self.feature_map.clear()
        
        self.update_bot_controls_status()

        if not current_bot or not current_bot._logged_in: 
            self.context_retention_label.SetLabel("Context Retention: N/A")
            return

        features = {
            "announce_join_leave": "Join/Leave Announce", "allow_channel_messages": "Channel Messages",
            "allow_broadcast": "Broadcast Messages", "allow_gemini_pm": "Gemini AI (PM)",
            "allow_gemini_channel": "Gemini AI (Channel /c)", "filter_enabled": "Word Filter",
            "bot_locked": "Bot Locked", "context_history_enabled": "Context History",
            "debug_logging_enabled": "Debug Logging"
        }

        for idx, (key, name) in enumerate(features.items()):
            status_str = "ON" if getattr(current_bot, key, False) else "OFF"
            self.feature_list.InsertItem(idx, name)
            self.feature_list.SetItem(idx, 1, status_str)
            self.feature_map[idx] = key
        
        self.context_retention_label.SetLabel(f"Context Retention: {current_bot.context_history_manager.retention_minutes} min")

    def OnChannelActivate(self, event):
        idx = event.GetIndex()
        channel_id = self.channel_list.GetItemData(idx)
        channel_path = self.channel_map.get(idx, {}).get('path', 'N/A')
        self.log_message(f"[GUI Action] Requesting join to channel '{channel_path}' (ID: {channel_id})")
        
        password = ""
        # Ask for password if channel seems to be password protected (can't know for sure from client side)
        # This is a simple heuristic. A better way would be to try to join and handle password error.
        dlg = wx.TextEntryDialog(self, f"Enter password for '{channel_path}' if required:", "Join Channel", style=wx.OK|wx.CANCEL|wx.TE_PASSWORD)
        if dlg.ShowModal() == wx.ID_OK:
            password = dlg.GetValue()
        dlg.Destroy()

        self.controller.join_channel(channel_id, password)

    def OnUserActivate(self, event):
        idx = event.GetIndex()
        self.selected_user_id = self.user_list.GetItemData(idx)
        self.selected_user_nick = self.user_map.get(idx, {}).get('nick', 'N/A')
        self.ShowUserActionMenu()
    
    def ShowUserActionMenu(self):
        if self.selected_user_id == -1: return

        menu = wx.Menu()
        my_rights = self.controller.bot_instance.my_rights if self.controller.bot_instance else 0

        # Create menu items and disable them if the bot lacks rights
        pm_item = menu.Append(wx.ID_ANY, f"&Send PM to {self.selected_user_nick}")
        
        kick_item = menu.Append(wx.ID_ANY, f"&Kick {self.selected_user_nick}")
        if not (my_rights & UserRight.USERRIGHT_KICK_USERS):
            kick_item.Enable(False)

        move_item = menu.Append(wx.ID_ANY, f"&Move {self.selected_user_nick}...")
        if not (my_rights & UserRight.USERRIGHT_MOVE_USERS):
            move_item.Enable(False)

        # Bind events
        self.Bind(wx.EVT_MENU, self.OnUserPM, pm_item)
        self.Bind(wx.EVT_MENU, self.OnUserKick, kick_item)
        self.Bind(wx.EVT_MENU, self.OnUserMove, move_item)

        self.PopupMenu(menu)
        menu.Destroy()

    def OnUserPM(self, event):
        dlg = wx.TextEntryDialog(self, f"Enter message to send to {self.selected_user_nick}:", "Send Private Message")
        if dlg.ShowModal() == wx.ID_OK:
            message = dlg.GetValue()
            if message:
                self.log_message(f"[GUI PM to {self.selected_user_nick}] {message}")
                self.controller.send_pm(self.selected_user_id, message)
        dlg.Destroy()

    def OnUserKick(self, event):
        confirm = wx.MessageBox(f"Are you sure you want to kick {self.selected_user_nick}?", "Confirm Kick", wx.YES_NO | wx.ICON_QUESTION)
        if confirm == wx.YES:
            self.log_message(f"[GUI Action] Kicking user {self.selected_user_nick} (ID: {self.selected_user_id})")
            self.controller.kick_user(self.selected_user_id)

    def OnUserMove(self, event):
        channel_paths = [chan['path'] for chan in self.channel_map.values()]
        if not channel_paths:
            wx.MessageBox("No channels available to move user to.", "Error", wx.OK | wx.ICON_ERROR)
            return

        dlg = wx.SingleChoiceDialog(self, f"Move {self.selected_user_nick} to which channel?", "Move User", channel_paths)
        if dlg.ShowModal() == wx.ID_OK:
            selected_path = dlg.GetStringSelection()
            target_chan = next((chan for chan in self.channel_map.values() if chan['path'] == selected_path), None)
            if target_chan:
                self.log_message(f"[GUI Action] Moving {self.selected_user_nick} to {selected_path}")
                self.controller.move_user(self.selected_user_id, target_chan['id'])
        dlg.Destroy()

    def OnFeatureToggle(self, event):
        idx = event.GetIndex()
        feature_key = self.feature_map.get(idx)
        current_bot = self.controller.bot_instance
        if not current_bot or not feature_key: return

        self.log_message(f"[GUI Action] Toggling feature: {feature_key}")
        toggle_method_name = f"toggle_{feature_key}"
        toggle_method = getattr(current_bot, toggle_method_name, None)

        if callable(toggle_method):
            toggle_method()
            self.update_feature_list()
        else:
            self.log_message(f"[GUI Error] Unknown toggle method '{toggle_method_name}'")

    def OnSendChannelMessage(self, event):
        current_bot = self.controller.bot_instance
        message = self.channel_msg_input.GetValue().strip()
        if not current_bot or not message: return

        if not current_bot._in_channel or current_bot._target_channel_id <= 0:
             self.log_message("[GUI Error] Cannot send: Bot is not in a channel."); return
        
        self.log_message(f"[GUI Send Chan] {message}")
        if current_bot._send_channel_message(current_bot._target_channel_id, f"{message}"):
            self.channel_msg_input.SetValue("")
        else:
            self.log_message("[GUI Error] Failed to send channel message.")

    def OnSendBroadcast(self, event):
        current_bot = self.controller.bot_instance
        message = self.broadcast_input.GetValue().strip()
        if not current_bot or not message: return
        
        self.log_message(f"[GUI Send Broadcast] {message}")
        if current_bot._send_broadcast(f"{message}"):
            self.broadcast_input.SetValue("")
        else:
            self.log_message("[GUI Error] Failed to send broadcast.")
    
    def OnDisconnect(self, event):
        self.log_message("Disconnect button clicked. Stopping bot...")
        self.controller.request_shutdown()

    def OnCloseWindow(self, event):
        self.log_message("Main window closing. Stopping bot...")
        self.controller.request_shutdown()
        self.Destroy()