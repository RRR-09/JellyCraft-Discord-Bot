# region Standard Libraries
import json
import logging
import os
from datetime import datetime
from traceback import format_exc
import argparse
# endregion

# region External Libraries
from dotenv import load_dotenv  # pip install python-dotenv
import pytz  # pip install pytz

print(
    "Importing Discord")  # Importing discord.py can stall due to faulty PyNaCl versions, this helps with identification
import discord  # pip install -U discord.py[voice]

print("Imported Discord")


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


async def process_ingame_stats():
    actions = []
    processed_msgs = 0
    currently_online = []
    last_restart = 0
    async for message in bot.channels["in_game"].history(limit=None, oldest_first=True):
        if message.author != bot.client.user:
            continue
        if processed_msgs % 25 == 0:
            print(f"Writing {processed_msgs} entries to file...")
            with open("analytics.json", "w") as json_file:
                json.dump(actions, json_file, indent=4)
            processed_msgs += 1
        if len(message.embeds) == 0:
            if "Server has started" in message.content:
                action_obj = {"time": message.created_at.timestamp(), "user": None, "action": "Restart"}
                actions.append(action_obj)
                print(action_obj)
                for player in currently_online:
                    action_obj = {"time": message.created_at.timestamp(), "user": player, "action": "left"}
                    actions.append(action_obj)
                    print(action_obj)
                    processed_msgs += 1
                currently_online = []
                last_restart = message.created_at.timestamp()
            continue
        for embed in message.embeds:
            if embed.author != discord.Embed.Empty and embed.author.name != discord.Embed.Empty:
                try:
                    action_desc = embed.author.name
                    user = embed.author.name.split(" ", 1)[0]
                    if "left the server" in action_desc:
                        action = "left"
                        try:
                            currently_online.remove(user)
                        except Exception:
                            print(f"ERROR, {user} WAS NEVER ONLINE, ASSUMING ONLINE SINCE RESTART")
                            action_obj = {"time": last_restart, "user": user, "action": "joined"}
                            actions.append(action_obj)
                            processed_msgs += 1
                    elif "joined the server" in action_desc:
                        action = "joined"
                        currently_online.append(user)
                    elif "has made the advancement" in action_desc:
                        continue
                    else:
                        raise
                except Exception:
                    user = "ERROR"
                    action = embed.author.name
                action_obj = {"time": message.created_at.timestamp(), "user": user, "action": action}
                actions.append(action_obj)
                processed_msgs += 1
                print(action_obj)

    with open("analytics.json", "w") as json_file:
        json.dump(actions, json_file, indent=4)
    do_log("Completed in-game analytics")


async def config():
    bot.server = bot.client.get_guild(bot.server)
    # Instantiate channel objects
    for channel_name in bot.channels:
        channel_id = bot.channels[channel_name]
        bot.channels[channel_name] = bot.server.get_channel(channel_id)


@bot.client.event
async def on_ready():
    try:
        do_log(f"Bot name: {bot.client.user.name}")
        do_log(f"Bot ID: {bot.client.user.id}")
        await config()
        await process_ingame_stats()
    except Exception:
        await log_error(f"\n\n\nCRITICAL ERROR: FAILURE TO INITIALIZE{format_exc()}")
        await bot.client.close()
        await bot.client.logout()
        exit()
        raise Exception("CRITICAL ERROR: FAILURE TO INITIALIZE")


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
    # DiscordPy tasks
    do_log("Loaded Config")
    do_log("Logging in")
    bot.client.run(os.getenv('DISCORD_TOKEN'))
    do_log("Logging out")


if __name__ == '__main__':
    main()
