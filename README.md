# AP Debate Matchmaking Bot

A Discord bot for managing matchmaking queues and round allocations for Asian Parliamentary (AP) Debate format competitions.

## Features

- **Automated Matchmaking Queue**: Users join a queue and are automatically matched when thresholds are reached
- **No Permission Requirements**: Everyone can use `/queue` and `/leave` commands
- **Multiple Round Types**:
  - 5 Players: Double Iron Round (2v2 + 1 Judge)
  - 6 Players: Single Iron Round (3v2 + 1 Judge)
  - 7+ Players: Standard Round (3v3 + Judges)
- **Host Controls**: Dedicated host channel with buttons to start rounds
- **Flexible Allocation System**: Complete UI for adjusting team compositions, swapping members, and toggling team types
- **Interactive Embeds**: Clean, organized displays for lobby status and round allocations
- **FREE Hosting**: Configured for Railway's free tier

## Quick Start

**New to this?** → Start with [START_HERE.md](START_HERE.md)

**Ready to deploy?** → Follow [SETUP_GUIDE.md](SETUP_GUIDE.md)

**Need quick info?** → Check [QUICK_REFERENCE.md](QUICK_REFERENCE.md)

## Project Structure

```
debate.gg/
├── main.py                 # Bot entry point
├── config.py              # Configuration management
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (create from .env.example)
├── .env.example          # Example environment configuration
├── .gitignore            # Git ignore rules
├── START_HERE.md         # Start here!
├── SETUP_GUIDE.md        # Complete setup guide
├── QUICK_REFERENCE.md    # Quick reference
├── RAILWAY_DEPLOY.md     # Railway deployment guide
├── README.md             # This file
├── railway.json          # Railway configuration
├── nixpacks.toml         # Nixpacks build config
├── runtime.txt           # Python version
├── cogs/
│   ├── __init__.py
│   ├── matchmaking.py    # Queue and matchmaking logic
│   └── adjustment.py     # Allocation adjustment UI
└── utils/
    ├── __init__.py
    ├── models.py         # Data models (DebateRound, Teams, etc.)
    └── embeds.py         # Embed builders
```

## Commands

### For Everyone
- `/queue` - Join the matchmaking queue
- `/leave` - Leave the queue

### For Admins Only
- `/clearqueue` - Clear the entire queue

## How It Works

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

## Deployment

### FREE Hosting on Railway

This bot is configured for Railway's free tier:
- $5/month in free credits
- ~500 hours/month (~21 days of 24/7 uptime)
- Perfect for small-to-medium debate servers

**Deployment Guide**: See [RAILWAY_DEPLOY.md](RAILWAY_DEPLOY.md)

### Requirements

- Python 3.10+
- Discord Bot Token
- Server with admin permissions

### Setup

1. **Clone the repository**:
   ```bash
   git clone <your-repo-url>
   cd debate.gg
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your values
   ```

4. **Run the bot**:
   ```bash
   python main.py
   ```

**For detailed setup instructions**, see [SETUP_GUIDE.md](SETUP_GUIDE.md)

## Configuration

Required environment variables (in `.env`):

```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_guild_id_here
LOBBY_CHANNEL_ID=your_lobby_channel_id_here
HOST_CHANNEL_ID=your_host_channel_id_here
HOST_ROLE_ID=your_host_role_id_here  # Optional
```

## Technical Details

### Architecture

- **Bot Framework**: py-cord (Discord.py fork)
- **Design Pattern**: Cog-based modular architecture
- **State Management**: In-memory (can be extended to SQLite)
- **UI Components**: Discord.py Views, Buttons, Modals, Selects

### Key Components

- **Matchmaking Cog**: Queue management, threshold detection, round allocation
- **Adjustment Cog**: Interactive UI for allocation modifications
- **Data Models**: Clean dataclasses for teams, judges, rounds, and queue
- **Embed Builders**: Consistent, professional Discord embeds

### Extensibility

The bot is designed to be easily extended:
- Add new round types in `utils/models.py`
- Customize team positions in `config.py`
- Add new commands in the cogs
- Implement persistence with SQLite

## Troubleshooting

### Bot doesn't respond to slash commands

- Wait up to 1 hour for commands to register globally
- Verify bot has `applications.commands` scope
- Check bot is online and GUILD_ID is correct

### "Configuration Error" on startup

- Check `.env` file exists and has all required values
- Verify all IDs are valid numbers (no quotes needed)

### Bot can't send messages

- Verify bot has permissions in lobby and host channels
- Check channel IDs in `.env` are correct

### "Privileged intent not enabled" error

- Go to Discord Developer Portal
- Enable Server Members Intent and Message Content Intent

**For more help**, see [SETUP_GUIDE.md](SETUP_GUIDE.md) Troubleshooting section

## Contributing

Contributions are welcome! The codebase is well-documented and modular.

## License

This project is provided as-is for educational and competitive debate purposes.

## Support

- Check [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions
- See [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for quick answers
- Review [RAILWAY_DEPLOY.md](RAILWAY_DEPLOY.md) for deployment help

---

**Ready to get started?** Open [START_HERE.md](START_HERE.md)!
