from .extras import SourceType
from .extras import shortURL, getURLBytes, getURLFileName

from io import BytesIO
from functools import reduce

from yt_dlp import YoutubeDL
from mutagen.mp3 import MP3
from mutagen.easyid3 import EasyID3

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
        self._data['shortmp3'] = shortURL(self._data['mp3'])


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
        self._data['shortmp3'] = shortURL(self._data['mp3'])

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