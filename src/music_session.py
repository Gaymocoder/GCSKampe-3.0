from .extras import sendMessage

import discord
import asyncio

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
        self.nexting = False
    

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


    def queueEmbed(self, position = None):
        description = ''
        if position == None:
            position = self._queuePosition
        for i in range(position, position + 10):
            if i >= len(self.queue):
                break
            track = self.queue[i]
            description += f'[:arrow_down:]({track.shortAudioURL}) {(i+1):02}. [**{track.title[:65] + ("...**" if len(track.title) > 65 else "**")}]({track.link})\n'
        embed = discord.Embed(description = description, color = discord.Colour.from_str('#000001'))
        embed.set_footer(text = f'{position+1}-{min(position + 10, len(self.queue))} from {len(self.queue)}')
        return embed


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
        await self.channelLog.send(embed = currentTrack.startedEmbed())


    async def waitTrackEnd(self):
        while (self.is_playing() or self.moving):
            if (self.moving):
                await self.waitToConnect()
                self.moving = False
                continue
            if (self.nexting):
                self.nexting = False
                break
            await asyncio.sleep(0.5)


    async def launchQueue(self):
        while (self._queuePosition < len(self.queue)):
            await self.play()
            await self.waitTrackEnd()
            self.voiceState.stop()
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
                await sendMessage(self.channelLog, "I've reached the end of the queue")