from .music import *
import datetime
import json
import yt_dlp

class Kampe(MusicKampe):
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
    
    async def on_ready(self):
        self.Link = f'https://discord.com/api/oauth2/authorize?client_id={self.user.id}&permissions=8&scope=bot'
        print(f'{datetime.datetime.utcnow().strftime("[%d.%m.%Y %T UTC]")} Logged in as {self.user} (ID: {self.user.id})')
        print('~~~~~~~~~~~~~~~~~~~~~~~~~')

    async def on_message(self, message):
        if message.content.lower() == 'ping':
            await message.channel.send('Pong!')
        await super().on_message(message)
        await self.process_commands(message)