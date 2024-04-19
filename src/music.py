import sys
import enum
import json
import time
import asyncio
import logging
import os, posixpath

import discord
import pyshorteners
from discord import FFmpegOpusAudio
from discord.ext import commands
from yt_dlp import YoutubeDL

from urllib import request
from urllib.parse import urlsplit, unquote
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


def shortURL(url):
    return pyshorteners.Shortener().dagd.short(url)


def getURLBytes(url, size):
    req = request.Request(url)
    req.add_header('Range', f'bytes={0}-{size-1}')
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'Mozilla/5.0 (X11; U; Linux i686) Gecko/20071127 Firefox/2.0.0.11')
    response = request.urlopen(req)
    return response.read()


def getURLFileName(url):
    urlpath = urlsplit(url).path
    basename = posixpath.basename(unquote(urlpath))
    if (os.path.basename(basename) != basename or unquote(posixpath.basename(urlpath)) != basename):
        raise ValueError
    return basename


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
        self._data['length'] = 'live'
        self._data['url'] = data['original_url']
        self._data['mp3'] = data['url']
        if not data['is_live']:
            self._data['length'] = data['duration_string']


    async def __getURLData(self):
        data = getURLBytes(await self.source(), 10)
        if data[0:3] != b'ID3':
            raise Exception('ID3 not in front of mp3 file')
        size = reduce(lambda a,b: a*128 + b, bytearray(data[-4:]), 0)

        header = BytesIO()
        data = getURLBytes(await self.source(), size + 2881)
        header.write(data)
        header.seek(0)
        return MP3(header, ID3 = EasyID3)


    async def __processURLData(self, mp3):
        data = mp3.tags
        self._data['url'] = await self.source()
        self._data['title'] = getURLFileName(self._data['url'])
        self._data['author'] = None
        self._data['length'] = f'{int(int(mp3.info.length) / 60):02}:{(int(mp3.info.length) % 60):02}'
        self._data['thumbnail'] = None
        self._data['mp3'] = self._data['url']

        if 'title' in data:
            self._data['title'] = data['title'][0]
        if 'author' in data:
            self._data['author'] = data['artist'][0]


    async def __getData(self):
        if self.__class__.__name__ == 'Track':
            await self.message.edit(embed = self.gettingMetadataEmbed())
        match self.srcType:
            case SourceType.URL:
                await self.__processURLData(await self.__getURLData())
            case SourceType.DISCORDATT:
                await self.__processURLData(await self.__getURLData())
            case SourceType.YOUTUBE:
                self.__processYoutubeData(self.__getYoutubeData())
        if self.__class__.__name__ == 'Track':
            await self.message.edit(embed = self.addingFinalEmbed())
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
    def length(self):
        return self._data['length']


    @property
    def link(self):
        return self._data['url']


    @property
    def audioURL(self):
        return self._data['mp3']


    def startedEmbed(self):
        description = f'Started playing: [**{self.title}**]({self.link})'
        embed = discord.Embed(color = discord.Colour, description = description)
        return embed


    @classmethod
    def addingFirstEmbed(self):
        return discord.Embed(description = 'Adding track to the queue...', color = discord.Colour.from_str('#000001'))


    def gettingMetadataEmbed(self):
        return discord.Embed(description = 'Adding track to the queue: getting metadata...', color = discord.Colour.from_str('#000001'))

    
    def addingFinalEmbed(self):
        return discord.Embed(description = f'Adding track to the queue: `{self.title}`...', color = discord.Colour.from_str('#000001'))


    def audio(self):
        return FFmpegOpusAudio(self.audioURL, **FFMPEG_OPTIONS, executable = "ffmpeg.exe")


class MusicSession:
    def __obliviate(self):
        self.queue = []
        self.loading = []
        self.rootMessage = None
        self._queuePosition = 0
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

    @property
    def queuePosition(self):
        if self.queue == []:
            return 0
        return (self._queuePosition + 1)


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
        currentTrack = self.queue[self._queuePosition]
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
        while (self._queuePosition < len(self.queue)):
            await self.play()
            await self.waitTrackEnd()
            if (not self.is_connected()):
                break
            self._queuePosition += 1


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


    def addedEmbed(self, track, guildID, author):
        embed = discord.Embed(title = 'Added track', color = discord.Colour.from_str('#00FF00'))
        embed.add_field(name = 'Track', value = f'**[{track.title}]({track.link})**', inline = False)
        embed.add_field(name = 'Track length', value = track.length)
        embed.add_field(name = 'Download', value = f'{shortURL(track.audioURL)}')
        embed.add_field(name = '', value = '', inline = False)
        upcomingPosition = len(self.sessions[guildID].queue) - self.sessions[guildID].queuePosition
        upcomingPosition = 'current' if upcomingPosition == 0 else upcomingPosition
        embed.add_field(name = 'Position in upcoming', value = 'next' if upcomingPosition == 1 else str(upcomingPosition))
        embed.add_field(name = 'Position in queue', value = len(self.sessions[guildID].queue))
        embed.add_field(name = '', value = '', inline = False)
        embed.set_footer(text = f'requested by {author.display_name}', icon_url = author.display_avatar.url)
        return embed


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
            
            trackMessage = await self.sessions[message.guild.id].channelLog.send(embed = Track.addingFirstEmbed())
            track = await Track(audioSource, self, trackMessage, srcType = SourceType.DISCORDATT)
            await self.sessions[message.guild.id].addTrack(track)
            asyncio.create_task(trackMessage.edit(embed = self.addedEmbed(track, message.guild.id, message.author)))


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

            if musicSource.startswith('https://www.youtube.com/') or musicSource.startswith('https://youtu.be/'):
                trackMessage = await self.sessions[ctx.guild.id].channelLog.send(embed = Track.addingFirstEmbed())
                track = await Track(musicSource, self, trackMessage, srcType = SourceType.YOUTUBE)
                await self.sessions[ctx.guild.id].addTrack(track)
                await trackMessage.edit(embed = self.addedEmbed(track, ctx.guild.id, ctx.author))
            elif musicSource.endswith('.mp3'):
                trackMessage = await self.sessions[ctx.guild.id].channelLog.send(embed = Track.addingFirstEmbed())
                track = await Track(musicSource, self, trackMessage, srcType = SourceType.URL)
                await self.sessions[ctx.guild.id].addTrack(track)
                await trackMessage.edit(embed = self.addedEmbed(track, ctx.guild.id, ctx.author))
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
        async def queue(ctx):
            if ctx.guild.id not in self.sessions:
                await ctx.send(f'There\'s no opened session on this server')
                return

            messages = ['']
            for i, track in enumerate(self.sessions[ctx.guild.id].queue):
                new_line = f'{i + 1}. [{track.title}]({track.link})\n'
                if len(messages[-1] + new_line) > 2000:
                    messages.append('')
                messages[-1] += new_line
            for message in messages:
                print(message)
                await ctx.send(message)


        @self.command()
        async def stopload(ctx):
            if ctx.guild.id not in self.sessions:
                await ctx.send(f'There\'s no opened session on this server')
                return

            if (ctx.author.id not in self.sessions[ctx.guild.id].loading):
                await ctx.send(f'{ctx.author.mention}, you have not opened loading yet')
                return

            self.loading.pop(ctx.author.id)
            await ctx.send(f'{ctx.author.mention}, loading stream has been closed')


        @self.command()
        async def stop(ctx):
            if ctx.guild.id not in self.sessions:
                await ctx.send(f'There\'s no opened session on this server')
                return

            self.sessions[ctx.guild.id].kicked = False
            await self.voiceDisconnect(ctx.guild.id)
            await ctx.send("The music session for this guild has been closed")