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


async def addTrackFromAtts(message):
    localQueue = []
    mes = ''
    for att in message.attachments:
        if att.url.find('.mp3') == -1:
            continue
        localQueue.append({ 'guild': message.guild.id,
                            'channel': message.channel.id,
                            'message': message.id,
                            'attachment': att.id})
        mes += f'Added track: {att.url}\n'
    await message.channel.send(mes)
    return localQueue
    

class MusicKampe(discord.ext.commands.Bot):
    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.initCommands()
        self.queue = []
        self.loading = {}
        self.playing = False
        self.voiceState = None
        self.channelLog = None
        self.queuePosition = 0


    async def getAttUrl(self, attAddress):
        channel = await self.fetch_channel(attAddress['channel'])
        message = await channel.fetch_message(attAddress['message'])
        for attachment in message.attachments:
            if attachment.id == attAddress['attachment']:
                return attachment.url
        return None


    async def getTrackUrl(self, trackInfo):
        if type(trackInfo) == dict:
            return await self.getAttUrl(trackInfo)
        return trackInfo


    async def launchQueue(self, ctx):
        while (self.queuePosition < len(self.queue)):
            currentTrack = await self.getTrackUrl(self.queue[self.queuePosition])
            await ctx.send(f'Started playing {currentTrack}')
            self.voiceState.play(FFmpegPCMAudio(currentTrack, executable= "ffmpeg.exe"))
            while (self.voiceState.is_playing() or self.voiceState.is_paused()):
                await asyncio.sleep(0.5)
            self.queuePosition += 1


    async def playTracks(self, ctx):
        if (self.voiceState == None):
            self.voiceState = await ctx.author.voice.channel.connect()
        if not (self.voiceState.is_playing() or self.voiceState.is_paused()):
            await self.launchQueue(ctx)
            await ctx.send("I've reached the end of the queue")


    async def on_message(self, message):
        if (message.author.id not in self.loading):
            return
        if (self.loading[message.author.id] != message.guild.id):
            return
        if (len(message.attachments) == 0):
            return
        localQueue = await addTrackFromAtts(message)
        self.queue.extend(localQueue)


    def initCommands(self):

        @self.command()
        async def play(ctx, musicSource : str):
            print("PLAY COMMAND EXECUTED")
            if ctx.author.voice == None:
                await ctx.send('You\'re not in voice channel')
                return
            if self.voiceState == None:
                self.voiceState = await ctx.author.voice.channel.connect()
            if musicSource.startswith('https://www.youtube.com/') or musicSource.startswith('https://youtu.be/'):
                self.queue.append(getYouTubeAudioUrl(musicSource))
            elif musicSource.endswith('.mp3'):
                self.queue.append(musicSource)
            else:
                await ctx.send('Wrong url: either direct mp3 or youtube')
                return
            await ctx.send(f'Added to queue: {musicSource}')
            await self.playTracks(ctx)
            

        @self.command()
        async def load(ctx):
            if (ctx.author.id in self.loading and self.loading[ctx.author.id] == ctx.guild.id):
                await ctx.send(f'{ctx.author.mention}, you have already opened loading in this server')
            self.loading[ctx.author.id] = ctx.guild.id
            await ctx.send('Send files, i\'ll add them to my queue')


        @self.command()
        async def stopload(ctx):
            if (ctx.author.id not in self.loading or self.loading[ctx.author.id] != ctx.guild.id):
                await ctx.send(f'{ctx.author.mention}, you have not opened loading yet')
                return

            self.loading.pop(ctx.author.id)
            await ctx.send(f'{ctx.author.mention}, loading stream has been closed')
            await self.playTracks(ctx)