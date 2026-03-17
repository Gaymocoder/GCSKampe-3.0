# GCS Discord Kampe
Discord-bot with some functions like:
1. Music

## Installation
### Dependencies
1. Python 3.10.11
2. Modules: discord.py,
            pyshorteners,
            mutagen,
            yt_dlp,
            PyNaCl
3. ffmpeg
#### About discord.py
For the current moment (April 2024) latest discord.py release (2.3.2) doesn't provide proper handle of disconnection, raising exceptions which break the event loop, so it has to be installed right from github with pip-command:
```
pip install -U git+https://github.com/Rapptz/discord.py.git --force-reinstall
```

### Prepare to launch
1. Download the repository
```
git clone https://github.com/Gaymocoder/GCSKampe-3.0.git
cd GCSKampe-3.0
```
2. Change token in "tokens.json" to yours

### Launch
1. Launch the bot
```
python startKampe.py
```

## Documentation

### Reacts
#### Ping
On every "ping" bot answer's "pong"
```
User: Ping
Bot: Pong!
```

### Commands
The command prefix is "k!" by default

#### k!link
Bot sends a message with invite-link to himself
```
User: k!link
Bot: *link to invite the bot to your server*
```

#### k!play \<source>
Bot joins to voice chat, where command executor is, and starts playing audio from requested source
Supported source types:
1. YouTube (https://www.youtube.com/)
2. Direct mp3 file link
```
User: k!play https://youtu.be/4xDzrJKXOOY
Bot: Started playing "synthwave radio 🌌 - beats to chill/game to"
```

#### k!next
Bot turns on new track
```
User: k!next
Bot: Started playing "lofi hip hop radio 📚 - beats to relax/study to"
```

#### k!load
Bot starts waiting for your audio files right in the text channel as attachments. By the end execute command stopload
```
User: k!load
Bot: Send files, i\'ll add them to my queue
User: *sends music files*
User: k!stopload
Bot: *User mention*, loading stream has been closed
```

#### k!queue
Bot sends messages with full queue for current music session.
With "download" icon you can download the track (powered by TinyURL).
```
User: k!queue
Bot: ⬇1. synthwave radio 🌌 - beats to chill/game to
     ⬇2. lofi hip hop radio 📚 - beats to relax/study to
     ⬇3. dark ambient radio 🌃 - music to escape/dream to
     ⬇4. peaceful piano radio 🎹 - music to focus/study to
     ...
```

#### k!stopload
Check the [load](####k!load) command

#### k!stop
Closes current session
```
User: k!stop
Bot: *disconnects from voice channel and removes current session from his cache*
Bot: The music session for this guild has been closed
```