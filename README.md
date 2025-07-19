# PyBot+: A Random TeamTalk Bot
*By Muhamad Alfian*

### Overview

This bot is just a random project. It started out aiming for my personal use, but because many people were asking me to open this to the public, here it is. I hope it's useful for you.

This bot can run with or without a GUI, connects to a TeamTalk 5 server, and responds to a bunch of commands. It uses some cool AI and web services to do things like answer questions, get the news, and manage your server.

Drop me a question or some feedback at: **hafiyanajah@gmail.com**

### Behind the Story

Honestly, I just wanted to see if I could build a bot. It was a personal project to learn and play around with Python and the TeamTalk platform. I added a feature, then another, and then people in my channels started noticing. They asked if they could use it, and that's when I realized maybe this "random project" could be helpful to others.

A big thumbs up to Google for helping me code this thing. Their AI is no joke and it did a lot of the heavy lifting for the conversational parts. You should really check out what it can do:
-   [Gemini](https://gemini.google.com)
-   [Google AI Studio](https://aistudio.google.com/app/apikey)

### What It Can Do (Feature List)

The bot has a bunch of commands. Some are for everyone, and some are just for admins. To see the full list, just send the bot a private message with the command `h`.

#### For Everyone
-   **AI Chat:** Talk to Google's Gemini AI. Use `c <your question>` in a PM, or `/c <your question>` in a channel. It even remembers the last few messages to keep the conversation going.
-   **News:** Get the latest news. Type `news top` for top stories, or `news <topic>` to search for something specific.
-   **Reminders:** The bot can remember things for you. The format is `remindme "your message" in 5 minutes` (or hours/days). It will PM you when the time is up, even if the bot restarts.
-   **Weather & Time:** Check the weather with `w <location>` or the time with `!time <location>`.
-   **URL Shortener:** Got a long link? Shorten it with `shorten <the long url>`.
-   **Polling:** You can create channel polls with `!poll "Question" "Option A" "B"`, vote with `!vote <id> <number>`, and see results with `!results <id>`.
-   **Bot Info:** Use `ping` to see if it's alive and `info` to get all the details about what it's running and what features are on.

#### For Admins Only
-   **Bot Control:** You can `rs` (restart), `q` (quit), or `lock` the bot. You can also `block` and `unblock` commands you don't want people using.
-   **Feature Toggles:** Turn things on and off, like join/leave announcements (`jcl`), the word filter (`!tfilter`), or the AI (`tg_gemini_pm`, `tg_gemini_chan`).
-   **User Management:** Admins can `kick`, `move`, `ban`, and `unban` users right from a PM.
-   **Channel Management:** Tell the bot to join another channel with `jc <channel_path>`.

### How to Get It Working

#### 1. Stuff You Need First
-   Python 3.11 or newer.
-   A TeamTalk 5 Server.
-   The TeamTalk 5 SDK. Unzip it and make sure the `TeamTalk_DLL` folder is sitting in the same directory as these bot files.

#### 2. Install the Libraries
You need a few Python libraries for this to work. I made a `requirements.txt` file to make it easy. Just run this in your terminal:
```bash
pip install -r requirements.txt
```

#### 3. Configuration
When you run the bot for the first time, it will ask you for some info since `config.json` doesn't exist yet. You'll need to enter your server details, a nickname for the bot, and your TeamTalk username so it knows who the admin is.

To get all the features working, you'll need some API keys. They're free to get:
-   **Gemini:** [Google AI Studio](https://aistudio.google.com/app/apikey)
-   **Weather:** [OpenWeatherMap](https://openweathermap.org/api)
-   **News:** [NewsAPI.org](https://newsapi.org)

Just paste them in when the bot asks or edit the `config.json` file later.

#### 4. Run It
-   **With the GUI:**
    ```bash
    python main_gui.py
    ```
-   **Without the GUI (console only):**
    ```bash
    python main.py
    ```

### Project Structure (For Contributors)

If you want to add something to the bot, here's a quick guide on where things go. Keeping the project organized makes it easier for everyone.

```
/
├── TeamTalk_DLL/          # TeamTalk 5 libraries go here
├── services/              # For connecting to external APIs (Weather, AI, News, etc.)
│   ├── gemini_service.py
│   ├── news_service.py
│   └── ...
├── handlers/              # For all the bot's command logic
│   ├── admin/             # Logic for admin-only commands
│   │   ├── bot_control.py
│   │   └── ...
│   ├── user_commands.py   # Logic for general user commands
│   ├── ai_commands.py     # Logic for AI-related commands
│   ├── command_handler.py # The main router that calls other handlers
│   └── ...
├── gui/                   # All GUI (wxPython) related files
│   ├── main_window.py
│   ├── config_dialog.py
│   └── ...
├── bot.py                 # The main bot class, event handling, and core logic
├── main.py                # Entry point for the console/headless version
├── main_gui.py            # Entry point for the GUI version
├── config_manager.py      # Handles loading/saving config.json
├── requirements.txt       # List of Python libraries needed
└── README.md              # This file
```

-   **Adding a new API service?** Create a new file in the `services/` directory.
-   **Adding a new user command?** Add the function to a relevant file in `handlers/` (like `user_commands.py` or `utility_commands.py`) and then add the command to the command map in `user_commands.py`.
-   **Changing the GUI?** The files you need are in the `gui/` directory.
-   **Changing core bot behavior?** That will likely be in `bot.py`.

### Code of Conduct
If you want to contribute to this project, that's awesome. Just follow a few simple rules so we can all get along.

1.  **Be Cool:** Treat everyone with respect. No personal attacks or harassment. We're all here to build something cool.
2.  **Work Together:** Be open to suggestions and give constructive feedback. It's a team effort.
3.  **Keep It Clean:** Avoid offensive language.
4.  **Stay Focused:** When you're working on an issue, try to keep the discussion related to that issue.
5.  **Follow the Structure:** Try to place new files and code in the correct directories as outlined in the Project Structure section. This helps keep things tidy.

Basically, just don't be a jerk.

### Recent Changes Made
-   **Status Saving:** Bot status message is now saved in `config.json` and persists after a restart.
-   **Restart Command:** Added the `rs` command for admins to restart the bot.
-   **Change Status Command:** Added the `cs <new_status>` command for users to change the bot's status message.
-   **Change Nickname Command:** Added the `cn <new_nick>` command for users to change the bot's nickname.

---