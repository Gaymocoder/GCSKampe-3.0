import discord
from discord import FFmpegOpusAudio
from discord.ext import commands
from yt_dlp import YoutubeDL
import asyncio
import enum
import json


def isConnected(member):
    return (member.voice != None and member.voice.channel != None)


class SourceType(enum.Enum):
    URL = 0
    YOUTUBE = 1
    DISCORDATT = 2


class Track:
    def __init__(self, srcAddress, bot, srcType = SourceType.URL):
        self.srcType = srcType
        self.__srcAddress = srcAddress
        self.__bot = bot


    async def __getDiscordAttURL(self):
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
        return FFmpegOpusAudio(await self.link(), executable= "ffmpeg.exe")


class MusicSession:
    def __obliviate(self):
        self.queue = []
        self.loading = []
        self.rootMessage = None
        self.queuePosition = 0


    async def disconnect(self):
        if self.is_connected():
            if self.voiceState.source != None:
                self.voiceState.source.cleanup()
            await self.voiceState.disconnect()
            self.voiceState.cleanup()
        self.__obliviate()


    def __init__(self, voiceClient, rootMessage):
        self.__obliviate()
        self.voiceState = voiceClient
        self.rootMessage = rootMessage
        self.kicked = True
    

    @property
    def channelLog(self):
        if self.rootMessage == None:
            return None
        return self.rootMessage.channel


    @property
    def author(self):
        if self.rootMessage == None:
            return None
        return self.rootMessage.author


    def is_connected(self):
        return (self.voiceState != None and self.voiceState.channel != None and self.voiceState.is_connected())


    def is_playing(self):
        return (self.voiceState != None and (self.voiceState.is_playing() or self.voiceState.is_paused()))


    async def addTrack(self, track):
        self.queue.append(track)
        await self.channelLog.send(f'Added to queue: {await self.queue[-1].source()}')
        await self.playTracks()


    async def launchQueue(self):
        print(self.queuePosition, self.queue)
        while (self.queuePosition < len(self.queue)):
            currentTrack = self.queue[self.queuePosition]
            audio = await currentTrack.audio()
            self.voiceState.play(audio)
            await self.channelLog.send(f'Started playing {await currentTrack.source()}')
            
            while (self.is_playing()):
                await asyncio.sleep(0.5)
            if (self.is_connected()):
                self.queuePosition += 1
            else:
                break


    async def playTracks(self):
        if (not self.is_connected()):
            self.voiceState = await self.sessionAuthor.voice.channel.connect()
        if not (self.is_playing()):
            await self.launchQueue()
            if (self.is_connected()):
                await self.channelLog.send("I've reached the end of the queue")


class MusicKampe(discord.ext.commands.Bot):

    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.sessions = {}
        self.initMusicCommands()


    async def addTracksFromAtts(self, message):
        for att in message.attachments:
            if att.url.find('.mp3') == -1:
                continue
            audioSource = {'guild': message.guild.id,
                'channel': message.channel.id,
                'message': message.id,
                'attachment': att.id}
            track = Track(audioSource, self, srcType = SourceType.DISCORDATT)
            await self.sessions[message.guild.id].addTrack(track)


    async def voiceConnect(self, voiceChannel, rootMessage):
        voiceState = await voiceChannel.connect()
        if voiceState != None:
            self.sessions[voiceChannel.guild.id] = MusicSession(voiceState, rootMessage)
            return self.sessions[voiceChannel.guild.id]

        print(f'Connection to voice channel "{voiceChannel.name}" (id: {voiceChannel.id}) failed')
        return False


    async def voiceDisconnect(self, guildId):
        if guildId in self.sessions:
            print(guildId)
            await self.sessions[guildId].disconnect()
            print(self.sessions)
            self.sessions.pop(guildId)
            print(self.sessions)
            return True
        else:
            print(f'Disconnection failed: no connection in guild "{(await self.fetch_guild(guildId)).name}" with id {guildId} is detected')
            return False

    
    async def startSession(self, ctx):
        connected = False
        print(self.sessions)
        if ctx.guild.id not in self.sessions:
            if (isConnected(ctx.author)):
                connected = await self.voiceConnect(ctx.author.voice.channel, ctx.message)
            else:
                await ctx.send('You\'re not connected to voice channel')

        if (not connected):
            print('Cannot start new music session')
            return False

        return self.sessions[ctx.guild.id]

        

    async def on_message(self, message):
        if (message.guild.id not in self.sessions):
            return
        if (message.author.id not in self.sessions[message.guild.id].loading):
            return
        if (message.attachments == []):
            return
        await self.addTracksFromAtts(message)


    async def on_voice_state_update(self, member, before, after):
        if member.id == self.user.id:
            if before.channel != None and after.channel == None:
                if self.sessions[member.guild.id].kicked == True:
                    await self.channelLog.send("I've been kicked from voice channel")
                    self.voiceDisconnect(member.guild.id)
                else:
                    self.sessions[member.guild.id].kicked = True


    def initMusicCommands(self):

        @self.command()
        async def play(ctx, musicSource : str):
            currentSession = await self.startSession(ctx)
            if (not currentSession):
                return

            if musicSource.startswith('https://www.youtube.com/') or musicSource.startswith('https://youtu.be/'):
                track = Track(musicSource, self, srcType = SourceType.YOUTUBE)
                await self.sessions[ctx.guild.id].addTrack(track)
            elif musicSource.endswith('.mp3'):
                track = Track(musicSource, self, srcType = SourceType.URL)
                await currentSession.addTrack(track)
            else:
                await ctx.send('Wrong url: either direct mp3 or youtube')
                return
            

        @self.command()
        async def load(ctx):
            currentSession = await self.startSession(ctx)
            if (not currentSession):
                return

            if (ctx.author.id in self.sessions[ctx.guild.id].loading):
                await ctx.send(f'{ctx.author.mention}, you have already opened loading in this server')
                return

            self.sessions[ctx.guild.id].loading.append(ctx.guild.id)
            await ctx.send('Send files, i\'ll add them to my queue')


        @self.command()
        async def stopload(ctx):
            currentSession = await self.startSession(ctx)
            if (not currentSession):
                return

            if (ctx.author.id not in self.sessions[ctx.guild.id].loading):
                await ctx.send(f'{ctx.author.mention}, you have not opened loading yet')
                return

            self.loading.pop(ctx.author.id)
            await ctx.send(f'{ctx.author.mention}, loading stream has been closed')


        @self.command()
        async def stop(ctx):
            if ctx.guild.id not in self.sessions:
                await ctx.send("You're not in voice channel")
            else:
                self.sessions[ctx.guild.id].kicked = False
                await self.voiceDisconnect(ctx.guild.id)