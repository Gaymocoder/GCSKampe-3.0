import discord
import asyncio

from .track import Track
from .music_session import MusicSession
from .extras import sendSuccess, sendError
from .extras import isConnected, SourceType
from .extras import sendWarning, sendMessage

from discord.ext import commands


class MusicKampe(discord.ext.commands.Bot):

    def __init__(self, *args, **kargs):
        super().__init__(*args, **kargs)
        self.sessions = {}
        self.initMusicCommands()


    def addedEmbed(self, track, guildID, author):
        upcomingPosition = len(self.sessions[guildID].queue) - self.sessions[guildID].queuePosition
        upcomingPosition = 'current' if upcomingPosition == 0 else upcomingPosition
        embed = discord.Embed(title = 'Added track', color = discord.Colour.from_str('#00FF00'))
        embed.add_field(name = 'Track', value = f'**[{track.title}]({track.link})**', inline = False)
        embed.add_field(name = 'Track length', value = track.length)
        embed.add_field(name = 'Download', value = f'{track.shortAudioURL}')
        embed.add_field(name = '', value = '', inline = False)
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
            self.sessions[message.guild.id].addingTracks.append(trackMessage.id)
            while self.sessions[message.guild.id].addingTracks[0] != trackMessage.id:
                await asyncio.sleep(0.5)
            await asyncio.sleep(2)
            track = await Track(audioSource, self, trackMessage, srcType = SourceType.DISCORDATT)
            await self.sessions[message.guild.id].addTrack(track)
            asyncio.create_task(trackMessage.edit(embed = self.addedEmbed(track, message.guild.id, message.author)))
            self.sessions[message.guild.id].addingTracks.pop(0)


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
            await sendWarning(ctx, 'You\'re not connected to voice channel')

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
                        await sendError(self.sessions[member.guild.id].channelLog, "I've been kicked from voice channel")
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
                self.sessions[ctx.guild.id].addingTracks.append(trackMessage.id)
                while self.sessions[ctx.guild.id].addingTracks[0] != trackMessage.id:
                    await asyncio.sleep(0.5)
                track = await Track(musicSource, self, trackMessage, srcType = SourceType.YOUTUBE)
                await self.sessions[ctx.guild.id].addTrack(track)
                await trackMessage.edit(embed = self.addedEmbed(track, ctx.guild.id, ctx.author))
                self.sessions[ctx.guild.id].addingTracks.pop(0)
            elif musicSource.endswith('.mp3'):
                trackMessage = await self.sessions[ctx.guild.id].channelLog.send(embed = Track.addingFirstEmbed())
                self.sessions[ctx.guild.id].addingTracks.append(trackMessage.id)
                while self.sessions[ctx.guild.id].addingTracks[0] != trackMessage.id:
                    await asyncio.sleep(0.5)
                track = await Track(musicSource, self, trackMessage, srcType = SourceType.URL)
                await self.sessions[ctx.guild.id].addTrack(track)
                await trackMessage.edit(embed = self.addedEmbed(track, ctx.guild.id, ctx.author))
                self.sessions[ctx.guild.id].addingTracks.pop(0)
            else:
                await sendError(ctx, 'Wrong url: either direct mp3 or youtube')
                return
            

        @self.command()
        async def load(ctx):
            currentSession = await self.startSession(ctx)
            if (not currentSession):
                return

            if (ctx.author.id in self.sessions[ctx.guild.id].loading):
                return await sendWarning(ctx, f'{ctx.author.mention}, you have already opened loading in this server')

            self.sessions[ctx.guild.id].loading.append(ctx.author.id)
            await sendMessage(ctx, 'Send files, i\'ll add them to my queue')


        @self.command()
        async def next(ctx):
            if ctx.guild.id not in self.sessions:
                return await sendError(ctx, f'There\'s no opened session on this server')
            self.sessions[ctx.guild.id].nexting = True


        @self.command()
        async def queue(ctx):
            if ctx.guild.id not in self.sessions:
                return await sendError(ctx, f'There\'s no opened session on this server')

            embed = self.sessions[ctx.guild.id].queueEmbed()
            await ctx.send(embed = embed)


        @self.command()
        async def stopload(ctx):
            if ctx.guild.id not in self.sessions:
                return await sendWarning(ctx, f'There\'s no opened session on this server')

            if (ctx.author.id not in self.sessions[ctx.guild.id].loading):
                return await sendWarning(ctx, f'{ctx.author.mention}, you have not opened loading yet')

            self.sessions[ctx.guild.id].loading.remove(ctx.author.id)
            await sendSuccess(ctx, f'{ctx.author.mention}, loading stream has been closed')


        @self.command()
        async def stop(ctx):
            if ctx.guild.id not in self.sessions:
                return await sendWarning(ctx, f'There\'s no opened session on this server')

            self.sessions[ctx.guild.id].kicked = False
            await self.voiceDisconnect(ctx.guild.id)
            await sendSuccess(ctx, "The music session for this guild has been closed")