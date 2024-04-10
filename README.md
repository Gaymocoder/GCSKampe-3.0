# GCS Discord Kampe
Audio Control application with presets

## Installation
### Dependencies
1. Python 3.10.11
2. Modules: discord.py
            yt_dlp
            PyNaCl
3. ffmpeg

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
#### play <source>
Bot joins to voice chat, where command executor is, and starts playing audio from requested source
Supported source types:
1. YouTube (https://www.youtube.com/)
2. Direct mp3 file link
```
User: k!play https://youtu.be/4xDzrJKXOOY
Bot: Started playing *verylonglinkthroughgooglevideocomtosourceaudio*
```
#### load
Bot starts waiting for your audio files right in the text channel as attachments. By the end execute command stopload
```
User: k!load
Bot: Send files, i\'ll add them to my queue
User: *sends music files*
User: k!stopload
Bot: *User mention*, loading stream has been closed
```
#### stopload
Check the [load](####load) command