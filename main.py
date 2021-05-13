# region Standard Libraries
import json
import logging
import math
import mimetypes
import os
import random
import re
import time
from datetime import datetime
from ftplib import FTP
from traceback import format_exc
import argparse
import imaplib
import email
# endregion

# region External Libraries
from dotenv import load_dotenv  # pip install python-dotenv
import pytz  # pip install pytz

print(
    "Importing Discord")  # Importing discord.py can stall due to faulty PyNaCl versions, this helps with identification
import discord  # pip install -U discord.py[voice]
from discord import Embed
from discord.ext import tasks

print("Imported Discord")
import asyncio  # pip install -U discord.py[voice];pip install aiofiles
import requests  # pip install requests
from mcstatus import MinecraftServer  # pip install mcstatus
import yaml  # pip install PyYaml
from mcipc.rcon.je import Client  # pip3.9 install mcipc
import pysftp  # pip3.9 install pysftp


# endregion

# region Global Functions/Properties
def get_est_time(time_provided=None):
    desired_timezone = pytz.timezone("America/Toronto")
    if time_provided is not None:
        do_log("GET_EST_TIME ERROR, PLEASE IMPLEMENT CONVERTER")
        return "ERROR"
    else:
        return datetime.now(desired_timezone).strftime("%Y-%b-%d %I:%M:%S %p EST")


def do_log(message):
    print(f"[{get_est_time()}] {message}")


class VarHolder:
    pass


global bot
bot = VarHolder()
logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

do_log("Initializing Discord Client")  # Initializing discord.py client can stall, this helps with identifying it
client_intents = discord.Intents(messages=True, guilds=True, members=True)
bot.client = discord.Client(intents=client_intents)
do_log("Initialized Discord Client")


async def log_error(error):
    if "KeyboardInterrupt" in error:
        raise KeyboardInterrupt
    error_message = f"[{get_est_time()}]\n{error}"
    error_log_filename = "errors.log"
    try:
        with open(error_log_filename, "a") as error_log:
            error_log.write(error_message)
    except FileNotFoundError:
        with open(error_log_filename, "w") as error_log:
            error_message = f"[{get_est_time()}] WARNING: Failed to find existing error log. Writing to new.\n\n{error}"
            error_log.write(error_message)
    do_log(error_message)


def json_eval_object_pairs_hook(ordered_pairs):
    special = {
        "true": True,
        "false": False,
        "null": None,
    }
    result = {}
    for key, value in ordered_pairs:
        if key in special:
            key = special[key]
        else:
            for numeric in int, float:
                try:
                    key = numeric(key)
                except ValueError:
                    continue
                else:
                    break
        result[key] = value
    return result


def json_load_eval(fp_obj):
    return json.load(fp_obj, object_pairs_hook=json_eval_object_pairs_hook)


async def find_server_member(message=None, discord_id=None):
    message_copy = message
    if message_copy is None:
        message_copy = VarHolder()
        message_copy.content = "_ " + str(discord_id)
        message_copy.guild = bot.server
    msg = message_copy.content.split(" ")
    if len(msg) > 1 and msg[1] == "":
        msg[1] = msg[2]
    if len(msg) == 1 and discord_id is None:
        user = message_copy.author
    elif msg[1].replace("<@", "").replace("!", "").replace(">", "").isdigit():
        msg = int(msg[1].replace("<@", "").replace("!", "").replace(">", ""))
        user = message_copy.guild.get_member(msg)
    else:
        msg = msg[1]
        user = message_copy.guild.get_member_named(msg)
        if user is None:
            member_obj = {}
            for member in message_copy.guild.members:
                nick = "" if member.display_name == member.name else member.display_name
                member_obj[member.id] = {"nickname": nick, "username": member.name,
                                         "discriminator": member.discriminator}

            # nickname case insensitive
            for id in member_obj:
                member = member_obj[id]
                if msg == member["nickname"].lower():
                    user = id
                    break
            if user is None:
                # username case insensitive
                for id in member_obj:
                    member = member_obj[id]
                    if msg == member["username"].lower():
                        user = id
                        break
                if user is None:
                    # nickname case insensitive startswith match
                    for id in member_obj:
                        member = member_obj[id]
                        if member["nickname"].lower().startswith(msg):
                            user = id
                            break
                    if user is None:
                        # username case insensitive startswith match
                        for id in member_obj:
                            member = member_obj[id]
                            if member["username"].lower().startswith(msg):
                                user = id
                                break
                        if user is None:
                            # nickname case insensitive loose match
                            for id in member_obj:
                                member = member_obj[id]
                                if msg in member["nickname"].lower():
                                    user = id
                                    break
                            if user is None:
                                # username case insensitive loose match
                                for id in member_obj:
                                    member = member_obj[id]
                                    if msg in member["username"].lower():
                                        user = id
                                        break
                                if user is None:
                                    return None
            user = message_copy.guild.get_member(user)
    return user


def do_side_thread(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()


@bot.client.event
async def on_error(event, args="", kwargs=""):
    error = format_exc()
    await log_error("[Uncaught Error] " + error)


# endregion

async def get_hook_in_server(message):
    hooks = await message.channel.webhooks()
    found_hook = None
    for h in hooks:
        if h.user.id == bot.client.user.id:
            found_hook = h
            break
    if found_hook is None:
        found_hook = await message.channel.create_webhook(name=bot.client.user.display_name)
    return found_hook


async def CMD_forge(message):
    if message.content.lower().startswith("/forge"):
        if await is_member_admin(message.author):
            await message.channel.send(message.content.replace("/forge ", "", 1))
            await message.delete()
        else:
            await log_error(
                "[{}] ERROR: Attempted forge, but \"{}\" has no \"Manage Guild\" permissions".format(get_est_time(),
                                                                                                     message.author.id))


async def is_mod_chat(channel):
    # print(channel.name.encode("ascii","ignore").decode("ascii","ignore"))
    everyone_can_see = True
    for overwrite in channel.overwrites_for(bot.server.default_role):
        if overwrite[0] == "read_messages":
            # print("everyone_can_see: {}".format(overwrite[1]))
            everyone_can_see = overwrite[1] is None or overwrite[1] != False
            break
    if not everyone_can_see:
        aids_cant_see = True
        for overwrite in channel.overwrites_for(bot.role_aid):
            if overwrite[0] == "read_messages":
                # print("aids cant see: {}".format(overwrite[1]))
                aids_cant_see = overwrite[1] is None or overwrite[1] == False
                break
        if aids_cant_see:
            return True
    return False


async def INIT_censor():
    bot.uncensored_channels = []
    for channel in bot.server.text_channels:
        if await is_mod_chat(channel) or (bot.censored_channels_bypass is not None and channel.id in bot.censored_channels_bypass):
            bot.uncensored_channels.append(channel.id)


@bot.client.event
async def on_guild_channel_update(before, after):
    await INIT_censor()


@bot.client.event
async def on_guild_channel_create(before, after):
    await INIT_censor()


@bot.client.event
async def on_guild_channel_delete(before, after):
    await INIT_censor()


async def should_censor_message(text):
    censor = False
    split_message = text.lower().split(" ")
    for censored_word in bot.censored_words_startswith:
        for word in split_message:
            if word.startswith(censored_word):
                censor = True
    if not censor and any(
            word in split_message for word in bot.censored_words_independent):  # Split by spaces
        censor = True
    return censor


async def BOTCMD_censor(message):
    if message.channel.id in bot.uncensored_channels:
        return
    if await should_censor_message(message.content):
        await message.delete()
        embed = Embed()
        embed.title = f"Bad Language in #{message.channel.name}"
        embed.description = f"{message.author.mention}, Please don't use bad language 😟\n"
        embed.description += "Also, please don't attempt to bypass this chat filter or you will get in trouble."
        if message.author.bot:
            if message.channel.id not in [bot.channel_in_game.id, bot.channel_server_console.id]:
                embed.description = "Somehow, this bot sent bad language. Please tell a staff member if you identify " \
                                    "the cause. "
                await message.channel.send(embed=embed)
        else:
            try:
                await message.author.send(embed=embed)
            except Exception:
                embed.title = "Bad Language"
                await message.channel.send(embed=embed)



async def INIT_profiles():
    bot.file_profiles = "profiles.json"
    bot.minecraft_profiles = {}
    try:
        with open(bot.file_profiles, "r") as json_file:
            bot.minecraft_profiles = json.load(json_file)
    except FileNotFoundError:
        await save_player_info()


async def INIT_discord_verify():
    bot.file_profile_links = "profile_links.json"
    bot.discord_to_minecraft = {}
    bot.minecraft_to_discord = {}
    try:
        with open(bot.file_profile_links, "r") as json_file:
            unprocessed_discord_to_minecraft = json.load(json_file)
        for discord_id in unprocessed_discord_to_minecraft:  # Convert to int
            minecraft_username = unprocessed_discord_to_minecraft[discord_id]["minecraft_username"]
            discord_username = unprocessed_discord_to_minecraft[discord_id]["discord_username"]
            discord_id = int(discord_id)
            member = bot.server.get_member(discord_id)
            if member is not None:
                discord_username = "{}#{}".format(member.name, member.discriminator)
            bot.discord_to_minecraft[discord_id] = {"minecraft_username": minecraft_username,
                                                    "discord_username": discord_username}
            bot.minecraft_to_discord[minecraft_username.lower()] = discord_id
    except FileNotFoundError:
        pass
    with open(bot.file_profile_links, "w") as json_file:
        json.dump(bot.discord_to_minecraft, json_file, indent=4)


async def BOTCMD_discord_verify(message):
    if message.guild is not None or message.author.id != bot.client.user.id:
        return
    msg_split = message.content.split("Your Discord account has been linked to ", 1)
    if len(msg_split) <= 1:
        return
    recipient = message.channel.recipient
    minecraft_username = msg_split[1].split(" ")[0]
    bot.discord_to_minecraft[recipient.id] = {"minecraft_username": minecraft_username,
                                              "discord_username": "{}#{}".format(recipient.name,
                                                                                 recipient.discriminator)}
    existing = minecraft_username.lower() in bot.minecraft_to_discord
    bot.minecraft_to_discord[minecraft_username.lower()] = recipient.id
    with open(bot.file_profile_links, "w") as json_file:
        json.dump(bot.discord_to_minecraft, json_file, indent=4)
    await bot.channel_server_console.send(
        "{} ({}#{}) has linked their Minecraft account\n`{}`".format(recipient.mention, recipient.name,
                                                                     recipient.discriminator,
                                                                     minecraft_username))
    
    if not existing:
        rcon_credentials = bot.minecraft_rcon
        with Client(rcon_credentials["host"], rcon_credentials["port"], passwd=rcon_credentials["password"]) as c:
            c.run(f"crazycrate give physical Boost 1 {minecraft_username}")
        await recipient.send("For verifying, you have been given 1 Boost key!\nIf you do not see it, please run the ``/keys`` command to see if you have a virtual key.\nIf you did not receive a key, please contact staff.")
    
    try:
        recipient_member = bot.server.get_member(recipient.id)
        await recipient_member.add_roles(bot.role_player)
        await recipient_member.remove_roles(bot.role_guest)
    except Exception:
        await log_error(format_exc())
    

async def get_minecraft_uuid(minecraft_name):
    response = requests.get(bot.minecraft_name_to_uuid_api.format(name=minecraft_name))
    info = response.json() if response.status_code == 200 else {}
    return info


async def save_player_info(profile=None):
    if profile is not None:
        username = profile["username"].lower()
        bot.minecraft_profiles[username] = profile
    with open(bot.file_profiles, "w") as json_file:
        json.dump(bot.minecraft_profiles, json_file, indent=4)


async def update_player_info(discord_id=None, minecraft_target=None):
    profile = {}
    if discord_id is not None:
        member = bot.server.get_member(discord_id)
        if member is not None:  # Member in server, update info
            discord_username = "{}#{}".format(member.name, member.discriminator)
            discord_profile = bot.discord_to_minecraft[discord_id]
            discord_profile["discord_username"] = discord_username
            bot.discord_to_minecraft[discord_id] = discord_profile
        else:
            discord_profile = bot.discord_to_minecraft[discord_id]
            discord_username = discord_profile["discord_username"]
            if not discord_username.endswith(" (Left Discord)"):
                discord_username += " (Left Discord)"
                discord_profile["discord_username"] = discord_username
                bot.discord_to_minecraft[discord_id] = discord_profile
        profile["discord_username"] = bot.discord_to_minecraft[discord_id]["discord_username"]
        profile["discord"] = discord_id
        minecraft_target = bot.discord_to_minecraft[discord_id]["minecraft_username"]
    else:
        profile["discord_username"] = "N/A"
        profile["discord"] = "N/A"
    if minecraft_target is not None:
        uuid_obj = await get_minecraft_uuid(minecraft_target)
    else:
        uuid_obj = {}
    if uuid_obj == {}:
        profile["username"] = "N/A"
        profile["uuid"] = "N/A"
        profile["skin"] = "N/A"
        return profile
    profile["username"] = uuid_obj["name"]
    profile["uuid"] = await convert_minecraft_uuid(uuid_obj["id"])
    avatar_request = requests.get(bot.minecraft_avatar_api.format(uuid=profile["uuid"]))
    profile["avatar"] = avatar_request.url if avatar_request.status_code == 200 else bot.minecraft_avatar_not_found_url
    return profile


async def get_player_info(discord_target=None, minecraft_target=None):
    target = None
    if discord_target is not None:
        member = await find_server_member(discord_id=discord_target)
        if member is None:
            return False
        else:
            if member.id not in bot.discord_to_minecraft:
                return None
            minecraft_target = bot.discord_to_minecraft[member.id]["minecraft_username"]
            discord_target = member.id
    if minecraft_target is not None:
        if minecraft_target.lower() in bot.minecraft_to_discord or minecraft_target.lower() in bot.minecraft_profiles:
            target = minecraft_target.lower()
            if target in bot.minecraft_to_discord:
                discord_target = bot.minecraft_to_discord[target]
    else:
        return False
    if target is None:
        return None

    profile = await update_player_info(discord_id=discord_target, minecraft_target=target)
    return profile


async def get_english_timestamp(time_var):
    original_time = time_var
    seconds_in_minute = 60
    seconds_in_hour = 60 * seconds_in_minute
    seconds_in_day = 24 * seconds_in_hour
    days = math.floor(time_var / seconds_in_day)
    time_var -= days * seconds_in_day
    hours = math.floor(time_var / seconds_in_hour)
    time_var -= hours * seconds_in_hour
    minutes = math.floor(time_var / seconds_in_minute)
    time_var -= minutes * seconds_in_minute
    seconds = round(time_var)
    if minutes == 0:
        return "{} second{}".format(seconds, "s" if seconds != 1 else "")
    if hours == 0:
        return "{} minute{}".format(minutes, "s" if minutes != 1 else "")
    hours = round(original_time / seconds_in_hour, 1)
    if days == 0:
        return "{} hour{}".format(hours, "s" if hours != 1 else "")
    return "{} day{}, {} hour{}".format(days, "s" if days != 1 else "", hours, "s" if hours != 1 else "")


async def CMD_pinfo(message):
    if not message.content.lower().startswith("/pinfo"):
        return
    await message.add_reaction("⌛")

    args = message.content.lower().strip().split(" ")
    embed = Embed()
    embed.title = "Player Info"
    discord_target = None
    minecraft_target = None
    if len(args) == 1:
        discord_target = message.author.id
    elif len(args) == 2 and (args[1].lower() in bot.minecraft_profiles or args[1].lower() in bot.minecraft_to_discord):
        minecraft_target = args[1].lower()
    else:
        discord_target = message.content.lower().strip().split(" ", 1)[1]
    profile = await get_player_info(discord_target=discord_target, minecraft_target=minecraft_target)
    if profile is None:
        if len(args) == 1:
            embed.description = "**Could not find any player information on you!**\nHave you registered with the in-game command \"/discordsrv link\"?"
        else:
            if minecraft_target is not None:
                search_type = "Minecraft"
                target = minecraft_target
            else:
                search_type = "Discord"
                target = await find_server_member(discord_id=discord_target)
                target = discord_target if target is None else target.display_name
            embed.description = "**Could not find any player information for {} user \"**{}**\"!**".format(search_type,
                                                                                                           target)
        await message.channel.send(embed=embed)
        await message.remove_reaction("⌛", bot.client.user)
        return
    # todo: rewrite the logic so pycharm doesn't give a breaking suggestion
    elif profile == False:
        if len(args) == 1:
            embed.description = "**Could not find you as a Discord user in the Discord server!**\nSomething might be wrong..."
        else:
            embed.description = "**Could not find Discord user **{}** in the Discord server!**".format(
                "\"" + discord_target + "\"")
        await message.channel.send(embed=embed)
        await message.remove_reaction("⌛", bot.client.user)
        return

    if profile["discord_username"] == "N/A":
        discord_user_entry = "N/A"
    elif profile["discord"] == "N/A" and (not profile["discord_username"].endswith(" (Left Discord)")):
        discord_user_entry = "<@{}>".format(profile["discord"])
    else:
        discord_user_entry = profile["discord_username"]
    embed.add_field(name="Discord", value=discord_user_entry)
    embed.add_field(name="Minecraft", value=profile["username"])
    embed.set_footer(text=await convert_minecraft_uuid(profile["uuid"]))
    embed.set_thumbnail(url=profile["avatar"])
    if bot.server_online:
        try:
            server = MinecraftServer.lookup("play.jellycraft.net")
            query = server.query()
            player_online = False
            if profile["username"] in query.players.names:
                player_online = True
            embed.add_field(name="Status on Minecraft", value="Online" if player_online else "Offline")
        except Exception:
            pass
        profile["essentials"] = await get_essentials_profile(profile["uuid"])
        localTime = None
        if profile["essentials"] is not False and "ipAddress" in profile["essentials"]:
            ip = profile["essentials"]["ipAddress"]
            try:
                r = requests.get(bot.ip_geolocation_api.format(ip_address=ip)).json()
                iptime = r["time_12"].replace(" ", ":").split(":")
                localTime = "{}:{} {}\n*({})*".format(iptime[0], iptime[1], iptime[3], r["date"])
            except Exception:
                error = format_exc()
                await log_error("[IPTimeZone Error] " + error)
        embed.add_field(name="Local Time", value=localTime if localTime is not None else "ERROR")

        if profile["essentials"] is not False and "timestamps" in profile["essentials"]:
            if player_online:
                online = profile["essentials"]["timestamps"]["login"] / 1000
                online = time.time() - online
                playTime = await get_english_timestamp(online)
                embed.add_field(name="Playing since", value=playTime + " ago" if playTime is not None else "ERROR")
            else:
                offline = profile["essentials"]["timestamps"]["logout"] / 1000
                offline = time.time() - offline
                lastPlayed = await get_english_timestamp(offline)
                embed.add_field(name="Last Played", value=lastPlayed + " ago" if lastPlayed is not None else "ERROR")
        else:
            embed.add_field(name="Playtime/Offline Since", value="ERROR")

    await message.remove_reaction("⌛", bot.client.user)
    await message.channel.send(embed=embed)


async def CMD_players(message):
    if message.content.lower().startswith("/players"):
        await message.add_reaction("⌛")
        embed = Embed()
        embed.title = "Server Players"
        server = MinecraftServer.lookup(bot.minecraft_rcon["host"])
        try:
            query = server.query()
            if len(query.players.names) == 0:
                embed.description = "No players online."
            else:
                descriptionRows = []
                for player in query.players.names:
                    joinedDesc = "\n".join(descriptionRows)
                    if len(joinedDesc) > 1850:
                        embed.description = joinedDesc
                        await message.channel.send(embed=embed)
                        descriptionRows = []
                        embed.title = ""
                    descriptionRows.append(player)
                joinedDesc = "\n".join(descriptionRows)
                embed.description = joinedDesc

            await message.channel.send(embed=embed)
            await message.remove_reaction("⌛", bot.client.user)
        except Exception:
            print("[Status Error Handle] \n" + format_exc())
            embed.description = "Server appears to be offline."
            await message.channel.send(embed=embed)
            await message.remove_reaction("⌛", bot.client.user)


async def is_member_admin(member):
    if isinstance(member, str):
        member_id = member
        member = bot.server.get_member(member)
        if member is None:
            await log_error("[{}] ERROR: Could not find member \"{}\".".format(get_est_time(), member_id))
            return False
    if not member.guild_permissions.manage_guild:
        return False
    return True


@tasks.loop(seconds=120.0)
async def COROUTINE_change_emoji_for_channel():
    for channel_id in bot.random_emoji_channels:
        channel = bot.server.get_channel(channel_id)
        random_emoji = random.choice(bot.random_emojis)
        name_format = bot.random_emoji_channels[channel_id]
        new_channel_name = name_format.format(emoji=random_emoji)
        await channel.edit(name=new_channel_name)


@tasks.loop(seconds=2)
async def COROUTINE_serverstatus():
    server = MinecraftServer.lookup(bot.minecraft_rcon["host"])
    try:
        status = server.status()
        server_status = "{0}/{1} players".format(status.players.online, status.players.max)
        bot.server_online = True
    except Exception:
        bot.server_online = False
        server_status = "[SERVER IS DOWN]"
    if server_status != bot.server_status:
        bot.server_status = server_status
        await bot.client.change_presence(activity=discord.Game(name=bot.server_status, type=0))


@tasks.loop(seconds=30)
async def COROUTINE_forceserverstatus():
    await bot.client.change_presence(activity=discord.Game(name=bot.server_status, type=0))


@tasks.loop(seconds=300)
async def COROUTINE_nicknamesync():
    found = 0
    needed_change = 0
    changed = 0
    for discord_id in bot.discord_to_minecraft:
        profile = bot.discord_to_minecraft[discord_id]
        member = bot.server.get_member(discord_id)
        if member is None:
            print(f"[NameSync] Missing discord user\n{profile}")
            continue
        found += 1
        if discord_id in bot.nickname_sync_bypass:
            continue
        minecraft_name = profile["minecraft_username"]
        true_name = minecraft_name
        uuid_obj = await get_minecraft_uuid(minecraft_name)
        if "id" in uuid_obj:
            uuid = await convert_minecraft_uuid(uuid_obj["id"])
            essentials_profile = await get_essentials_profile(uuid)
            if essentials_profile != False:
                if "nickname" in essentials_profile:
                    true_name = essentials_profile["nickname"]
                    color_tag_count = true_name.count("§")
                    for i in range(color_tag_count):
                        try:
                            color_char_index = true_name.index("§")
                            if color_char_index != -1:
                                color_to_remove = true_name[color_char_index:color_char_index+2]
                                true_name = true_name.replace(color_to_remove, "")
                        except:
                            print(format_exc())
                            pass
        if member.display_name.lower() != true_name.lower():
            needed_change += 1
            try:
                await member.edit(nick=true_name)
                changed += 1
            except:
                error = format_exc()
                await log_error(f"[COROUTINE_nicknamesync] {member.display_name} / {minecraft_name}\n" + error)
    print(f"[NameSync] {found}/{len(bot.discord_to_minecraft)} found, {changed}/{needed_change} changed")


async def get_paypal_transactions_from_gmail():
    try:
        purchases = []
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login('jellycraftpaypal@gmail.com','PT$M9qBX9up^%3')

        mail.select('Paypal')

        result, data = mail.search(None, 'UnSeen') #Find "Unread" emails
        mail_ids = data[0]
        for mail_id in mail_ids.split():
            current_mail_id = str(int(mail_id)) #It's weird like that
            result, data = mail.fetch(current_mail_id, "(RFC822)")
            for response_part in data:
                if isinstance(response_part, tuple):
                    # from_bytes, not from_string
                    msg = email.message_from_bytes(response_part[1])
                    email_from = msg['from']
                    email_subject = msg['subject']
                    if "Notification of Payment Received" in email_subject:
                        msg_content = str(data[0][1])
                        #Mail seems to have plaintext and HTML versions, simple way to get the second HTML part
                        minecraft_username = msg_content.split("Minecraft Username: ",1)[-1].split("Minecraft Username: =\\r\\n",1)[-1].split("</span>",1)[0]
                        item_purchased = email_subject.split("Item #",1)[-1].split(" - Notification of Payment Received",1)[0]
                        amount_paid = msg_content.split("Total* $",1)[-1].split("\\r\\n",1)[0]
                        purchases.append({"username": minecraft_username, "item_purchased": item_purchased, "amount_paid": amount_paid})
                        mail.store(current_mail_id,'+FLAGS','\Seen') #Mark as "Read"
        mail.close()
        mail.logout()
        return True, purchases
    except:
        return False, format_exc()


async def INIT_Store():
    bot.file_store_lookup = "store_lookup.json"
    bot.store_lookup = {}
    try:
        with open(bot.file_store_lookup, "r") as json_file:
            bot.store_lookup = json.load(json_file)
    except FileNotFoundError:
        bot.store_lookup["Test3"] = {"friendlyname": "Test Item", "commands": [
            "crazycrate give physical Fortune 1 {username}",
            "crazycrate give physical Fortune 1 {username}"
        ]}
        with open(bot.file_store_lookup, "w") as json_file:
            json.dump(bot.store_lookup, json_file, indent=4)

async def process_store_item(username, item):
    lookup = bot.store_lookup[item]
    print(f"[Process Store Item] {username} | {item} | {lookup}")
    rcon_credentials = bot.minecraft_rcon
    with Client(rcon_credentials["host"], rcon_credentials["port"], passwd=rcon_credentials["password"]) as c:
        """c.tellraw("@a", 
        [
            {"text": "[JellyCraft Store] ", "color": "green"}, 
            {"text": username, "color": "white", "bold": "true"},
            {"text": " has purchased ", "color": "white"},
            {"text": lookup["friendlyname"], "color": "white", "bold": "true"},
            {"text": "!", "color": "white"}
        ])"""
        for cmd in lookup["commands"]:
            cmd_formatted = cmd.format(username=username)
            print(cmd_formatted)
            c.run(cmd_formatted)
            if cmd != cmd_formatted:
                player_online = False
                server = MinecraftServer.lookup(bot.minecraft_rcon["host"])
                try:
                    query = server.query()
                    if len(query.players.names) != 0:
                        for player in query.players.names:
                            if username.strip().lower() == player.strip().lower():
                                player_online = True
                                break
                except:
                    print(format_exc())
                if not player_online:
                    friendlyname = lookup["friendlyname"]
                    message = f"Thanks for your purchase of {friendlyname}!"
                    if "key" in friendlyname.lower():
                        message += " Since you were offline, it has been made virtual. Type /keys to see all your keys."
                    c.run(f"mail {username} {message}")


async def log_store_transaction(username, item, amount_paid):
    numerical_amount_paid = 0
    try:
        numerical_amount_paid = float(amount_paid.replace("$","").split(" ",1)[0])
    except:
        await log_error("log_store_transaction\n"+format_exc())
        return
    
    desired_timezone = pytz.timezone("America/Toronto")
    current_est_time = datetime.now(desired_timezone)
    file_name = f"{current_est_time.year}-{current_est_time.month}.json"
    file_monthly_store_log = os.path.join("store_log",file_name)
    
    item_lookup = bot.store_lookup[item]
    friendly_item_name = item_lookup["friendlyname"]
    
    log_entry = {
        "timestamp": time.time(), 
        "friendly_time": get_est_time(), 
        "username": username, 
        "item_code": item, 
        "item_name": friendly_item_name,
        "amount_paid_text": amount_paid, 
        "amount_paid_numerical": numerical_amount_paid
    }
    
    bot.monthly_store_log = []
    try:
        with open(file_monthly_store_log, "r") as json_file:
            bot.monthly_store_log = json.load(json_file)
    except FileNotFoundError:
        pass
        
    bot.monthly_store_log.append(log_entry)
    with open(file_monthly_store_log, "w") as json_file:
        json.dump(bot.monthly_store_log, json_file, indent=4)

    await bot.channel_transactions.send(f"__[{log_entry['friendly_time']}]__\n``{username}`` bought ``{friendly_item_name}``\n${amount_paid}")
    
    
@tasks.loop(seconds=30)
async def COROUTINE_checkPaypal():
    success, data = await get_paypal_transactions_from_gmail()
    if not success:
        print(data)
        await bot.channel_transactions.send(f"__[{get_est_time()}]__\nFailed to check PayPal transactions!\n```py\n{data}```")
        return
    for purchase in data:
        username = purchase["username"]
        item = purchase["item_purchased"]
        amount_paid = purchase["amount_paid"]
        await log_store_transaction(username, item, amount_paid)
        
        await process_store_item(username, item)


async def upload_monthly_fundraising_progress(amount, file_name):
    args = bot.website_sftp
    try:
        cnopts = pysftp.CnOpts()
        cnopts.hostkeys = None   
        with pysftp.Connection(host=args["host"], username=args["username"], password=args["password"], cnopts=cnopts) as sftp:
            sftp.cwd(f"/var/www/jellycraft.net/html/store/goals/")  # The full path
            upload_file_path = os.path.join("store_log", file_name)
            with open(upload_file_path, "w") as f:
                f.write(str(amount))
            sftp.put(upload_file_path)
        await asyncio.sleep(5)
        if os.path.exists(upload_file_path):
            os.remove(upload_file_path)
    except:
        await log_error(f"[upload_monthly_fundraising_progress]\n{format_exc()}")
        
        
@tasks.loop(seconds=30)
async def COROUTINE_updateSite():
    desired_timezone = pytz.timezone("America/Toronto")
    current_est_time = datetime.now(desired_timezone)
    webserver_file_name = f"{current_est_time.year}-{current_est_time.month}.txt"
    
    file_name = f"{current_est_time.year}-{current_est_time.month}.json"
    file_monthly_store_log = os.path.join("store_log",file_name)
    
    current_raised = 0
    try:
        with open(file_monthly_store_log, "r") as json_file:
            bot.monthly_store_log = json.load(json_file)
        
        for purchased_item in bot.monthly_store_log:
            current_raised += float(purchased_item["amount_paid_numerical"])
    except FileNotFoundError:
        pass
    
    await upload_monthly_fundraising_progress(current_raised, webserver_file_name)
        
        
async def INIT_SlashCommands():
    # discord_slash.utils.manage_commands.add_slash_command(bot_id, bot_token: str, guild_id, cmd_name: str, description: str, options: Optional[list] = None)
    # await discord_slash.utils.manage_commands.remove_all_commands_in(bot.client.user.id, bot.token, guild_id=None)
    # await discord_slash.utils.manage_commands.remove_all_commands_in(bot.client.user.id, bot.token, guild_id=None)
    # await discord_slash.utils.manage_commands.add_slash_command(bot.client.user.id, bot.token, None, "players", "List the players currently on the Minecraft server", None)
    # discord_slash.utils.manage_commands.create_option(name: str, description: str, option_type: Union[int, type], required: bool, choices: Optional[list] = None)
    # await discord_slash.utils.manage_commands.create_option(name="Discord Ping", description: "A mention like @DiscordName", option_type: Union[int, type], required: False, choices: Optional[list] = None)
    # await discord_slash.utils.manage_commands.add_slash_command(bot.client.user.id, bot.token, None, "pinfo", "Gets info about a player", None)
    pass


async def suggest_minecraft_profile_link(user):
    message = f"{user.mention} Thanks for joining the Discord!\nMake sure to link your Minecraft account for more features by using the ``/discord link`` command in-game!"
    try:
        await user.send(message)
    except Exception:
        try:
            await bot.channel_botcmds.send(message)
        except Exception:
            error = format_exc()
            await log_error("[suggest_minecraft_profile_link] " + error)
            

async def BOTCMD_Welcome(message):
    if message.channel.id != bot.channel_welcome.id or message.author.id == bot.client.user.id or not message.type.name == "new_member":
        return
    try:
        new_member = message.author
        await message.delete()
        embed = Embed()
        embed.description = f"Welcome to the server, {new_member.display_name}#{new_member.discriminator}!"
        await message.channel.send(embed=embed)
        await suggest_minecraft_profile_link(new_member)
    except:
        error = format_exc()
        await log_error("[Welcome] " + error)
        
        
async def BOTCMD_InGame(message):
    if message.channel.id != bot.channel_in_game.id or message.author.bot:
        return
    if await should_censor_message(message.clean_content):
        return
    if not bot.server_online:
        return
    embed = Embed()
    color = "#" + hex(message.author.top_role.color.value).replace("0x", "", 1)
    color = color if color != "#0" else "#FFFFFF"
    role = message.author.top_role.name
    clean_everyone_content = message.clean_content if message.mention_everyone else message.content
    embed.description = "[{}] {}: {}".format(role, message.author.display_name, clean_everyone_content)

    try:
        failed = False
        failed_msg = "Unknown Error!"
        if message.author.id in bot.discord_to_minecraft:
            username = bot.discord_to_minecraft[message.author.id]["minecraft_username"]
            uuid_obj = await get_minecraft_uuid(username)
            if "id" in uuid_obj:
                uuid = await convert_minecraft_uuid(uuid_obj["id"])
                essentials_profile = await get_essentials_profile(uuid)
                if essentials_profile != False:
                    display_name = message.author.display_name
                    if essentials_profile is not None and "nickname" in essentials_profile:
                        display_name = essentials_profile["nickname"]
                        embed.description = "[{}] {}: {}".format(role, re.sub(r"(§[a-zA-Z0-9])", "", display_name),
                                                                 clean_everyone_content)
                    rcon_credentials = bot.minecraft_rcon
                    with Client(rcon_credentials["host"], rcon_credentials["port"],
                                passwd=rcon_credentials["password"]) as c:
                        c.tellraw("@a", [{"text": "[", "color": "white"}, {"text": role, "color": color},
                                         {"text": "] {}".format(display_name)},
                                         {"text": ": {}".format(message.clean_content), "color": "white"}])
                        await message.channel.send(embed=embed)
                        await message.delete()
                else:
                    failed = True
                    failed_msg = "Could not find Essentials Profile based on Minecraft UUID ({}) of username ({})!".format(
                        uuid, username)
            else:
                failed = True
                failed_msg = "Could not find UUID based on Minecraft username {}!".format(username)
        else:
            failed = True
            failed_msg = "Could not find your username!\nHave you linked your discord on the Minecraft server?"
        if failed:
            await message.add_reaction("🕵️")
            await message.add_reaction("❌")

            try:
                await message.author.send(failed_msg)
            except Exception:
                await message.channel.send(failed_msg)
    except Exception:
        if "mcipc.rcon.errors.NoPlayerFound" not in format_exc():
            error = format_exc()
            await log_error("[Discord-To-Minecraft] " + error)
            try:
                await message.add_reaction("📡")
                await message.add_reaction("❌")
            except Exception:
                pass
        else:
            try:
                embed.set_footer(text="Note: No players online when this message was sent.")
                await message.channel.send(embed=embed)
                await message.delete()
            except Exception:
                pass


async def get_essentials_profile(uuid):
    args = bot.minecraft_ftp
    try:
        with FTP(args["host"], args["username"], args["password"]) as ftp:
            ftp.cwd("/plugins/Essentials/userdata")
            yml_file = []
            ftp.retrlines("RETR {}.yml".format(uuid), yml_file.append)
            yml_file = "\n".join(yml_file)
            yml_file = yaml.safe_load(yml_file)
    except Exception:
        error = format_exc()
        await log_error("[GetEssentials Error] " + error)
        yml_file = ""
    if yml_file == "":
        return False
    else:
        return yml_file


async def convert_minecraft_uuid(uuid, to_dashed=True):
    uuid = uuid.replace("-", "")
    output = uuid
    if to_dashed:
        try:
            output = "{}-{}-{}-{}-{}".format(uuid[:8], uuid[8:12], uuid[12:16], uuid[16:20], uuid[20:])
        except Exception:
            return False
    return output


@bot.client.event
async def on_message(message):
    if not bot.ready:  # Race condition
        return
    if message.content.lower().startswith("/off") and message.author.id == bot.owner_id:
        try:
            await message.delete()
        except Exception:
            pass
        await bot.client.close()
        await bot.client.logout()
        return
    msg2 = message
    msg2.content = msg2.content.replace("@everyone", "@ everyone").replace("@here", "@ here")
    for i in bot.botcommands:
        # Execute every function that starts with BOTCMD_
        await globals()[i](msg2)
    if message.author == bot.client.user or message.author.bot:
        return
    on_server = message.guild == bot.server
    not_whitelisted_channel = message.channel.id not in bot.channels_allowing_bot_commands
    not_admin = not await is_member_admin(message.author)
    if on_server and not_whitelisted_channel and not_admin:
        return
    # Execute every function that starts with CMD_
    for i in bot.commands:
        await globals()[i](msg2)


async def config():
    bot.server = bot.client.get_guild(bot.server)
    bot.last_changed_emoji = 0
    bot.channel_server_console = bot.server.get_channel(bot.channel_server_console)
    bot.channel_in_game = bot.server.get_channel(bot.channel_in_game)
    bot.channel_welcome = bot.server.get_channel(bot.channel_welcome)
    bot.channel_botcmds = bot.server.get_channel(bot.channel_botcmds)
    bot.channel_transactions = bot.server.get_channel(bot.channel_transactions)
    bot.server_status = "Querying server..."
    bot.role_aid = bot.server.get_role(817297406759534612)
    bot.role_guest = bot.server.get_role(817134137067438112)
    bot.role_player = bot.server.get_role(808900317638426676)


@bot.client.event
async def on_ready():
    try:
        do_log(f"Bot name: {bot.client.user.name}")
        do_log(f"Bot ID: {bot.client.user.id}")
        await bot.client.change_presence(activity=discord.Game(name="Starting bot...", type=0))
        await config()
        bot.commands = [i for i in dir(__import__(__name__)) if i.startswith("CMD_")]
        bot.botcommands = [i for i in dir(__import__(__name__)) if i.startswith("BOTCMD_")]
        bot.functions = [i for i in dir(__import__(__name__)) if i.startswith("FUNC")]
        bot.initfunctions = [i for i in dir(__import__(__name__)) if i.startswith("INIT_")]
        bot.addreactraw = [i for i in dir(__import__(__name__)) if i.startswith("ADDREACTRAW_")]
        bot.addreact = [i for i in dir(__import__(__name__)) if i.startswith("ADDREACT_")]
        for i in bot.initfunctions:
            await globals()[i]()
        await bot.client.change_presence(activity=discord.Game(name=bot.server_status, type=0))
        COROUTINE_change_emoji_for_channel.start()
        COROUTINE_serverstatus.start()
        COROUTINE_forceserverstatus.start()
        COROUTINE_nicknamesync.start()
        COROUTINE_checkPaypal.start()
        COROUTINE_updateSite.start()
        do_log("Ready\n\n")
        bot.ready = True
    except Exception:
        await log_error(f"\n\n\nCRITICAL ERROR: FAILURE TO INITIALIZE{format_exc()}")
        await bot.client.close()
        await bot.client.logout()
        exit()
        raise Exception("CRITICAL ERROR: FAILURE TO INITIALIZE")
        return


def load_config_to_bot():
    parser = argparse.ArgumentParser(description='Discord bot arguments.')
    parser.add_argument('--config', help='Filepath for the config JSON file', default="config.json")
    args = parser.parse_args()
    try:
        with open(args.config, "r", encoding="utf-8") as config_file:
            loaded_config = json_load_eval(config_file)
    except FileNotFoundError:
        raise FileNotFoundError(f"'{args.config}' not found.")
    for config_key in loaded_config:
        loaded_val = loaded_config[config_key]
        setattr(bot, config_key, loaded_val)
        do_log(f"Loaded config setting \n'{config_key}' ({type(loaded_val).__name__})\n{loaded_val} ")


def load_env_vars():
    load_dotenv(verbose=True)
    env_vars = {
        "DISCORD_TOKEN": "",
        "IPGEOLOCATIONIO_KEY": "",
        "MINECRAFT_FTP_HOST": "",
        "MINECRAFT_FTP_PASSWORD": "",
        "MINECRAFT_FTP_USERNAME": "",
        "MINECRAFT_RCON_HOST": "",
        "MINECRAFT_RCON_PASSWORD": "",
        "MINECRAFT_RCON_PORT": "",
        "WEBSITE_SFTP_HOST": "",
        "WEBSITE_SFTP_PASSWORD": "",
        "WEBSITE_SFTP_USERNAME": "",
    }
    for env_var_name in env_vars:
        env_var_val = os.getenv(env_var_name)
        if os.getenv(env_var_name) is None:
            raise NameError(f"'{env_var_name}' environment variable not found.")
        env_vars[env_var_name] = env_var_val
    return env_vars


def censor_text(text):  # Censors the second half of a string, minus 4 characters
    return text[:int(len(text) / 2)] + str("*" * (int(len(text) / 2) - 4)) + text[:4]


def main():
    global bot
    bot.ready = False
    do_log("Loading Config")

    load_config_to_bot()  # Load a json to the bot class
    env_vars = load_env_vars()  # Load the needed environment variables, optionally from a .env file

    # Perform some formatting and parsing with env vars while they're still in scope
    do_log(f'Discord token: {censor_text(env_vars["DISCORD_TOKEN"])}')
    bot.minecraft_ftp = {"host": env_vars["MINECRAFT_FTP_HOST"], "username": env_vars["MINECRAFT_FTP_USERNAME"],
                         "password": env_vars["MINECRAFT_FTP_PASSWORD"]}
    bot.minecraft_rcon = {"host": env_vars["MINECRAFT_RCON_HOST"], "port": int(env_vars["MINECRAFT_RCON_PORT"]),
                          "password": env_vars["MINECRAFT_RCON_PASSWORD"]}
    bot.ip_geolocation_api = bot.ip_geolocation_api.format(api_key=env_vars["IPGEOLOCATIONIO_KEY"],
                                                           ip_address="{ip_address}")
    bot.website_sftp = {"host": env_vars["WEBSITE_SFTP_HOST"], "username": env_vars["WEBSITE_SFTP_USERNAME"],
                         "password": env_vars["WEBSITE_SFTP_PASSWORD"]}
    # DiscordPy tasks
    do_log("Loaded Config")
    do_log("Logging in")
    bot.client.run(env_vars["DISCORD_TOKEN"])
    do_log("Logging out")


if __name__ == '__main__':
    main()
    # mainthread = threading.Thread(target=main)
    # mainthread.start()
