#About
A contracted Discord bot for a Minecraft Server. Uses a prototyping overhead framework instead of discord.py standard command and event framework. Pending rewrite to standard discord.py format.


# Functions (and items to manually test):
## Basic Functions
1. Welcome functionality 
    - Keeps join log accurate in case of bot failure by detecting and deleting Discord's default greeting (would not be deleted if bot is offline)
    - Custom welcome messages
    - DM a user with recommendations about linking Minecraft account
    - Pings them in the bot commands channel if they have DMs turned off
2. Censor swear words from people and bots, except for:
    - Chats that only roles above a certain role (Aid) can see
    - Custom-specified channels in the config
3. Routes any chat messages in a configurable channel from the Discord server to in-game chat
    - Mimics nickname and role prefix/color handling, indistinguishable from in-game chat
    - Enforces censor and does not send anything in-game that triggers the Censor function
4. Monitor verifications that occur via "DiscordSRV" plugin, and
    - Store Minecraft-Discord relations in a local db
    - If the minecraft name is not in the local db, give them a bonus item ingame
5. Get a list of players online by running "/players", info provided via querying (with friendly handling of exceptions thrown by server being offline)
6. Change an emoji for channel(s) to a random emoji from the config
7. Change the bot's status to reflect the playercount (or offline status) of the Minecraft server by:
    - Querying the server and intelligently comparing the current status it has stored for the Minecraft server, and updating if different (to avoid discord rate limits)
    - Every 30 seconds, force the server status that what is currently stored (to override any accidental status sets by "DiscordSRV")
8. Get information about a player by running "/pinfo" with fail-safe friendly error response messages every step of the way.
    - Will target the first matching condition: 
        - If no name specified, the Discord of the person who ran the command
        - Any matching stored Minecraft username
        - Any Discord user pinged while running the command
        - Any Discord user who's numerical ID matches
        - Any exact Discord username in the server
        - Any exact Discord nickname in the server
        - Any Discord username that starts with the name specified ("jelly" would find "JellyBot")
        - Any Discord nickname that starts with the name specified
        - Any Discord username that has the name specified in it ("elly" would find "JellyBot")
        - Any Discord nickname that has the name specified in it
        - Send failure message if none of the above could apply
     - Get Discord or Minecraft username (whichever is missing) from what is stored in local db
     - Gets Minecraft UUID by online API
     - Uses UUID to get skinned avatar screenshot via online API
     - Checks (and shows) if the player is currently in-game
     - Connects to the Minecraft server via FTP and uses their UUID to get their profile from the "Essentials" plugin
     - Checks (and shows) how long they have been playing (or offline since) in a friendly format ("2 hours, 31 minutes ago")
     - Checks (and shows) what time it currently is for that player based on where they are in the (real) world
8. Every 30 seconds, syncs Discord name to the Minecraft username (or nickname if present, found by downloading their "Essentials" profile) of every linked user
    - Users can be made exempt from this by adding their Discord ID to the config
## Advanced Functions
### Store
  todo


