# About
A contracted Discord bot for a Minecraft Server. Uses a prototyping overhead framework instead of discord.py standard command and event framework. Pending rewrite to standard discord.py format.


# Functions (and items to manually test):
## Auxiliary Functions
1. Player Playtime Barchart Race
    - Scan the message logs in the log channel on Discord and create time data on users based on leaves/joins
    - Compile the data into a chartable format
    - Create an animation

![Bar Chart Animation](https://i.imgur.com/BlgrwLy.gif)
## Basic Functions
1. Welcome functionality 
    - Keeps join log accurate in case of bot failure by detecting and deleting Discord's default greeting (would not be deleted if bot is offline)
    - Custom welcome messages
    - DM a user with recommendations about linking Minecraft account
    - Pings them in the bot commands channel if they have DMs turned off
    - Changes role if detected failure from other bots responsible for changing roles on join
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
~~The challenge with registering payment was no additional cost, unlimited transactions, and 24/7 uptime. There are no first/second-party methods at the time of writing, the closest thing is Paypal's IPN API which requires you to build, host and maintain an endpoint. ~~
Paypal randomizes their email formats without warning (words used, layout, etc.), so the previous method was unreliable. an endpoint has built to support Paypal's IPN system, using Heroku free dynamo, which hibernates after 30 minutes of inactivity. Exceeding the free monthly limits is next to impossible.
The current process is,
1. "Buy Now" buttons are created on PayPal's page, with
    - Specific "Item Codes"
    - An input for a username, specifically called "Minecraft Username"
2. A modified and better looking version of the button code is placed on the website. The username field is made required.
~~3. After a user submits their transaction, an email is dispatched to the email address attached to the account.~~
~~4. This account has forwarding set up to a seperate untouched account that only the bot has access to (and for good reason, security is required to be lower for this to work and having that on a main account is a bad idea)~~
~~5. Any incoming message with a certain critera is automatically moved from Inbox to a "PayPal" folder~~
~~6. At an interval, the bot logs into this email address and searches for unread "PayPal" emails. ~~
~~7. If it finds any, it automatically marks them as "Read" to avoid duplication, and parses out the Item Code, Cost, and Username~~
3. The backend running on Heroku actively listens for any PayPal IPN requests sent to it, verifies it, and sends the results to a transaction backend channel on the Discord, for logging/user-friendly debugging
4. It takes the Item Code and opens our store_lookup.json. There, the item code should be present with additional information such as "friendly name" and "commands to run".
5. It open an RCON connection to the Minecraft Server and give the user whatever they purchased.
    - One of the items are keys. Keys cannot be given physically while offline, so instead they are given "virtually" and they player is sent a "mail" that will prompt them to check their virtual keys once they log back in.
6. It then logs the Username, Friendly Name, and Cost in a Discord channel (configurable)
7. It will add that transaction to its internal database, which is used later.
8. To avoid race conditions, every 30 seconds, the bot opens the transaction log for that month and calculates the total. 
9. The total is then uploaded to a file on the website's server under the "YYYY-MM.txt" format.
10. The website is set to, on load, check for this file on its server. If it doesn't exist, it assumes 0. If it does exist, it takes that number and applies it to the "Monthly Goal" progress meter.
