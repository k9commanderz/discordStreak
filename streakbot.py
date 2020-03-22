import discord
import json
from discord.ext import commands
from discord.ext import tasks
from datetime import datetime
from database import DataBase
from discord.ext.commands import CommandError

bot = commands.Bot(command_prefix='$')

usersInCurrentGuild = {}

streakData = json.load(open("streak.json", "r+"))


class StreakBot(commands.Cog):
    today = datetime.today().date().strftime("%d-%m-%Y")
    yesterday = None

    def __init__(self, bot):
        self.bot = bot
        self.embed = None
        self.dataBase = DataBase('discordStreakBot.db')

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'We have logged in as {self.bot.user}\n')
        self.dateCheck.start()

        # self.scanCurrentServer()
        # self.updateJson()

    # @commands.Cog.listener()
    # async def on_command_error(self, ctx, error):
    #     """
    #     Stop raising error for commands bugs to much
    #     """
    #     if isinstance(error, CommandError):
    #         return
    #     raise error

    @commands.Cog.listener()
    async def on_message(self, message):

        user = message.author
        userID = user.id
        guildID = message.guild.id

        # ignore bots
        if not user.bot:

            messageLength = len(message.content.split())
            # add the length of the message to the database to track
            self.dataBase.addMessageCount(guildID, userID, messageLength)
            # retrieve user message count
            msgCount = self.dataBase.getMessageCount(guildID, user.id)
            # retrieve server message threshold
            guildThreshold = self.dataBase.getServerThreshold(guildID)
            # check if they had streaked
            streaked = self.dataBase.checkUserStreaked(guildID, userID)

            # give streak if they had streaked.
            if msgCount >= guildThreshold and not streaked:
                self.dataBase.addStreakToUser(guildID, userID, self.today)

    @commands.command()
    async def streak(self, ctx, *args):

        # getting the guild the message was sent from

        guildID = ctx.guild.id

        # return first 25
        leaderBoard = self.dataBase.viewLeaderBoard(guildID)

        # get the username of a user and remove anything after their deliminator #
        userNames = '\n'.join([user[0].split('#')[0] for user in leaderBoard])

        # userName = []
        #
        # for user in leaderBoard:
        #     userName = user[0].split('#')[0]

        usersTotalMessages = '\n'.join([str(user[1]) for user in leaderBoard])
        usersStreakDays = '\n'.join([str(user[2]) for user in leaderBoard])

        # check if user has mentioned someone
        mention = ctx.message.mentions

        # get the first word this will be used for $streak me to retrieve current user's streak
        otherMessage = args

        # if user has mentioned someone return the first mention in case they mentioned more than once
        if mention:
            # get the user that was mention
            userMentioned = mention[0]
            # check if the user mentioned is a bot other wise cancel
            if not mention[0].bot:
                # send the information over to another method to send an embed for that user
                # passing over ctx to send message to the channel

                await self.mentionStreak(ctx, userMentioned, guildID)

        # check if there's any other messages that were sent
        elif otherMessage:

            # get the first word that was mentioned
            otherMessage = args[0]

            if otherMessage == "me":
                await self.mentionStreak(ctx, ctx.author, guildID)

        else:
            self.embed = dict(
                title=f"**==STREAK LEADERBOARD==**",
                color=9127187,
                thumbnail={
                    "url": "https://cdn4.iconfinder.com/data/icons/miscellaneous-icons-2-1/200/misc_movie_leaderboards3-512.png"},
                fields=[dict(name="**Users**", value=userNames, inline=True),
                        dict(name="Streak Total", value=usersStreakDays, inline=True),
                        dict(name="Total Words Sent", value=usersTotalMessages, inline=True)],
                footer=dict(text=f"Total Words counted on {self.today}")
            )
            await ctx.channel.send(embed=discord.Embed.from_dict(self.embed))

    # checking for the dates if its a new day
    @tasks.loop(seconds=60)
    async def dateCheck(self):

        currentDay = datetime.today().date().strftime("%d-%m-%Y")

        if self.today != currentDay:
            # keeping tracking of the day  before
            yesterday = self.today
            # updating today so it is the correct date
            self.today = currentDay

            print("New Day")
            self.checkStreaks()

    @staticmethod
    def checkStreaks():

        # we will be looping through the servers to add or reset the streak
        for guild in streakData:

            guildWordCount = streakData[guild]['serverInfo']["wordcount"]

            # check each members in the guild
            for member in streakData[guild]:

                # Ignore server info
                if member == 'serverInfo':
                    continue

                # retrieve total messages sent
                memberTotalMessage = streakData[guild][member][0]

                # if the user has sent more than 20 words today
                if memberTotalMessage >= guildWordCount:

                    # reset their messages sent
                    streakData[guild][member][0] = 0

                    # print(streakData[guild][member][0])

                    #  change streaked today to false as its a new day so no streak yet
                    streakData[guild][member][2] = False

                else:
                    # reset their messages sent
                    streakData[guild][member][0] = 0

                    # clear the streak if they had any
                    streakData[guild][member][1] = 0
        print('done')
        # back up the file
        json.dump(streakData, open("streak.json", "w"))

    @commands.Cog.listener()
    async def on_member_join(self, user):

        # add the user to the correct server
        if not user.bot:
            print(f"New user has joined {user.guild.name}")
            self.dataBase.addUser(user.guild, user)

    @commands.Cog.listener()
    async def on_member_remove(self, user):

        # remove the user from data as they have left
        if not user.bot:
            print(f"user has left  {user.guild.name}")
            self.dataBase.removeUser(user.guild.id, user.id)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):

        print(f"New Guild Has Joined {guild.name}")
        # add new guild to the database
        self.dataBase.addNewGuild(guild)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild):

        print(f"A Guild Has left {guild.name}")
        self.dataBase.removeServer(guild.id)

    @commands.command()
    async def info(self, ctx):

        # how many server the bot is in
        totalGuilds = len(self.bot.guilds)
        totalUsers = len(self.bot.users)

        totalChannels = sum([len(guild.channels) for guild in self.bot.guilds])

        latency = int(self.bot.latency * 100)

        guildMessageFrom = str(ctx.guild.id)

        # the threshold(total messages to achieve to streak) the guild has been set to
        guildMessageThreshold = streakData[guildMessageFrom]['serverInfo']["wordcount"]

        self.embed = dict(
            title=f"**==DISCORD STREAK INFO==**",
            color=9127187,
            description=
            f":white_small_square: Minimum word count for streak is {guildMessageThreshold}.\n"
            f":white_small_square: Streaks are added when you reach {guildMessageThreshold} words or more.\n"
            ":white_small_square: Streak will reset at midnight GMT failure to meet word count.\n"
            ,
            thumbnail={
                "url": "https://cdn3.iconfinder.com/data/icons/shopping-e-commerce-33/980/shopping-24-512.png"},
            fields=[dict(name=f"**====================** \n"
                         , value=f":book: Total Servers\n"
                                 f":book: Total Players\n"
                                 f":book: Total Channels\n"
                                 f":book: My Connection\n"
                                 "====================", inline=True),

                    dict(name="**====================**", value=f":white_small_square:    {totalGuilds}\n "
                                                                f":white_small_square:    {totalUsers:02,}\n"
                                                                f":white_small_square:    {totalChannels}\n"
                                                                f":white_small_square:    {latency} ms\n"
                                                                f"====================",
                         inline=True),

                    dict(name="**Useful Links**",
                         value=f":white_small_square: [Vote](https://top.gg/bot/685559923450445887) for the bot \n"
                               f":white_small_square: [support channel](https://discord.gg/F6hvm2) for features request| upcoming updates"
                         ,
                         inline=False),

                    dict(name="**Update**",
                         value=f":white_small_square: **!streak @someone** to view their summary profile\n"
                               f":white_small_square: **!streak me** to view your own profile \n"
                               f":white_small_square: small Achievement has been added summary profile.\n"
                               f":white_small_square: set threshold for amount words for a streak **!threshold amount** \n"
                               f":white_small_square: **only server owner can set threshold**",
                         inline=False),

                    ],

            footer=dict(text=f"HAPPY STREAKING!"),
        )
        await ctx.channel.send(embed=discord.Embed.from_dict(self.embed))

    async def mentionStreak(self, ctx, user, guildID):

        userName, MsgCount, streakCounter, streaked, highestStreak, lastStreakDay, highMsgCount \
            = self.dataBase.getUserInfo(guildID, user.id)

        guildThreshold = self.dataBase.getServerThreshold(guildID)

        # adding emotes based on different stages of streak for current streak only
        # if user has reached 3 or more streak day they get fire streak
        if streakCounter >= 3:

            userStreakFormat = f"{streakCounter} :fire:"

            #  if user reached over 100 streaks they get #100 emote
            if streakCounter >= 100:
                userStreakFormat = f"{streakCounter} :fire: :100: "

        else:
            userStreakFormat = streakCounter

        # message to be put in the footer if they had achieved a streak
        streakClaimedMessage = "You have claimed your streak for today"

        # footer message to indicate if the user has received a streak for today
        footerMessage = streakClaimedMessage if MsgCount >= guildThreshold else f"Word count till streak {guildThreshold -MsgCount}" \
 \
            # userTotalMessages = userTotalMessages if userTotalMessages < 100 else f"{userTotalMessages} "

        self.embed = dict(
            color=9127187,
            author={"icon_url": f"{user.avatar_url}", "url": f"{user.avatar_url}",
                    "name": f"{userName}'s Profile Summary"},
            fields=[
                dict(name="**Highest Streak**", value=highestStreak, inline=True),
                dict(name="**Current Streak**", value=userStreakFormat, inline=True),
                dict(name=":book: **Other Stats**",
                     value=f":small_blue_diamond: **Last Streaked:**  \u200b {lastStreakDay}\n"
                           f":small_blue_diamond: **Current Word Count:**  \u200b {MsgCount:0,}\n"
                           f":small_blue_diamond: **Total Word Count:**  \u200b {highMsgCount:0,}",
                     inline=False),

            ],
            # image = {"url": f"{user.avatar_url}"},
            # footer
            footer=dict(text=f"{footerMessage}"),

        )

        # check if the user has achieved any of the milestones
        self.achievementUnlocks(highestStreak, highMsgCount)

        await ctx.channel.send(embed=discord.Embed.from_dict(self.embed))

    def achievementUnlocks(self, userStreak, totalMessage):

        # milestone that will be used for looping
        milestones = {10: "",
                      20: "",
                      40: "",
                      60: "",
                      80: "",
                      100: "",
                      150: ""}

        msgMilestone = {500: "",
                        1000: "",
                        2000: "",
                        10000: "",
                        20000: "",
                        50000: "",
                        100000: ""}

        # loop through the milestone and check if the user has reached the milestone if they have give them diamond
        # else cross

        achievementStreakCheck = '\n'.join([f":gem: {milestone} Streaks"
                                            if userStreak >= milestone else f":x: {milestone} Streaks"
                                            for milestone in milestones])

        achievementMsgCheck = '\n'.join([
            f":gem: {milestone:02,} words" if totalMessage >= milestone else f":x: {milestone:02,} words"
            for milestone in msgMilestone])

        # add the achievement to the embed to display
        achievements = dict(name="**Streak Milestones**",
                            value=f"{achievementStreakCheck}", inline=True)

        achievement2 = dict(name="**Words Milestones**",
                            value=f"{achievementMsgCheck}", inline=True)

        bottomBar = dict(name="=====**More Achievements To Come**====", value=f"\u200b")

        self.embed['fields'].append(achievements)
        self.embed['fields'].append(achievement2)
        self.embed['fields'].append(bottomBar)

    # will be used for debugging when need to make changes
    @commands.command()
    async def updateData(self, ctx):
        if ctx.author.id == 125604422007914497:
            json.dump(streakData, open("streak.json", "w"))
            await ctx.channel.send("Database has been backed up")

    @commands.command()
    async def threshold(self, ctx, total):

        guildOwnerId = ctx.guild.owner_id
        currentUserId = ctx.author.id
        guildMessageFrom = str(ctx.guild.id)

        # if it is not the guild owner ignore | only guild owner can set threshold
        if currentUserId == guildOwnerId:
            # in case the user has put in words as a digit instead of actual integers
            try:
                newThresholdCounter = int(total)

                newThreshold = streakData[guildMessageFrom]['serverInfo']["wordcount"] = newThresholdCounter

                await ctx.channel.send(f"New message threshold has been set for the server to {newThresholdCounter}")
            except ValueError:
                pass

    # this is only needed if you had the old system and need to add extra info

    def updateJson(self):

        # we will be looping through the servers to add or reset the streak
        for guild in streakData:

            serverInfo = {'serverInfo': {"wordcount": 100,
                                         "channels": []
                                         }
                          }

            if 'serverInfo' not in streakData[guild]:
                streakData[guild].update(serverInfo)

            # check each members in the guild
            for member in streakData[guild]:
                newDataSet = {"highestStreak": 0,
                              "lastStreakDay": "Never Streaked",
                              "highestMessageCount": 0}

                # every guild has a message threshold count this would need to be ignored
                memberInfo = streakData[guild][member]

                if type(memberInfo) == list:
                    # check if the dictionary exist for remaining stats
                    try:
                        checkIndex = memberInfo[3]
                        pass
                    except IndexError:
                        # if the index does not exist mean no stats available
                        memberInfo.append(newDataSet)

        json.dump(streakData, open("streak.json", "w"))

        print("Json UPDATED")

    # would be used if hosting bot yourself
    def scanCurrentServer(self):

        # scanning al the guild the bot is currently in and return their ID
        for guild in self.bot.guilds:

            # create a list to hold each users for different guild
            usersInCurrentGuild[guild.id] = {}

            for member in guild.members:

                # checking if the user is a bot as we wont be tracking the bots
                if not member.bot:
                    # add those users into the system
                    # each member has total message, days of streak

                    newDataSet = {"highestStreak": 0,
                                  "lastStreakDay": "Never Streaked",
                                  "highestMessageCount": 0}

                    usersInCurrentGuild[guild.id].update({member.id: [0, 0, False, newDataSet]})

            serverInfo = {'serverInfo': {"wordcount": 100,
                                         "channels": []
                                         }
                          }

            # add word count for the server
            usersInCurrentGuild[guild.id].update(serverInfo)

        json.dump(usersInCurrentGuild, open("streak.json", "w"))

    # this is only for debugging not to be used for implementation
    @commands.command()
    async def givestreak(self, ctx, totalStreak):

        guildMessageFrom = str(ctx.guild.id)

        testGuildID = 602439523284287508

        if ctx.author.id == 125604422007914497 and ctx.guild.id == testGuildID:
            mentionedUser = ctx.message.mentions[0].name
            mentionedUserID = str(ctx.message.mentions[0].id)
            # give the user a streak point
            streakData[guildMessageFrom][mentionedUserID][1] += int(totalStreak)

            await ctx.channel.send(f"{mentionedUser} has been given {totalStreak} streaks")

    # this is only for debugging not to be used for implementation
    @commands.command()
    async def givemsg(self, ctx, totalStreak):

        guildMessageFrom = str(ctx.guild.id)
        testGuildID = 602439523284287508
        if ctx.author.id == 125604422007914497 and ctx.guild.id == testGuildID:
            mentionedUser = ctx.message.mentions[0].name
            mentionedUserID = str(ctx.message.mentions[0].id)
            # give the user a streak point
            streakData[guildMessageFrom][mentionedUserID][3]["highestMessageCount"] += int(totalStreak)

            await ctx.channel.send(f"{mentionedUser} has been given {totalStreak} MSG POINT")


if __name__ == "__main__":
    bot.add_cog(StreakBot(bot))
    bot.remove_command("help")
    bot.run("")

"""
Methods to update when changing Json

when guild joins
when user join guilds

"""
