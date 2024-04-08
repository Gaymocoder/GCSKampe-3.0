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
#### here()
Reacts on "k!here"
```
User: k!here
Bot: Yup, I'm here! Hello!
```