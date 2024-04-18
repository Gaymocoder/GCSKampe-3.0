import src as kampe

import json
import discord

tokens = json.loads(open('ttokens.json', encoding = 'utf').read())

kampe = kampe.Kampe(intents = discord.Intents.all(), command_prefix = 'k!')
kampe.run(tokens["kampe 3.0"])