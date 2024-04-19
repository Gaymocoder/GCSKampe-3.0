import enum
import discord
import pyshorteners
import os, posixpath

from urllib import request
from urllib.parse import urlsplit, unquote


class SourceType(enum.Enum):
    URL = 0
    YOUTUBE = 1
    DISCORDATT = 2


FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}


def isConnected(member):
    return (member.voice != None and member.voice.channel != None)


def shortURL(url):
    return pyshorteners.Shortener().tinyurl.short(url)


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


async def sendSuccess(ctx, success):
    return await ctx.send(embed = discord.Embed(color = discord.Colour.from_str("#00FF00"), description = success))
        

async def sendWarning(ctx, warning):
    return await ctx.send(embed = discord.Embed(color = discord.Colour.from_str("#FFFF00"), description = warning))


async def sendError(ctx, error):
    return await ctx.send(embed = discord.Embed(color = discord.Colour.from_str("#FF0000"), description = error))


async def sendMessage(ctx, message):
    return await ctx.send(embed = discord.Embed(color = discord.Colour.from_str("#000001"), description = message))