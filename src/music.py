import discord
from discord import FFmpegPCMAudio
from discord.ext import commands
from yt_dlp import YoutubeDL
import asyncio

def getYouTubeAudioUrl(url):
    ydlOptions = {
        'format': 'bestaudio/best',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }]
    }
    data = YoutubeDL(ydlOptions).extract_info(url, download = False)
    return data['url']


def addTrackFromAtts(message):
    localQueue = []
    mes = ''
    for att in message.attachments:
        if att.url.find('.mp3') == -1:
            continue
        localQueue.append({
            'guild': message.guild.id,
            'channel': message.channel.id,
            'message': message.id,
            'attachment': att.id})
        mes += f'Added track: {att.url}\n'
    return mes, localQueue
    

class MusicKampe(discord.ext.commands.Bot):
    def __init__(self, *args, **kargs):
        self.queue = []
        self.loading = {}
        self.vc = None
        self.queuePosition = -1
        self.playing = False
        super().__init__(*args, **kargs)
        self.initCommands()

    async def getAttUrl(self, attAddress):
        channel = await self.fetch_channel(attAddress['channel'])
        message = await channel.fetch_message(attAddress['message'])
        for att in message.attachments:
            if att.id == attAddress['attachment']:
                return att.url

    async def playTracks(self, ctx):
        if self.vc == None:
            self.vc = await ctx.author.voice.channel.connect()
        if self.vc.is_playing():
            return
        if self.queuePosition == -1:
            self.queuePosition = 0
        while len(self.queue) >= self.queuePosition + 1:
            if type(self.queue[self.queuePosition]) == dict:
                self.vc.play(FFmpegPCMAudio(await self.getAttUrl(self.queue[self.queuePosition]), executable= "ffmpeg.exe"))
            else:
                self.vc.play(FFmpegPCMAudio(self.queue[self.queuePosition], executable= "ffmpeg.exe"))
            while (self.vc.is_playing()):
                await asyncio.sleep(0.5)
            self.queuePosition += 1
        await ctx.send("I've reached the end of the queue")

    async def on_message(self, message):
        try:
            if (self.loading[message.author.id] == message.guild.id):
                if len(message.attachments) == 0:
                    return
                answer, localQueue = addTrackFromAtts(message)
                await message.channel.send(answer)
                self.queue.extend(localQueue)
        except KeyError:
            pass

    def initCommands(self):

        @self.command()
        async def play(ctx, musicSource : str):
            print("PLAY COMMAND EXECUTED")
            if ctx.author.voice == None:
                await ctx.send('You\'re not in voice channel')
                return
            if self.vc == None:
                self.vc = await ctx.author.voice.channel.connect()
            if musicSource.startswith('https://www.youtube.com/'):
                self.queue.append(getYouTubeAudioUrl(musicSource))
            elif musicSource.endswith('.mp3'):
                self.queue.append(musicSource)
            else:
                await ctx.send('Wrong url: either direct mp3 or youtube')
            await self.playTracks(ctx)
            

        @self.command()
        async def load(ctx):
            try:
                self.loading[ctx.author.id]
                await ctx.send(f'{ctx.author.mention}, you have already opened loading in another channel')
            except KeyError:
                pass
            self.loading[ctx.author.id] = ctx.guild.id
            await ctx.send('Send files, i\'ll add them to my queue')

        @self.command()
        async def stopload(ctx):
            try:
                if (self.loading[ctx.author.id] != ctx.guild.id):
                    await ctx.send(f'{ctx.author.mention}, you have not opened loading yet')
                    return
                self.loading.pop(ctx.author.id)
                await ctx.send(f'{ctx.author.mention}, loading stream has been closed')
                await self.playTracks(ctx)
            except KeyError:
                await ctx.send(f'{ctx.author.mention}, you have not opened loading yet')