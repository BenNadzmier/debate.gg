# Quick Start Guide

Get your AP Debate Matchmaking Bot running in 5 minutes!

## Prerequisites Checklist

- [ ] Python 3.8+ installed
- [ ] Discord account with server admin permissions
- [ ] Text editor for editing `.env` file

## Step-by-Step Setup

### 1. Create Discord Bot (3 minutes)

1. Go to https://discord.com/developers/applications
2. Click "New Application", name it "AP Debate Bot"
3. Go to "Bot" tab, click "Add Bot"
4. Enable these intents:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
5. Click "Reset Token" and **copy the token** (save it somewhere safe!)

### 2. Invite Bot to Server (1 minute)

1. In Developer Portal, go to "OAuth2" > "URL Generator"
2. Select scopes: `bot` and `applications.commands`
3. Select permissions:
   - ✅ Read Messages/View Channels
   - ✅ Send Messages
   - ✅ Embed Links
   - ✅ Use Slash Commands
4. Copy the URL, open in browser, select your server, authorize

### 3. Get Discord IDs (1 minute)

Enable Developer Mode: Discord Settings > Advanced > Developer Mode ✅

Then right-click and copy IDs for:
- Your server → "Copy Server ID"
- Host channel (where admins get notifications) → "Copy Channel ID"
- Lobby channel (where users see the queue) → "Copy Channel ID"

### 4. Install & Configure (1 minute)

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file from template
cp .env.example .env
```

Edit `.env` and paste your values:
```env
DISCORD_TOKEN=paste_bot_token_here
GUILD_ID=paste_server_id_here
HOST_CHANNEL_ID=paste_host_channel_id_here
LOBBY_CHANNEL_ID=paste_lobby_channel_id_here
```

### 5. Run! (10 seconds)

```bash
python main.py
```

You should see:
```
✓ Loaded cogs.matchmaking
✓ Loaded cogs.adjustment
Logged in as AP Debate Bot
```

## Test It Out

1. In your lobby channel, type `/queue`
2. The lobby embed should appear showing you in the queue!
3. Get 4 more people to join (or use alt accounts for testing)
4. When 5 people are queued, the host channel gets a notification
5. Click "Start Double Iron Round"
6. Adjust allocations as needed
7. Click "Confirm & Start Round" and enter a motion

## Next Steps

- Read [README.md](README.md) for full documentation
- See deployment options for running 24/7
- Customize team positions in [config.py](config.py)

## Common Issues

**Bot doesn't respond to `/queue`**
- Wait up to 1 hour for slash commands to register, or add your server ID to `debug_guilds` in main.py

**"Configuration Error" when starting**
- Check that `.env` file exists and all values are filled in (no quotes needed)

**Bot offline when you close terminal**
- See README.md for production deployment options (systemd, Docker, cloud hosting)

## Need Help?

Open an issue on GitHub or check the full README.md for troubleshooting.
