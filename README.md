# AP Debate Matchmaking Bot

A Discord bot for managing matchmaking queues and round allocations for Asian Parliamentary (AP) Debate format competitions.

## Features

- **Automated Matchmaking Queue**: Users join a queue and are automatically matched when thresholds are reached
- **Multiple Round Types**:
  - 5 Players: Double Iron Round (2v2 + 1 Judge)
  - 6 Players: Single Iron Round (3v2 + 1 Judge)
  - 7+ Players: Standard Round (3v3 + Judges)
- **Host Controls**: Dedicated host channel with buttons to start rounds
- **Flexible Allocation System**: Complete UI for adjusting team compositions, swapping members, and toggling team types
- **Interactive Embeds**: Clean, organized displays for lobby status and round allocations

## Project Structure

```
debate.gg/
├── main.py                 # Bot entry point
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create from .env.example)
├── .env.example          # Example environment configuration
├── .gitignore            # Git ignore rules
├── README.md             # This file
├── cogs/
│   ├── __init__.py
│   ├── matchmaking.py    # Queue and matchmaking logic
│   └── adjustment.py     # Allocation adjustment UI
└── utils/
    ├── __init__.py
    ├── models.py         # Data models (DebateRound, Teams, etc.)
    └── embeds.py         # Embed builders
```

## Prerequisites

- Python 3.8 or higher
- pip (Python package installer)
- A Discord Bot Token
- Server Administrator permissions on your Discord server

## Setup Instructions

### 1. Create a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Navigate to the "Bot" section in the left sidebar
4. Click "Add Bot"
5. Under "Privileged Gateway Intents", enable:
   - Server Members Intent
   - Message Content Intent
6. Click "Reset Token" and copy your bot token (you'll need this later)

### 2. Invite the Bot to Your Server

1. In the Developer Portal, go to "OAuth2" > "URL Generator"
2. Select the following scopes:
   - `bot`
   - `applications.commands`
3. Select the following bot permissions:
   - Read Messages/View Channels
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Use Slash Commands
   - Mention Everyone (optional, for host role pings)
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

### 3. Get Required IDs

You'll need to enable Developer Mode in Discord to copy IDs:

1. In Discord, go to User Settings > Advanced > Enable "Developer Mode"
2. Get your **Guild ID** (Server ID):
   - Right-click your server icon
   - Click "Copy Server ID"
3. Get your **Host Channel ID**:
   - Right-click the channel where hosts will receive notifications
   - Click "Copy Channel ID"
4. Get your **Lobby Channel ID**:
   - Right-click the channel where the lobby embed will be displayed
   - Click "Copy Channel ID"
5. (Optional) Get your **Host Role ID**:
   - Go to Server Settings > Roles
   - Right-click the host role
   - Click "Copy Role ID"

### 4. Clone and Configure

```bash
# Clone or download the project
cd debate.gg

# Install dependencies
pip install -r requirements.txt

# Copy the example environment file
cp .env.example .env

# Edit .env with your configuration
# Use a text editor to fill in your values
```

Edit the `.env` file with your values:

```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_guild_id_here
HOST_CHANNEL_ID=your_host_channel_id_here
LOBBY_CHANNEL_ID=your_lobby_channel_id_here
HOST_ROLE_ID=your_host_role_id_here  # Optional
```

### 5. Run the Bot

```bash
python main.py
```

You should see output like:
```
Loading extensions...
✓ Loaded cogs.matchmaking
✓ Loaded cogs.adjustment
Matchmaking cog loaded
Adjustment cog loaded
Logged in as YourBotName (ID: 123456789)
Connected to 1 guild(s)
------
```

## Usage

### User Commands

- `/queue` - Join the matchmaking queue
- `/leave` - Leave the matchmaking queue

### Admin Commands

- `/clearqueue` - Clear the entire queue (requires Administrator permission)

### How It Works

1. **Joining the Queue**: Users run `/queue` to join the matchmaking pool. The lobby embed updates automatically to show who's in queue.

2. **Matchmaking Thresholds**:
   - When 5 players join, hosts can start a Double Iron Round (2v2)
   - When 6 players join, hosts can start a Single Iron Round (one team has 3, one has 2)
   - When 7+ players join, hosts can start a Standard Round (3v3) or wait for more panelists

3. **Starting a Round**: The host clicks a button in the host channel to start the round. The bot randomly assigns users to positions.

4. **Adjusting Allocations**: Before confirming, hosts can:
   - Swap any two members' positions
   - Toggle teams between Full (3 debaters) and Iron (2 debaters)
   - Move debaters to judge roles
   - Move judges to debater roles

5. **Confirming**: Once satisfied with allocations, the host clicks "Confirm & Start Round", enters the motion, and the round begins!

## Deployment for Production

### Option 1: Local Server / VPS

For running on a dedicated server or VPS:

1. Follow the setup instructions above
2. Use a process manager like `systemd` or `pm2` to keep the bot running

#### Using systemd (Linux)

Create a service file `/etc/systemd/system/debate-bot.service`:

```ini
[Unit]
Description=AP Debate Matchmaking Bot
After=network.target

[Service]
Type=simple
User=youruser
WorkingDirectory=/path/to/debate.gg
ExecStart=/usr/bin/python3 /path/to/debate.gg/main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl enable debate-bot
sudo systemctl start debate-bot
sudo systemctl status debate-bot
```

#### Using PM2 (Node.js process manager)

```bash
# Install PM2
npm install -g pm2

# Start the bot
pm2 start main.py --name debate-bot --interpreter python3

# Save the process list
pm2 save

# Set PM2 to start on boot
pm2 startup
```

### Option 2: Cloud Hosting (Heroku)

1. Create a `Procfile` in the project root:
   ```
   worker: python main.py
   ```

2. Create a `runtime.txt` to specify Python version:
   ```
   python-3.10.12
   ```

3. Deploy to Heroku:
   ```bash
   heroku create your-app-name
   heroku config:set DISCORD_TOKEN=your_token
   heroku config:set GUILD_ID=your_guild_id
   heroku config:set HOST_CHANNEL_ID=your_host_channel_id
   heroku config:set LOBBY_CHANNEL_ID=your_lobby_channel_id
   git push heroku main
   heroku ps:scale worker=1
   ```

### Option 3: Docker

1. Create a `Dockerfile`:
   ```dockerfile
   FROM python:3.10-slim

   WORKDIR /app

   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   COPY . .

   CMD ["python", "main.py"]
   ```

2. Create a `docker-compose.yml`:
   ```yaml
   version: '3.8'

   services:
     bot:
       build: .
       env_file:
         - .env
       restart: unless-stopped
   ```

3. Run with Docker Compose:
   ```bash
   docker-compose up -d
   ```

### Option 4: Railway / Render

Both Railway and Render support Python apps with minimal configuration:

1. Connect your GitHub repository
2. Set environment variables in the platform's dashboard
3. The platform will auto-detect `requirements.txt` and deploy

## Troubleshooting

### Bot doesn't respond to slash commands

- Make sure you've enabled the bot scope and applications.commands when inviting
- Slash commands may take up to 1 hour to register globally. Use `debug_guilds` for instant updates during development.

### "Configuration Error" on startup

- Check that your `.env` file exists and has all required values
- Verify that all IDs are valid numbers (no quotes needed in .env)

### Bot can't send messages

- Verify the bot has permissions in the lobby and host channels
- Check that the channel IDs in `.env` are correct

### "Privileged intent not enabled" error

- Go to the Discord Developer Portal
- Enable Server Members Intent and Message Content Intent in the Bot section

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

## License

This project is provided as-is for educational and competitive debate purposes.

## Support

For issues or questions, please open an issue on the GitHub repository.
