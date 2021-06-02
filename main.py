# region Standard Libraries
import json
import logging
import math
import os
import random
import re
import time
from datetime import datetime
from ftplib import FTP
from traceback import format_exc
import argparse
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
import requests  # pip install requests
from mcstatus import MinecraftServer  # pip install mcstatus
import yaml  # pip install PyYaml
from mcipc.rcon.je import Client  # pip3.9 install mcipc
import pysftp  # pip3.9 install pysftp


# endregion

# region Global Functions/Properties
def censor_text(text):  # Censors the second half of a string, minus 4 characters
    return text[:int(len(text) / 2)] + str("*" * (int(len(text) / 2) - 4)) + text[:4]


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
# noinspection PyRedeclaration
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


def json_eval_object_pairs_hook(ordered_pairs):  # Necessary function for json_load_eval
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


def json_load_eval(fp_obj):  # Loads a json evaluating any strings to possible variables
    return json.load(fp_obj, object_pairs_hook=json_eval_object_pairs_hook)


# noinspection PyShadowingBuiltins
async def find_server_member(message=None, discord_id=None):  # todo: Clean this up
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


# noinspection PyUnusedLocal
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


async def cmd_forge(message):
    if message.content.lower().startswith("/forge"):
        if await is_member_admin(message.author):
            await message.channel.send(message.content.replace("/forge ", "", 1))
            await message.delete()
        else:
            await log_error(
                f"[{get_est_time()}] ERROR: Attempted forge, but \"{message.author.id}\" has no \"Manage Guild\" "
                f"permissions")


async def is_mod_chat(channel):
    # print(channel.name.encode("ascii","ignore").decode("ascii","ignore"))
    not_everyone_can_see = False
    for overwrite in channel.overwrites_for(bot.server.default_role):
        permission_name, permission_value = overwrite[0], overwrite[1]
        if permission_name == "read_messages":
            not_everyone_can_see = permission_value is not True
            break
    if not_everyone_can_see:
        aids_cant_see = False
        for overwrite in channel.overwrites_for(bot.roles["aid"]):
            permission_name, permission_value = overwrite[0], overwrite[1]
            if permission_name == "read_messages":
                aids_cant_see = permission_value is not True
                break
        if aids_cant_see:
            return True
    return False


async def init_censor():
    bot.uncensored_channels = []
    for channel in bot.server.text_channels:
        do_not_censor = bot.channels_without_censoring is not None and channel.id in bot.channels_without_censoring
        if do_not_censor or await is_mod_chat(channel):
            bot.uncensored_channels.append(channel.id)


# noinspection PyUnusedLocal
@bot.client.event
async def on_guild_channel_update(before, after):
    await init_censor()


# noinspection PyUnusedLocal
@bot.client.event
async def on_guild_channel_create(channel):
    await init_censor()


# noinspection PyUnusedLocal
@bot.client.event
async def on_guild_channel_delete(channel):
    await init_censor()


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


async def bot_cmd_censor(message):
    if message.channel.id in bot.uncensored_channels:
        return
    if await should_censor_message(message.content):
        await message.delete()
        embed = Embed()
        embed.title = f"Bad Language in #{message.channel.name}"
        embed.description = f"{message.author.mention}, Please don't use bad language 😟\n"
        embed.description += "Also, please don't attempt to bypass this chat filter or you will get in trouble."
        if message.author.bot:
            if message.channel.id not in [bot.channels["in_game"].id, bot.channels["server_console"].id]:
                embed.description = "Somehow, this bot sent bad language. Please tell a staff member if you identify " \
                                    "the cause. "
                await message.channel.send(embed=embed)
        else:
            try:
                await message.author.send(embed=embed)
            except Exception:
                embed.title = "Bad Language"
                await message.channel.send(embed=embed)


async def init_profiles():
    bot.file_profiles = "profiles.json"
    bot.minecraft_profiles = {}
    try:
        with open(bot.file_profiles, "r") as json_file:
            bot.minecraft_profiles = json.load(json_file)
    except FileNotFoundError:
        await save_player_info()


async def init_discord_verify():
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
                discord_username = f"{member.name}#{member.discriminator}"
            bot.discord_to_minecraft[discord_id] = {"minecraft_username": minecraft_username,
                                                    "discord_username": discord_username}
            bot.minecraft_to_discord[minecraft_username.lower()] = discord_id
    except FileNotFoundError:
        pass
    with open(bot.file_profile_links, "w") as json_file:
        json.dump(bot.discord_to_minecraft, json_file, indent=4)


async def bot_cmd_discord_verify(message):
    if message.guild is not None or message.author.id != bot.client.user.id:
        return
    msg_split = message.content.split("Your Discord account has been linked to ", 1)
    if len(msg_split) <= 1:
        return
    recipient = message.channel.recipient
    minecraft_username = msg_split[1].split(" ")[0]
    bot.discord_to_minecraft[recipient.id] = {
        "minecraft_username": minecraft_username,
        "discord_username": f"{recipient.name}#{recipient.discriminator}"
    }
    existing = minecraft_username.lower() in bot.minecraft_to_discord
    bot.minecraft_to_discord[minecraft_username.lower()] = recipient.id
    with open(bot.file_profile_links, "w") as json_file:
        json.dump(bot.discord_to_minecraft, json_file, indent=4)
    await bot.channels["server_console"].send(
        f"{recipient.mention} ({recipient.name}#{recipient.discriminator}) has linked their Minecraft account\n"
        f"`{minecraft_username}`"
    )

    if not existing:
        rcon_credentials = bot.minecraft_rcon
        with Client(rcon_credentials["host"], rcon_credentials["port"], passwd=rcon_credentials["password"]) as c:
            c.run(f"crazycrate give physical Boost 1 {minecraft_username}")
        await recipient.send(
            "For verifying, you have been given 1 Boost key!\n"
            "If you do not see it, please run the ``/keys`` command to see if you have a virtual key.\n"
            "If you did not receive a key, please contact staff."
        )

    try:
        recipient_member = bot.server.get_member(recipient.id)
        await recipient_member.add_roles(bot.roles["player"])
        await recipient_member.remove_roles(bot.roles["guest"])
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
            discord_username = f"{member.name}#{member.discriminator}"
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


# noinspection PyTypeChecker
async def cmd_player_info(message):
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
            embed.description = "**Could not find any player information on you!**\nHave you registered with the " \
                                "in-game command \"/discordsrv link\"? "
        else:
            if minecraft_target is not None:
                search_type = "Minecraft"
                target = minecraft_target
            else:
                search_type = "Discord"
                target = await find_server_member(discord_id=discord_target)
                target = discord_target if target is None else target.display_name
            embed.description = f"**Could not find any player information for {search_type} user \"**{target}**\"!**"
        await message.channel.send(embed=embed)
        await message.remove_reaction("⌛", bot.client.user)
        return
    # todo: rewrite the logic so pycharm doesn't give a breaking suggestion
    elif profile == False:
        if len(args) == 1:
            embed.description = "**Could not find you as a Discord user in the Discord server!**\nSomething might be " \
                                "wrong... "
        else:
            embed.description = f"**Could not find Discord user **\"{discord_target}\"** in the Discord server!**"
        await message.channel.send(embed=embed)
        await message.remove_reaction("⌛", bot.client.user)
        return

    if profile["discord_username"] == "N/A":
        discord_user_entry = "N/A"
    elif profile["discord"] == "N/A" and (not profile["discord_username"].endswith(" (Left Discord)")):
        discord_user_entry = f"<@{profile['discord']}>"
    else:
        discord_user_entry = profile["discord_username"]
    embed.add_field(name="Discord", value=discord_user_entry)
    embed.add_field(name="Minecraft", value=profile["username"])
    embed.set_footer(text=await convert_minecraft_uuid(profile["uuid"]))
    embed.set_thumbnail(url=profile["avatar"])
    if bot.server_online:
        player_online = False
        try:
            server = MinecraftServer.lookup("play.jellycraft.net")
            query = server.query()
            if profile["username"] in query.players.names:
                player_online = True
            embed.add_field(name="Status on Minecraft", value="Online" if player_online else "Offline")
        except Exception:
            pass
        profile["essentials"] = await get_essentials_profile(profile["uuid"])
        local_time = None
        if profile["essentials"] is not False and "ipAddress" in profile["essentials"]:
            ip = profile["essentials"]["ipAddress"]
            try:
                r = requests.get(bot.ip_geolocation_api.format(ip_address=ip)).json()
                local_hour, local_minute, local_am_pm = r["time_12"].replace(" ", ":").split(":")
                local_time = f"{local_hour}:{local_minute} {local_am_pm}\n*({r['date']})*"
            except Exception:
                error = format_exc()
                await log_error("[IPTimeZone Error] " + error)
        embed.add_field(name="Local Time", value=local_time if local_time is not None else "ERROR")

        if profile["essentials"] is not False and "timestamps" in profile["essentials"]:
            if player_online:
                online = profile["essentials"]["timestamps"]["login"] / 1000
                online = time.time() - online
                play_time = await get_english_timestamp(online)
                embed.add_field(name="Playing since", value=play_time + " ago" if play_time is not None else "ERROR")
            else:
                offline = profile["essentials"]["timestamps"]["logout"] / 1000
                offline = time.time() - offline
                last_played = await get_english_timestamp(offline)
                embed.add_field(name="Last Played", value=last_played + " ago" if last_played is not None else "ERROR")
        else:
            embed.add_field(name="Playtime/Offline Since", value="ERROR")

    await message.remove_reaction("⌛", bot.client.user)
    await message.channel.send(embed=embed)


async def cmd_players(message):
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
                description_rows = []
                for player in query.players.names:
                    joined_description = "\n".join(description_rows)
                    if len(joined_description) > 1850:
                        embed.description = joined_description
                        await message.channel.send(embed=embed)
                        description_rows = []
                        embed.title = ""
                    description_rows.append(player)
                joined_description = "\n".join(description_rows)
                embed.description = joined_description

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
            await log_error(f"[{get_est_time()}] ERROR: Could not find member \"{member_id}\".")
            return False
    try:
        if not member.guild_permissions.manage_guild:
            return False
    except Exception:
        return False
    return True


@tasks.loop(seconds=120.0)
async def coroutine_change_emoji_for_channel():
    for channel_id in bot.random_emoji_channels:
        channel = bot.server.get_channel(channel_id)
        random_emoji = random.choice(bot.random_emojis)
        name_format = bot.random_emoji_channels[channel_id]
        new_channel_name = name_format.format(emoji=random_emoji)
        await channel.edit(name=new_channel_name)


@tasks.loop(seconds=2)
async def coroutine_server_status():
    server = MinecraftServer.lookup(bot.minecraft_rcon["host"])
    try:
        status = server.status()
        server_status = f"{status.players.online}/{status.players.max} players"
        bot.server_online = True
    except Exception:
        bot.server_online = False
        server_status = "[SERVER IS DOWN]"
    if server_status != bot.server_status:
        bot.server_status = server_status
        await bot.client.change_presence(activity=discord.Game(name=bot.server_status, type=0))


@tasks.loop(seconds=30)
async def coroutine_force_server_status():
    await bot.client.change_presence(activity=discord.Game(name=bot.server_status, type=0))


@tasks.loop(seconds=300)
async def coroutine_nickname_sync():
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
        if discord_id in bot.user_ids_to_skip_nickname_sync:
            continue
        minecraft_name = profile["minecraft_username"]
        true_name = minecraft_name
        uuid_obj = await get_minecraft_uuid(minecraft_name)
        if "id" in uuid_obj:
            uuid = await convert_minecraft_uuid(uuid_obj["id"])
            essentials_profile = await get_essentials_profile(uuid)
            if essentials_profile is not False and essentials_profile is not None:
                if "nickname" in essentials_profile:
                    true_name = essentials_profile["nickname"]
                    color_tag_count = true_name.count("§")
                    for i in range(color_tag_count):
                        try:
                            color_char_index = true_name.index("§")
                            if color_char_index != -1:
                                color_to_remove = true_name[color_char_index:color_char_index + 2]
                                true_name = true_name.replace(color_to_remove, "")
                        except Exception:
                            print(format_exc())
                            pass
        if member.display_name.lower() != true_name.lower():
            needed_change += 1
            try:
                await member.edit(nick=true_name)
                changed += 1
            except Exception:
                error = format_exc()
                await log_error(f"[coroutine_nickname_sync] {member.display_name} / {minecraft_name}\n" + error)
    print(f"[NameSync] {found}/{len(bot.discord_to_minecraft)} found, {changed}/{needed_change} changed")


async def init_store():
    bot.file_store_lookup = "store_lookup.json"
    bot.store_lookup = {}
    try:
        with open(bot.file_store_lookup, "r") as json_file:
            bot.store_lookup = json.load(json_file)
    except FileNotFoundError:
        # Test item
        bot.store_lookup["Test3"] = {"friendly_name": "Test Item", "commands": [
            "crazycrate give physical Fortune 1 {username}",
            "crazycrate give physical Fortune 1 {username}"
        ]}
        with open(bot.file_store_lookup, "w") as json_file:
            json.dump(bot.store_lookup, json_file, indent=4)


async def is_player_online(username):
    player_online = False
    server = MinecraftServer.lookup(bot.minecraft_rcon["host"])  #
    try:
        query = server.query()
        if len(query.players.names) != 0:
            for player in query.players.names:
                if username.strip().lower() == player.strip().lower():
                    player_online = True
                    break
    except Exception:
        print(format_exc())
        return False
    return player_online


async def process_store_item(username, item):
    lookup = bot.store_lookup[item]
    print(f"[Process Store Item] {username} | {item} | {lookup}")
    rcon_credentials = bot.minecraft_rcon
    host, port, passwd = rcon_credentials["host"], rcon_credentials["port"], rcon_credentials["password"]
    with Client(host, port, passwd=passwd) as rcon:
        rcon.tellraw("@a", [
            {"text": "[JellyCraft Store] ", "color": "green"},
            {"text": username, "color": "white", "bold": "true"},
            {"text": " has purchased ", "color": "white"},
            {"text": lookup["friendly_name"], "color": "white", "bold": "true"},
            {"text": "!", "color": "white"}
        ])
        for cmd in lookup["commands"]:
            cmd_formatted = cmd.format(username=username)
            rcon.run(cmd_formatted)
            if cmd != cmd_formatted:  # If we've had to substitute a username, which we can assume is a targeted cmd,
                if not await is_player_online(username):
                    friendly_name = lookup["friendly_name"]
                    message = f"Thanks for your purchase of {friendly_name}!"
                    if "key" in friendly_name.lower():
                        message += " Since you were offline, it has been made virtual. Type /keys to see all your keys."
                    rcon.run(f"mail {username} {message}")


async def make_member_on_discord(username):
    username_lower = username.lower()
    if username_lower not in bot.minecraft_to_discord:
        await bot.channels["admin"].send(
            f"WARNING: Could not find Discord account for ``{username}``, was unable to make them a member on Discord.")
        return
    else:
        discord_id = bot.minecraft_to_discord[username_lower]
        member = bot.server.get_member(discord_id)
        await member.add_roles(bot.roles["member"])
        await member.remove_roles(bot.roles["player"])
        await member.remove_roles(bot.roles["guest"])


async def init_temp_purchases():
    bot.file_temp_purchases = os.path.join("store_log", "temporary_purchases.json")
    bot.temp_purchases = []
    try:
        with open(bot.file_temp_purchases, "r") as json_file:
            bot.temp_purchases = json.load(json_file)
    except FileNotFoundError:
        with open(bot.file_temp_purchases, "w") as json_file:
            json.dump(bot.temp_purchases, json_file, indent=4)


async def log_temp_purchase(username, item_name):
    temp_membership_obj = {}
    username_lower = username.lower()
    temp_membership_obj["time_stamp"] = time.time()
    temp_membership_obj["user_name"] = username_lower
    temp_membership_obj["item_name"] = item_name
    temp_membership_obj["discord_id"] = ""
    if username_lower in bot.minecraft_to_discord:
        temp_membership_obj["discord_id"] = bot.minecraft_to_discord[username_lower]
    else:
        await bot.channels["admin"].send(
            f"WARNING: ``{username}`` purchased temporary membership but was not found in the Discord.\nIf they join, "
            f"please manually give member to them and ensure they link their account before the end of the month.")
    bot.temp_purchases.append(temp_membership_obj)
    with open(bot.file_temp_purchases, "w") as json_file:
        json.dump(bot.temp_purchases, json_file, indent=4)


@tasks.loop(seconds=30)
async def coroutine_check_temp_purchases():
    try:
        with open(bot.file_temp_purchases, "r") as json_file:
            bot.temp_purchases = json.load(json_file)
    except FileNotFoundError:
        print(f"[coroutine_check_temp_purchases]: Missing file '{bot.file_temp_purchases}'?")
        return
    one_month = ((60 * 60) * 24) * 30
    reprocessed_temp_purchases = []
    for temp_purchase in bot.temp_purchases:
        expiry_date = float(temp_purchase["time_stamp"]) + one_month
        if time.time() > expiry_date:
            discord_id = temp_purchase["discord_id"]
            user_name = temp_purchase["user_name"]
            if discord_id == "":
                if user_name in bot.minecraft_to_discord:
                    discord_id = bot.minecraft_to_discord["user_name"]
                else:
                    await bot.channels["admin"].send(
                        f"WARNING: The membership purchased by ``{user_name}`` 30 days ago has now expired, but they "
                        f"are not in the discord. Can't revoke Discord membership.")
                    continue
            member = bot.server.get_member(int(discord_id))
            try:
                await member.remove_roles(bot.roles["member"])
                await member.add_roles(bot.roles["player"])
                await bot.channels["admin"].send(
                    f"The membership purchased by ``{user_name}`` 30 days ago has now expired, and their member role "
                    f"on Discord has been revoked.")
            except Exception:
                await bot.channels["admin"].send(
                    f"The membership purchased by ``{user_name}`` 30 days ago has now expired, but there was an error "
                    f"revoking their member role on Discord.")
                await bot.channels["admin"].send(f"```py\n{format_exc()}```")
        else:
            reprocessed_temp_purchases.append(temp_purchase)
    bot.temp_purchases = reprocessed_temp_purchases
    with open(bot.file_temp_purchases, "w") as json_file:
        json.dump(reprocessed_temp_purchases, json_file, indent=4)


async def log_store_transaction(username, item, amount_paid):
    try:
        numerical_amount_paid = float(amount_paid.replace("$", "").split(" ", 1)[0])  # "$10.53 USD" -> 10.53
    except Exception:
        await log_error("[log_store_transaction]\n" + format_exc())
        return

    desired_timezone = pytz.timezone("America/Toronto")
    current_est_time = datetime.now(desired_timezone)
    file_name = f"{current_est_time.year}-{current_est_time.month}.json"
    file_monthly_store_log = os.path.join("store_log", file_name)

    item_lookup = bot.store_lookup[item]
    friendly_item_name = item_lookup["friendly_name"]

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

    log_message = f"__[{log_entry['friendly_time']}]__\n``{username}`` bought ``{friendly_item_name}``\n{amount_paid}"
    await bot.channels["transactions"].send(log_message)

    if item in ["Membership_1Month", "Membership_Permanent"]:
        if item == "Membership_1Month":
            await log_temp_purchase(username, item)
        await make_member_on_discord(username)


async def bot_cmd_paypal_transaction(message):
    if message.channel.id != bot.channels["paypal_ipn_log"].id:
        return
    try:
        purchase = json.loads(message.content)
    except Exception:
        print(format_exc())
        return
    if "verified" in purchase and purchase["verified"]:
        username = purchase["user_name"]
        item = purchase["item_code"]
        amount_paid = purchase["total_friendly"]
        await log_store_transaction(username, item, amount_paid)
        await process_store_item(username, item)


async def upload_monthly_fundraising_progress(amount, file_name):
    args = bot.website_sftp
    host, username, password = args["host"], args["username"], args["password"]

    # Create the folder if it doesn't exist, and (over)write the file with the amount specified
    store_log_folder = "store_log"
    if not os.path.exists(store_log_folder):
        os.mkdir(store_log_folder)
    upload_file_path = os.path.join(store_log_folder, file_name)
    with open(upload_file_path, "w") as f:
        f.write(str(amount))

    try:
        opts = pysftp.CnOpts()
        # noinspection SpellCheckingInspection
        opts.hostkeys = None  # Force insecure, Todo: Use keys and make secure
        with pysftp.Connection(host=host, username=username, password=password, cnopts=opts) as sftp:
            sftp.cwd(f"/var/www/jellycraft.net/html/store/goals/")
            sftp.put(upload_file_path)
            # Remove the temporary file we made Todo: Upload binary without creating temp files
            if os.path.exists(upload_file_path):
                os.remove(upload_file_path)
    except Exception:
        await log_error(f"[upload_monthly_fundraising_progress]\n{format_exc()}")


@tasks.loop(seconds=30)
async def coroutine_update_site():
    desired_timezone = pytz.timezone("America/Toronto")
    current_est_time = datetime.now(desired_timezone)
    webserver_file_name = f"{current_est_time.year}-{current_est_time.month}.txt"

    file_name = f"{current_est_time.year}-{current_est_time.month}.json"
    file_monthly_store_log = os.path.join("store_log", file_name)

    current_raised = 0
    try:
        with open(file_monthly_store_log, "r") as json_file:
            bot.monthly_store_log = json.load(json_file)

        for purchased_item in bot.monthly_store_log:
            current_raised += float(purchased_item["amount_paid_numerical"])
    except FileNotFoundError:
        pass

    await upload_monthly_fundraising_progress(current_raised, webserver_file_name)


async def suggest_minecraft_profile_link(user):
    message = f"{user.mention} Thanks for joining the Discord!\nMake sure to link your Minecraft account for more " \
              f"features by using the ``/discord link`` command in-game! "
    try:
        await user.send(message)
    except Exception:  # User has DMs blocked
        try:
            await bot.channels["bot_spam"].send(message)
        except Exception:  # Failed to send a message for some reason
            error = format_exc()
            await log_error("[suggest_minecraft_profile_link] " + error)


async def bot_cmd_welcome(message):
    # Continue if message is not from bot, in welcome channel, and is a new_member type
    if message.author.id != bot.client.user.id:
        is_welcome_message = message.channel.id == bot.channels["welcome"].id and message.type.name == "new_member"
        if not is_welcome_message:
            return
    else:
        return
    try:
        new_member = message.author
        await message.delete()
        embed = Embed()
        embed.description = f"Welcome to the server, {new_member.display_name}#{new_member.discriminator}!"
        await message.channel.send(embed=embed)
        await suggest_minecraft_profile_link(new_member)
    except Exception:
        await log_error("[Welcome] " + format_exc())


async def bot_cmd_ingame_chat(message):
    if message.channel.id != bot.channels["in_game"].id or message.author.bot:
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
    embed.description = f"[{role}] {message.author.display_name}: {clean_everyone_content}"

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
                        clean_display_name = re.sub(r"(§[a-zA-Z0-9])", "", display_name)
                        embed.description = f"[{role}] {clean_display_name}: {clean_everyone_content}"
                    rcon_credentials = bot.minecraft_rcon
                    with Client(rcon_credentials["host"], rcon_credentials["port"],
                                passwd=rcon_credentials["password"]) as c:
                        c.tellraw("@a", [{"text": "[", "color": "white"}, {"text": role, "color": color},
                                         {"text": f"] {display_name}"},
                                         {"text": f": {message.clean_content}", "color": "white"}])
                        await message.channel.send(embed=embed)
                        await message.delete()
                else:
                    failed = True
                    failed_msg = f"Could not find Essentials Profile based on Minecraft UUID ({uuid}) " \
                                 f"of username ({username})! "
            else:
                failed = True
                failed_msg = f"Could not find UUID based on Minecraft username {username}!"
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
            # noinspection SpellCheckingInspection
            ftp.retrlines(f'RETR {uuid}.yml', yml_file.append)
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
            output = f"{uuid[:8]}-{uuid[8:12]}-{uuid[12:16]}-{uuid[16:20]}-{uuid[20:]}"
        except Exception:
            return False
    return output


@bot.client.event
async def on_message(message):
    if not bot.ready:  # Race condition
        return
    # Basic non-overridable shutdown command
    if message.author.id == bot.owner_id and message.content.lower().startswith("/off"):
        try:
            await message.delete()
        finally:
            await bot.client.close()
            await bot.client.logout()
            return
    message_cleaned = message
    message_cleaned.content = message_cleaned.content.replace("@everyone", "@ everyone").replace("@here", "@ here")
    for function_name in bot.bot_commands:
        # Execute every function that starts with bot_cmd_
        await globals()[function_name](message_cleaned)
    if message.author == bot.client.user or message.author.bot:
        return
    on_server = message.guild == bot.server
    not_whitelisted_channel = message.channel.id not in bot.channels_allowing_bot_commands
    not_admin = not await is_member_admin(message.author)
    if on_server and not_whitelisted_channel and not_admin:
        return
    # Execute every function that starts with cmd_
    for function_name in bot.commands:
        await globals()[function_name](message_cleaned)


async def config():
    bot.server = bot.client.get_guild(bot.server)
    bot.last_changed_emoji = 0
    # Instantiate channel objects
    for channel_name in bot.channels:
        channel_id = bot.channels[channel_name]
        bot.channels[channel_name] = bot.server.get_channel(channel_id)
    # Instantiate role objects
    for role_name in bot.roles:
        role_id = bot.roles[role_name]
        bot.roles[role_name] = bot.server.get_role(role_id)

    bot.server_status = "Querying server..."


@bot.client.event
async def on_ready():
    try:
        do_log(f"Bot name: {bot.client.user.name}")
        do_log(f"Bot ID: {bot.client.user.id}")
        await bot.client.change_presence(activity=discord.Game(name="Starting bot...", type=0))
        await config()
        bot.commands = [i for i in dir(__import__(__name__)) if i.startswith("cmd_")]
        bot.bot_commands = [i for i in dir(__import__(__name__)) if i.startswith("bot_cmd_")]
        bot.init_functions = [i for i in dir(__import__(__name__)) if i.startswith("init_")]
        bot.coroutines = [i for i in dir(__import__(__name__)) if i.startswith("coroutine_")]

        # Run any custom initialization functions
        for init_function_name in bot.init_functions:
            await globals()[init_function_name]()
        await bot.client.change_presence(activity=discord.Game(name=bot.server_status, type=0))

        # Start any custom coroutines
        for coroutine_name in bot.coroutines:
            globals()[coroutine_name].start()
        do_log("Ready\n\n")
        bot.ready = True
    except Exception:
        await log_error(f"\n\n\nCRITICAL ERROR: FAILURE TO INITIALIZE{format_exc()}")
        await bot.client.close()
        await bot.client.logout()
        exit()
        raise Exception("CRITICAL ERROR: FAILURE TO INITIALIZE")


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


def main():
    global bot
    bot.ready = False
    do_log("Loading Config")

    load_config_to_bot()  # Load a json to the bot class
    load_dotenv(verbose=True)

    # Merge any env vars with config vars, and make variables easily accessible
    do_log(f"Discord token: {censor_text(os.getenv('DISCORD_TOKEN'))}")
    bot.minecraft_ftp = {
        "host": os.getenv("MINECRAFT_FTP_HOST"),
        "username": os.getenv("MINECRAFT_FTP_USERNAME"),
        "password": os.getenv("MINECRAFT_FTP_PASSWORD")
    }
    bot.minecraft_rcon = {
        "host": os.getenv("MINECRAFT_RCON_HOST"),
        "port": int(os.getenv("MINECRAFT_RCON_PORT")),
        "password": os.getenv("MINECRAFT_RCON_PASSWORD")
    }
    bot.website_sftp = {
        "host": os.getenv("WEBSITE_SFTP_HOST"),
        "username": os.getenv("WEBSITE_SFTP_USERNAME"),
        "password": os.getenv("WEBSITE_SFTP_PASSWORD")
    }

    bot.ip_geolocation_api = bot.ip_geolocation_api.format(api_key=os.getenv("IPGEOLOCATIONIO_KEY"),
                                                           ip_address="{ip_address}")

    # DiscordPy tasks
    do_log("Loaded Config")
    do_log("Logging in")
    bot.client.run(os.getenv('DISCORD_TOKEN'))
    do_log("Logging out")


if __name__ == '__main__':
    main()
