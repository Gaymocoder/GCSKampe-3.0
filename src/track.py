from .audio_data import AudioData
from .extras import SourceType, FFMPEG_OPTIONS

import discord
from discord import FFmpegOpusAudio

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

    
    @property
    def shortAudioURL(self):
        return self._data['shortmp3']


    def startedEmbed(self):
        description = f'Started playing: [**{self.title}**]({self.link})'
        embed = discord.Embed(color = discord.Colour.from_str('#000001'), description = description)
        return embed


    @classmethod
    def addingFirstEmbed(cls):
        return discord.Embed(description = '**Adding track to the queue...**', color = discord.Colour.from_str('#000001'))


    def gettingMetadataEmbed(self):
        return discord.Embed(description = '**Adding track to the queue: getting metadata...**', color = discord.Colour.from_str('#000001'))

    
    def addingFinalEmbed(self):
        return discord.Embed(description = f'**Adding track to the queue: `{self.title}`...**', color = discord.Colour.from_str('#000001'))


    def audio(self):
        return FFmpegOpusAudio(self.audioURL, **FFMPEG_OPTIONS, executable = "ffmpeg.exe")