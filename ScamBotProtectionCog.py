from datetime import datetime
from difflib import SequenceMatcher
from io import BytesIO
import discord
from discord import Embed
from utils.dataIO import fileIO
from discord.ext import commands
import discord.ext.commands.context
import utils.checks as checks
from PIL import Image
import imagehash
import requests
import asyncio
import sharedBot
import unicodedata
import re
import enchant

class ScamBotProtection(commands.Cog):

    scamBotFilter = ["rl", "giveaway", "giveaways", "gift", "administration", "rltracker", "psyonix", "PSYONIX", "gifts", "g1fts", "quickselling", "gamersrdy", "rltracker","rlgarage", "rewards", "prizes"]

    imagesHashes = [
        imagehash.average_hash(Image.open('data/scambot_protection/psyonix-transparent.png')),
        imagehash.average_hash(Image.open('data/scambot_protection/psyonix.jpg')),
        imagehash.average_hash(Image.open('data/scambot_protection/1.jpg')),
        imagehash.average_hash(Image.open('data/scambot_protection/2.jpg')),
        imagehash.average_hash(Image.open('data/scambot_protection/3.png')),
        imagehash.average_hash(Image.open('data/scambot_protection/4.png')),
        imagehash.average_hash(Image.open('data/scambot_protection/6.jpg'))
    ] #Add extra images to this list
    Dictionary = enchant.Dict("en_US")

    #Define an owner guild for Debug messages and extra info (it's the bot owner's guild)
    ownerGuildID = "371935977196879872"

    regexPatterns = [
        "gift(?:s)?",
        "giveaway(?:s)?",
        "\bgift?",
        "qu(?:i|)ckselling",
        "psy(?:(?:0|o|))(?:ni|)x",
        "psy(?:.*)x",
        "rl(?: |_|-|)gara(?:s)?",
        "rl(?: |_|-|)(?:.*)tra(?:cke|de)(?:s)?",
        "rl(?: |_|-|)(?:.*)supp(?:s)?",
        "rl(?: |_|-|)(?:.*)prize(?:s)?"
        "rl(?: |_|-|)(?:.*)mod(?:s)?",
        "rl(?: |_|-|)(?:.*)hel(?:s)?",
        "rl(?: |_|-|)(?:.*)rew(?:.*)?",
        "rl(?: |_|-|)(?:.*)ass(?:s)?",
        "rl(?: |_|-|)(?:.*)(?: |_|-|)giveaway(?:s)?",
        "rl(?: |_|-|)(?:.*)(?: |_|-|)giveaway(?:s)?",
        "psy(?:(?:0|o))nix(?: |_|-|)(?:.*)(?: |_|-|)mod(?:s)?",
        "psy(?:(?:0|o))nix(?: |_|-|)(?:.*)(?: |_|-|)supp(?:s)?",
        "psy(?:(?:0|o))nix(?: |_|-|)(?:.*)(?: |_|-|)ass(?:s)?"
    ]


    similarityMatch = 8 #Adjust this number. Lower => Image needs to be more similar to one of the blacklisted avatars
    similarityRatioPercentFuzzyWords = 0.85

    def __init__(self, bot):
        self.bot = bot

        passports = fileIO('data/scambot_protection/passport.json', 'load')

        for server in passports:
            try:
                for player in passports[server]['users']:
                    try:
                        key = player
                        value = passports[server]['users'][player]
                        if (value == 1):
                            sharedBot.passports.append(str(key))
                    except:
                        continue
            except:
                continue


    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self.runChecks(member)

        
    @commands.Cog.listener()
    async def on_user_update(self, user_before, user_after):
        await self.runChecks(user_after)

    async def runChecks(self, member):
        try:

            username_lower = str(member.name).lower()
            username = str((unicodedata.normalize('NFKD', username_lower).encode('ascii', 'ignore')).decode("ascii")).lower()

            #Check exact word filter
            try:
                for entry in self.scamBotFilter:
                    if(self.contains_word(username, entry)):
                        #Found a match
                        if(not str(member.id) in sharedBot.passports):
                            createdAt = member.created_at
                            difference = (datetime.now() - createdAt).days
                            if (difference < 14):
                                await self.messageAndBan(member, "Exact word filter match")
                                return

            except Exception as e:
                print("Error in exact filter match: {}".format(e))
            #Check Regex pattern matcher
            try:
                if (await self.runRegexFilters(member, username)):
                    return
            except Exception as e:
                print("Error in regex filter match: {}".format(e))

            try:
                if (await self.runDictionaryAvatarCreationdate(member, username)):
                    return
            #Check Similar string comparison with SequenceMatcher
            #if (await self.runFuzzyWordsCheck(member, username)):
               # return
            except Exception as e:
                print("Error in avatar dictionary filter match: {}".format(e))
            #Process user avatar and find similarity to the Psyonix images loaded in the self.imageHash list
            try:
                with requests.get(member.avatar_url) as r:
                    img_data = r.content

                user_hash = imagehash.average_hash(Image.open(BytesIO(img_data)))

                for hash in self.imagesHashes:
                    difference = hash - user_hash
                    if(difference < self.similarityMatch):
                        createdAt = member.created_at
                        difference = (datetime.now() - createdAt).days
                        if (difference < 6):
                            await self.messageAndBan(member, "Avatar match")
                            return
            except Exception as e:
                print(e)
                pass
        except Exception as e:
            print(e)
            pass

    async def runDictionaryAvatarCreationdate(self, member, username):
        username_split = username.split(" ")
        InitialValue = True

        for word in username_split:
            InitialValue = InitialValue and self.Dictionary.check(word)

        if(InitialValue):
            #All the words are in a dictionary, set off a flag.
            #Check avatar and Join date
            createdAt = member.created_at
            difference = (datetime.now() - createdAt).days
            if(difference < 6):
                #Account is less than 6 days old.
                if(member.avatar == None):
                    #No avatar, it's a scam bot.
                    #Ban
                    await self.messageAndBan(member, "Avatar and name check (+ Account less than a week old)")
                    return True

    async def runRegexFilters(self, member, username):
        compiled_regex = re.compile("|".join(self.regexPatterns))
        array = compiled_regex.findall(username)
        if (len(array) > 0):
            if (not str(member.id) in sharedBot.passports):
                await self.messageAndBan(member, "Regex match")
                return True

    async def runFuzzyWordsCheck(self, member, username):
        for entry in self.scamBotFilter:
            if(self.similar(username, entry) >= self.similarityRatioPercentFuzzyWords):
                if (not str(member.id) in sharedBot.passports):
                    await self.messageAndBan(member, "Fuzzy word filter")
                    return True

    #Messages the user and bans them
    async def messageAndBan(self, member, reason=""):
        if (not str(member.id) in sharedBot.passports):
            try:
                embed = Embed(title="You have been banned",
                                     description="Your account was intercepted by our protection system and you have been banned",
                                     colour=0xFF0000)
                await member.send(embed=embed)
                await asyncio.sleep(0.5)
            except:
                pass

            try:
                await self.globalBan(member, reason)
            except Exception as e:
                print("Failed to ban {} ({})".format(member, member.id))
                pass

    async def messageAndKick(self, member, reason=""):
        if (not str(member.id) in sharedBot.passports):
            try:
                embed = Embed(title="You have been kicked",
                                     description="Your account was intercepted by our protection system and you have been kicked",
                                     colour=0xFF0000)
                await member.send(embed=embed)
                await asyncio.sleep(0.5)
            except:
                pass

            try:
                await self.globalBan(member, reason)
            except Exception as e:
                print("Failed to kick {} ({})".format(member, member.id))
                pass

    @commands.group()
    @commands.check(checks.is_aspire)
    async def globalunban(self, ctx, userid):
        for guild in self.bot.guilds:
            try:
                await guild.unban(discord.Object(id=int(str(userid))))
                print("Unbanned in {}".format(guild))
                try:
                    scambot_channel = [ch for ch in guild.text_channels if ch.name == 'scambot-logs'][0]
                    embed = Embed(title="Unbanned user: <@{}>".format(userid),
                                  description="Unbanned user __<@{}> ({})__ .\n\nReason: {}".format(
                                      userid, userid, "User was found to be a false positive."),
                                  colour=0xFFDF00)
                    await scambot_channel.send(embed=embed)
                except:
                    pass
            except:
                pass
        await ctx.channel.send("Finished global unban.")

    @commands.group()
    @commands.check(checks.is_aspire)
    async def globalban(self, ctx, userid):
        for guild in self.bot.guilds:
            try:
                await guild.ban(discord.Object(id=int(str(userid))), reason="Suspected giveaway scam bot")
                print("Banned in {}".format(guild))
                try:
                    scambot_channel = [ch for ch in guild.text_channels if ch.name == 'scambot-logs'][0]
                    embed = Embed(title="Banned user: <@{}>".format(userid),
                                  description="Banned user __<@{}> ({})__ .\n\nReason: {}".format(
                                      userid, userid, "User was found to be a scam bot.\nNOTE: This is a global ban notice (the bot bans in all the servers it is in) and does not necessarily mean this user joined the server you are seeing this message in."),
                                  colour=0x443a59)
                    await scambot_channel.send(embed=embed)
                except:
                    pass
            except:
                pass
        await ctx.channel.send("Finished global ban.")

    @commands.group()
    @commands.check(checks.is_mod)
    async def passport(self,ctx, userid):

        try:
            strippedUser = int(userid.strip("<@!&>"))
        except Exception as e:
            embed = Embed(title="Error", description="{} is not a valid id.".format(userid), colour=0xFF0000)
            await ctx.channel.send(embed=embed)
            return


        passports = fileIO('data/scambot_protection/passport.json', 'load')
        try:
            passports[str(ctx.guild.id)]
        except:
            passports[str(ctx.guild.id)] = {}

        try:
            passports[str(ctx.guild.id)]['users']
        except:
            passports[str(ctx.guild.id)]['users'] = {}

        try:
            pp = passports[str(ctx.guild.id)]['users'][str(strippedUser)]
            if (pp == 1):
                del passports[str(ctx.guild.id)]['users'][str(strippedUser)]
                fileIO('data/scambot_protection/passport.json', 'save', passports)
                sharedBot.passports.remove(str(strippedUser))

                embed = Embed(title="Success", description="**Revoked** passport for user {}.".format(strippedUser),
                                     colour=0x443a59)
                await ctx.channel.send(embed=embed)
                return
        except:
            passports[str(ctx.guild.id)]['users'][str(strippedUser)] = 1
            sharedBot.passports.append(str(strippedUser))

            fileIO('data/scambot_protection/passport.json', 'save', passports)
            try:
                await ctx.guild.unban(discord.Object(id=int(strippedUser)))
            except:
                pass

            await ctx.channel.send("Unbanned and given passport to user: <@{}>.\nThey will now not be intercepted by the scambot filter".format(strippedUser))

    #Bans the user in all servers the bot instance is in
    async def globalBan(self, user, reason=""):
        try:
            for guild in self.bot.guilds:
                try:
                    await guild.ban(discord.Object(id=int(user.id)), reason="Suspected giveaway scam bot")

                    try:
                        description_string = "Banned user __{} ({})__ for suspected giveaway scambot / highly suspicious account.\n\n__Creation date:__ {}\n__Reason:__ {}\n\n_NOTE: This is a global ban notice (the bot bans in all the servers it is in) and does not necessarily mean this user joined the server you are seeing this message in._".format(
                                          user, user.id, str(user.created_at), reason)
                        if(str(guild.id) == str(self.ownerGuildID)):
                            description_string = "Banned user __{} ({})__ for suspected giveaway scambot / highly suspicious account.\n\n__Creation date:__ {}\n__Original Discord:__ {}\n__Reason:__ {}\n\n_NOTE: This is a global ban notice (the bot bans in all the servers it is in) and does not necessarily mean this user joined the server you are seeing this message in._".format(
                                user, user.id, str(user.created_at), str(user.guild), reason)

                        scambot_channel = [ch for ch in guild.text_channels if ch.name == 'scambot-logs'][0]
                        embed = Embed(title="Banned user: {}".format(user),
                                      description=description_string,
                                      colour=0x443a59)
                        embed.set_thumbnail(url=user.avatar_url)
                        await scambot_channel.send(embed=embed)
                    except:
                        try:
                            description_string = "\*Banned user __{} ({})__ for suspected giveaway scambot / highly suspicious account.\n\n__Reason:__ {}\n\n_NOTE: This is a global ban notice (the bot bans in all the servers it is in) and does not necessarily mean this user joined the server you are seeing this message in._".format(
                                user, user.id, reason)

                            scambot_channel = [ch for ch in guild.text_channels if ch.name == 'scambot-logs'][0]
                            embed = Embed(title="Banned user: {}".format(user),
                                          description=description_string,
                                          colour=0x443a59)
                            embed.set_thumbnail(url=user.avatar_url)
                            await scambot_channel.send(embed=embed)
                        except:
                            pass

                except:
                    pass

        except:
            pass

    async def globalUnban(self, user):
        for guild in self.bot.guilds:
            await guild.unban(discord.Object(id=int(user.id)))


    def contains_word(self, s, w):
        return (' ' + w + ' ') in (' ' + s + ' ')

    def similar(self, a, b):
        return SequenceMatcher(None, a, b).ratio()
