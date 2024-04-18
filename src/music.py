import sys
import enum
import json
import time
import asyncio
import logging

import discord
from discord import FFmpegOpusAudio
from discord.ext import commands
from yt_dlp import YoutubeDL

from urllib import request
from functools import reduce
from io import BytesIO
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3
from logging import debug as DEBUG, info as INFO


FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}


def isConnected(member):
    return (member.voice != None and member.voice.channel != None)


def getURLBytes(url, size):
    req = request.Request(url)
    req.add_header('Range', f'bytes={0}-{size-1}')
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11')
    response = request.urlopen(req)
    return response.read()


class SourceType(enum.Enum):
    URL = 0
    YOUTUBE = 1
    DISCORDATT = 2


class AudioData:
    def __init__(self, srcAddress, bot, message, srcType = SourceType.URL):
        self.srcType = srcType
        self.message = message
        self.__srcAddress = srcAddress
        self.__bot = bot
        self._data = {}


    def __await__(self):
        return self.__getData().__await__()


    def __getYoutubeData(self):
        ydlOptions = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }]
        }
        return YoutubeDL(ydlOptions).extract_info(self.__srcAddress, download = False)

    
    def __processYoutubeData(self, data):
        self._data['title'] = data['fulltitle']
        self._data['author'] = data['uploader']
        self._data['thumbnail'] = data['thumbnail']
        self._data['url'] = data['original_url']
        self._data['mp3'] = data['url']


    async def __getURLData(self):
        data = getURLBytes(await self.source(), 10)
        if data[0:3] != b'ID3':
            raise Exception('ID3 not in front of mp3 file')
        size = reduce(lambda a,b: a*128 + b, bytearray(data[-4:]), 0)

        header = BytesIO()
        data = getURLBytes(await self.source(), size + 2881)
        header.write(data)
        header.seek(0)
        return MP3(header, ID3 = EasyID3).tags


    async def __processURLData(self, data):
        self._data['title'] = data['title'][0]
        self._data['author'] = data['artist'][0]
        self._data['thumbnail'] = None
        self._data['url'] = await self.source()
        self._data['mp3'] = self._data['url']


    async def __getData(self):
        asyncio.create_task(self.message.edit(content = 'Adding new track to the queue: getting metadata...'))
        match self.srcType:
            case SourceType.URL:
                await self.__processURLData(await self.__getURLData())
            case SourceType.DISCORDATT:
                await self.__processURLData(await self.__getURLData())
            case SourceType.YOUTUBE:
                self.__processYoutubeData(self.__getYoutubeData())
        asyncio.create_task(self.message.edit(content = f'Adding new track to the queue: {self._data["title"]}'))
        return self


    async def __getDiscordAttURL(self):
        channel = await self.__bot.fetch_channel(self.__srcAddress['channel'])
        message = await channel.fetch_message(self.__srcAddress['message'])
        for attachment in message.attachments:
            if attachment.id == self.__srcAddress['attachment']:
                return attachment.url
        return None


    async def source(self):
        if 'url' in self._data:
            return self._data['url']

        match self.srcType:
            case SourceType.URL:
                return self.__srcAddress
            case SourceType.YOUTUBE:
                return self.__getYoutubeAudioURL()
            case SourceType.DISCORDATT:
                return await self.__getDiscordAttURL()


class Track(AudioData):
    def __init__(self, srcAddress, bot, message, srcType = SourceType.URL):
        super().__init__(srcAddress, bot, message, srcType = srcType)


    @property
    def title(self):
        return self._data['title']


    @property
    def author(self):
        return self._data['author']


    @property
    def link(self):
        return self._data['url']


    @property
    def audioURL(self):
        return self._data['mp3']


    def audio(self):
        return FFmpegOpusAudio(self.audioURL, **FFMPEG_OPTIONS, executable = "ffmpeg.exe")


class MusicSession:
    def __obliviate(self):
        self.queue = []
        self.loading = []
        self.rootMessage = None
        self.queuePosition = 0
        self.playing = False


    def __init__(self, voiceClient, rootMessage):
        self.__obliviate()
        self.voiceState = voiceClient
        self.rootMessage = rootMessage
        self.kicked = True
        self.moving = False
    

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


    async def disconnect(self):
        if self.is_connected():
            if self.voiceState.source != None:
                self.voiceState.source.cleanup()
            await self.voiceState.disconnect()
            self.voiceState.cleanup()
        self.__obliviate()


    async def waitToConnect(self):
        self.voiceState.pause()
        while (not self.is_connected()):
            await asyncio.sleep(0.5)
        self.voiceState.resume()


    async def updateConnectionData(self):
        self.voiceState = self.voiceState.guild.voice_client


    async def addTrack(self, track):
        self.queue.append(track)
        asyncio.create_task(self.playTracks())


    async def play(self):
        currentTrack = self.queue[self.queuePosition]
        audio = currentTrack.audio()
        self.voiceState.play(audio)
        await self.channelLog.send(f'Started playing `"{currentTrack.title}"`')


    async def waitTrackEnd(self):
        while (self.is_playing() or self.moving):
            if (self.moving):
                await self.waitToConnect()
                self.moving = False
                continue
            await asyncio.sleep(0.5)


    async def launchQueue(self):
        while (self.queuePosition < len(self.queue)):
            await self.play()
            await self.waitTrackEnd()
            if (not self.is_connected()):
                break
            self.queuePosition += 1


    async def playTracks(self):
        if (not self.is_connected()):
            self.voiceState = await self.author.voice.channel.connect()
        if (not self.playing):
            self.playing = True
            await self.launchQueue()
            self.playing = False
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
            audioSource = {
                'guild': message.guild.id,
                'channel': message.channel.id,
                'message': message.id,
                'attachment': att.id
            }
            
            trackMessage = await self.sessions[message.guild.id].channelLog.send(f'Adding new track to the queue...')
            track = await Track(audioSource, self, trackMessage, srcType = SourceType.DISCORDATT)
            await self.sessions[message.guild.id].addTrack(track)
            asyncio.create_task(trackMessage.edit(content = f'Added new track to the queue: "`{track.title}`"'))


    async def voiceConnect(self, voiceChannel, rootMessage):
        voiceState = await voiceChannel.connect()
        if voiceState != None:
            self.sessions[voiceChannel.guild.id] = MusicSession(voiceState, rootMessage)
            return self.sessions[voiceChannel.guild.id]

        print(f'Connection to voice channel "{voiceChannel.name}" (id: {voiceChannel.id}) failed')
        return False


    async def voiceDisconnect(self, guildId):
        if guildId in self.sessions:
            await self.sessions[guildId].disconnect()
            self.sessions.pop(guildId)
            return True
        else:
            print(f'Disconnection failed: no connection in guild "{(await self.fetch_guild(guildId)).name}" with id {guildId} is detected')
            return False

    
    async def startSession(self, ctx):
        connected = False
        if ctx.guild.id in self.sessions:
            return self.sessions[ctx.guild.id]

        if (isConnected(ctx.author)):
            connected = await self.voiceConnect(ctx.author.voice.channel, ctx.message)
        else:
            await ctx.send('You\'re not connected to voice channel')

        if (not connected):
            print('Cannot start new music session')

        return connected

        

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
            if before.channel != after.channel and before.channel != None:
                if after.channel == None:
                    if self.sessions[member.guild.id].kicked == True:
                        await self.sessions[member.guild.id].channelLog.send("I've been kicked from voice channel")
                        await self.voiceDisconnect(member.guild.id)
                    else:
                        self.sessions[member.guild.id].kicked = True
                else:
                    self.sessions[member.guild.id].moving = True
                    


    def initMusicCommands(self):

        @self.command()
        async def play(ctx, musicSource : str):
            currentSession = await self.startSession(ctx)
            if (not currentSession):
                return

            trackMessage = self.channelLog.send(f'Adding new track to the queue...')
            if musicSource.startswith('https://www.youtube.com/') or musicSource.startswith('https://youtu.be/'):
                track = await Track(musicSource, self, await trackMessage, srcType = SourceType.YOUTUBE)
                await self.sessions[ctx.guild.id].addTrack(track)
            elif musicSource.endswith('.mp3'):
                track = await Track(musicSource, self, await trackMessage, srcType = SourceType.URL)
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

            self.sessions[ctx.guild.id].loading.append(ctx.author.id)
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