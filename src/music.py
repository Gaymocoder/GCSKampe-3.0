import discord
from discord import FFmpegPCMAudio
from discord.ext import commands
from yt_dlp import YoutubeDL
import asyncio
import enum
import json


class SourceType(enum.Enum):
    URL = 0
    YOUTUBE = 1
    DISCORDATT = 2


class Track():
    def __init__(self, srcAddress, bot, srcType = SourceType.URL):
        self.srcType = srcType
        self.__srcAddress = srcAddress
        self.__bot = bot

    async def __getDiscordAttUrl(self):
        channel = await self.__bot.fetch_channel(self.__srcAddress['channel'])
        message = await channel.fetch_message(self.__srcAddress['message'])
        for attachment in message.attachments:
            if attachment.id == self.__srcAddress['attachment']:
                return attachment.url
        return None

    def __getYoutubeAudioURL(self):
        ydlOptions = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }]
        }
        data = YoutubeDL(ydlOptions).extract_info(self.__srcAddress, download = False)
        print(json.dumps(data, indent = 4,  ensure_ascii = False))
        return data['url']


    async def link(self):
        match self.srcType:
            case SourceType.URL:
                return self.__srcAddress
            case SourceType.YOUTUBE:
                return self.__getYoutubeAudioURL()
            case SourceType.DISCORDATT:
                return await self.__getDiscordAttURL()

    
    async def source(self):
        if self.srcType == SourceType.DISCORDATT:
            return await self.link()
        return self.__srcAddress


    def data(self):
        pass

        
    async def audio(self):
        return FFmpegPCMAudio(await self.link(), executable= "ffmpeg.exe")


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


    async def musicConnect(self, voice):
        if self.voiceState != None:
            return True
        if voice != None:
            self.voiceState = await voice.channel.connect()
            return True
        else:
            await self.channelLog.send('You\'re not in voice channel')
            self.channelLog = None
            return False


    async def addTrack(self, track, voice = None):
        await self.musicConnect(voice)
        self.queue.append(track)
        await self.channelLog.send(f'Added to queue: {await self.queue[-1].source()}')
        await self.playTracks()


    async def launchQueue(self):
        while (self.queuePosition < len(self.queue)):
            currentTrack = self.queue[self.queuePosition]
            await self.channelLog.send(f'Started playing {await currentTrack.source()}')
            self.voiceState.play(await currentTrack.audio())
            while (self.voiceState.is_playing() or self.voiceState.is_paused()):
                await asyncio.sleep(0.5)
            self.queuePosition += 1


    async def playTracks(self):
        if (self.voiceState == None):
            self.voiceState = await self.channelLog.author.voice.channel.connect()
        if not (self.voiceState.is_playing() or self.voiceState.is_paused()):
            await self.launchQueue()
            await self.channelLog.send("I've reached the end of the queue")


    async def addTracksFromAtts(message):
        for att in message.attachments:
            if att.url.find('.mp3') == -1:
                continue
            audioSource = {'guild': message.guild.id,
                'channel': message.channel.id,
                'message': message.id,
                'attachment': att.id}
            await self.addTrack(Track(audioSource, self, srcType = SourceType.DISCORDATT), voice = message.author.voice)


    async def on_message(self, message):
        if (message.author.id not in self.loading):
            return
        if (self.loading[message.author.id] != message.guild.id):
            return
        if (message.attachments == []):
            return
        await self.addTracksFromAtts(message)


    def initCommands(self):

        @self.command()
        async def play(ctx, musicSource : str):
            print("PLAY COMMAND EXECUTED")
            if self.channelLog == None:
                self.channelLog = ctx.channel
            if not (await self.musicConnect(ctx.author.voice)):
                return
            if musicSource.startswith('https://www.youtube.com/') or musicSource.startswith('https://youtu.be/'):
                await self.addTrack(Track(musicSource, self, srcType = SourceType.YOUTUBE), voice = ctx.author.voice)
            elif musicSource.endswith('.mp3'):
                await self.addTrack(Track(musicSource, self, srcType = SourceType.URL), voice = ctx.author.voice)
            else:
                await ctx.send('Wrong url: either direct mp3 or youtube')
                return
            
            await self.playTracks()
            

        @self.command()
        async def load(ctx):
            if (ctx.author.id in self.loading and self.loading[ctx.author.id] == ctx.guild.id):
                await ctx.send(f'{ctx.author.mention}, you have already opened loading in this server')
                return
            self.loading[ctx.author.id] = ctx.guild.id
            await ctx.send('Send files, i\'ll add them to my queue')


        @self.command()
        async def stopload(ctx):
            if (ctx.author.id not in self.loading or self.loading[ctx.author.id] != ctx.guild.id):
                await ctx.send(f'{ctx.author.mention}, you have not opened loading yet')
                return
            self.loading.pop(ctx.author.id)
            await ctx.send(f'{ctx.author.mention}, loading stream has been closed')