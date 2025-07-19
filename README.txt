My TeamTalk Python Bot Project! (NewTeamTalkBot v2.6)

Alright, this is my Python bot for TeamTalk 5 servers! Been tinkering with this for a while, using AI to help build out the features and the GUI side of things. It's come quite a long way!

This bot (version 2.6 now!) is designed to run on a TeamTalk 5 server and provide some helpful, fun, and administrative features.

What's Inside? (The Cool Stuff)

Graphical Interface (GUI): Uses wxPython to show a live log, let you toggle features on/off easily, and even send basic channel or broadcast messages right from the window.

Gemini AI Smarts: If you give it a Google Gemini API key in the config.ini, users can chat with the AI via Private Message (c <question>) or in the bot's channel (/c <question>). You can toggle these features. It can even do AI-powered welcome messages!

Weather Checks: Pop in an OpenWeatherMap API key, and users can get weather updates via PM (w <location>) or in the channel (/w <location>).

Fun Stuff like Polls: Create simple polls (!poll), let users vote (!vote), and see the results (!results).

Word Filter: Define a list of words in the config, and the bot can warn/kick users in its channel for using them. Can be toggled on/off (!tfilter).

Admin Superpowers: Lots of commands for admins (defined in the config) like restarting the bot, changing its nickname/status (which get saved!), moving/kicking/banning users, blocking specific commands, locking the bot, managing the filter list, and more. Use h in PM for the full list!

Join/Leave Announcements: Optionally announce when users join or leave the bot's channel (toggle with jcl admin command).

It Tries to Reconnect: If the connection drops, it'll wait a random short time and try to get back online automatically.

Config File Driven: Uses config.ini to store server details, API keys, admin names, etc. If it's missing on first run, a GUI setup window pops up!

What You'll Need (The Requirements)

Python 3: Needs a reasonably modern Python 3 installation.

TeamTalk 5 SDK: You MUST have the TeamTalk5.py wrapper file (from the TeamTalk SDK) in the same directory as NewTeamTalkBot.py. This bot won't work without it.

Python Libraries: You need to install a few libraries. Open your terminal or command prompt and run:

pip install requests google-generativeai wxPython


requests: For the weather feature.

google-generativeai: For the Gemini AI features.

wxPython: For the GUI window.

Getting Started (How to Run It)

Make sure you have Python 3 installed.

Place NewTeamTalkBot.py and TeamTalk5.py in the same folder.

Install the required libraries using the pip install ... command above.

Run the script from your terminal:

python NewTeamTalkBot.py

First Time? If config.ini doesn't exist, a setup window will appear. Fill in your server details (host, port), the bot's account details (username, password), the nickname you want the bot to use, and optionally any admin usernames (comma-separated), your Gemini API key, and your OpenWeatherMap API key.

Note: API keys are optional, but the AI and Weather features won't work without them!

Click "Save and Connect". This creates config.ini.

Already Configured? If config.ini exists, the bot will try to connect using those settings, and the main GUI window will appear.

Talking to the Bot

Private Message (PM): Send the bot a PM. Start with h to see the list of available commands.

In the Channel: If the features are enabled, you can use /c <question> for AI or /w <location> for weather directly in the channel the bot is in.

Use the GUI: The main window shows logs, lets you toggle features (like Gemini PM/Channel access, Broadcasts, etc.) by double-clicking, and has input boxes to send messages as the bot.

The config.ini File

This file stores all your settings. You can edit it manually if you need to, but the initial GUI setup and some admin commands (cn, cs, gapi, !filter) can update parts of it automatically.

Just a Heads-Up

This is still kind of a personal project. There might be bugs!

AI helped a lot with the coding, especially the GUI and threading bits, but I've tried to test things out.

Make sure the bot has the necessary rights on the TeamTalk server to do things like send channel messages, broadcasts, kick/ban, etc., if you want to use those admin commands. Check its rights with the rights PM command.

Hope it's useful or at least interesting! :)
