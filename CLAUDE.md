# Debate.gg - Discord Debate Matchmaking Bot

## Project Overview
A Discord bot for matchmaking debate rounds. Users queue up as debaters or judges in either 1v1 or AP (Asian Parliamentary) format. When enough players queue, the bot auto-creates a round with random allocation, participants confirm, channels are created, and the chair judge manages the round.

## Tech Stack
- **Python 3.10+** with **py-cord** (not discord.py) for Discord API
- Cog-based architecture with `discord.ext.commands`
- Environment variables via `python-dotenv`
- Guild-specific slash commands via `debug_guilds`

## Architecture

### Cogs (2 active)
- `cogs/matchmaking.py` — Queue management, round allocation, lobby display
- `cogs/rounds.py` — Participant confirmation, channel creation, chair judge controls, prep timer, round completion

### Key Files
- `main.py` — Bot class, cog loading, command sync
- `config.py` — Environment config (DISCORD_TOKEN, GUILD_ID, LOBBY_CHANNEL_ID, prep times)
- `utils/models.py` — Data models: DebateRound, DebateTeam, JudgePanel, MatchmakingQueue
- `utils/embeds.py` — All Discord embed builders (EmbedBuilder class with static methods)

### Data Models
- **FormatType**: `ONE_V_ONE`, `AP`
- **RoundType**: `PM_LO` (1v1), `DOUBLE_IRON` (2v2), `SINGLE_IRON` (3v2), `STANDARD` (3v3)
- **TeamType**: `SOLO` (1), `IRON` (2), `FULL` (3)
- **MatchmakingQueue**: Separate debater/judge lists per format, threshold detection
- **DebateRound**: Teams, judges, motion, channel IDs, category ID, format label

## Round Lifecycle Flow
1. Users `/queue` as debater/judge for 1v1 or AP
2. `check_matchmaking_threshold()` auto-detects when enough players queue
3. Bot auto-creates round with random team allocation (shuffled)
4. Participant confirmation sent to lobby channel (90s timeout, all must confirm)
5. On all confirm → private category + 5 channels created (text, debate VC, gov-prep VC, opp-prep VC, judges VC)
6. Chair judge enters motion via "Enter Motion" button in text channel
7. Chair judge clicks "Start Prep" → timer starts (15 min 1v1 / 30 min AP)
8. Timer expires → bot auto-moves debaters from prep VCs to debate VC
9. Judge clicks "Mark Round Complete" → all channels + category deleted

## Channel Permissions
- **Category + Text + Debate VC**: All round participants can see/access
- **Gov Prep VC**: Government team members only
- **Opp Prep VC**: Opposition team members only
- **Judges VC**: Judges only
- **@everyone**: Denied view/connect on all round channels
- **Bot**: Full permissions including `move_members` and `manage_channels`

## Environment Variables (.env)
```
DISCORD_TOKEN=       # Required
GUILD_ID=            # Required - server ID for guild-specific commands
LOBBY_CHANNEL_ID=    # Required - where lobby embed + confirmations appear
```

## Queue Thresholds
- **1v1**: 2 debaters + 1 judge
- **Double Iron**: 4 debaters + 1 judge
- **Single Iron**: 5 debaters + 1 judge
- **Standard**: 6+ debaters + 1+ judges

## Important Patterns
- py-cord button callbacks require `(self, button, interaction)` signature even if `button` is unused
- Persistent views use `custom_id` parameter and `timeout=None` to survive bot restarts
- `current_round` on the Matchmaking cog blocks new rounds during confirmation
- `active_rounds` dict tracks rounds with created channels (keyed by round_id)
- Re-queuing on cancel: `debate_round.format_label` determines which queue to return participants to
- Prep timer uses `asyncio.sleep()` in a background task, cancellable via `debate_round._prep_task`

## Branch Info
- `main` branch: Has older multi-lobby system
- `single-queue` branch: Current development branch with single global queue, format selection, chair judge controls
