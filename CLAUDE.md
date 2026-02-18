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
- `utils/models.py` — Data models: DebateRound, DebateTeam, JudgePanel, MatchmakingQueue, Party
- `utils/embeds.py` — All Discord embed builders (EmbedBuilder class with static methods)

### Data Models
- **FormatType**: `ONE_V_ONE`, `AP`
- **RoundType**: `PM_LO` (1v1), `DOUBLE_IRON` (2v2), `SINGLE_IRON` (3v2), `STANDARD` (3v3)
- **TeamType**: `SOLO` (1), `IRON` (2), `FULL` (3)
- **MatchmakingQueue**: Separate debater/judge lists per format, threshold detection
- **DebateRound**: Teams, judges, motion, channel IDs, category ID, format label, ballot, judge_ratings, rated_debater_ids
- **Party**: Host + members (max 3), used for AP queue team grouping
- **SpeakerScore**: member, position_name, score (50-100 substantive, 25-50 reply)
- **Ballot**: judge, winner, gov_scores, opp_scores, gov_reply, opp_reply, validate() method
- **BallotDraft**: Accumulates state across the multi-step ballot flow (assignments, scores)
- **JudgeRating**: debater, score (1-10), optional feedback

## Round Lifecycle Flow
1. Users `/queue` as debater/judge for 1v1 or AP
2. `check_matchmaking_threshold()` auto-detects when enough players queue
3. Bot auto-creates round with random team allocation (shuffled)
4. Participant confirmation sent to lobby channel (90s timeout, all must confirm)
5. On all confirm → private category + 5 channels created (text, debate VC, gov-prep VC, opp-prep VC, judges VC)
6. Chair judge enters motion via "Enter Motion" button in text channel
7. Chair judge clicks "Start Prep" → timer starts (15 min 1v1 / 30 min AP)
8. Timer expires → bot auto-moves debaters from prep VCs to debate VC
9. Judge clicks "Submit Ballot" → two-page modal (winner + speaker scores)
10. Ballot validated → judge gets DM with results, debaters get "Rate Judge" DM
11. Debaters rate judge (1-10 + optional feedback) → receive full ballot results
12. After all debaters rate → judge gets aggregated ratings DM
13. Judge clicks "Mark Round as Complete" → confirmation → channels + category deleted

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

## Party System (AP Format)
Debaters can form parties (max 3 members) to be guaranteed on the same team in AP rounds.

### Commands
- `/invite @user` — Create/extend a party and DM the invited user with accept/decline buttons
- `/party` — View current party status (host, members, queue status)
- `/leaveparty` — Host: disbands entire party + removes all from queue. Member: leaves party + queue.

### Party Queue Rules
- Party host runs `/queue debater AP` to queue ALL party members together
- Non-host party members cannot `/queue` individually (told to ask host)
- Party host cannot queue for 1v1 or as judge while in a party
- `/leave` by host removes all party members from queue (party preserved)
- `/leave` by non-host member removes them from queue AND the party

### Party-Aware Allocation
- `_build_allocation_units()` groups party members into indivisible units
- Units are shuffled and placed on teams together (party members always on same side)
- `max_party_size` parameter on `get_threshold_type()` prevents party of 3 from triggering double iron (2v2)

### Storage (on Matchmaking cog, in-memory)
- `self.parties: dict[int, Party]` — host_id → Party
- `self.member_to_party: dict[int, int]` — member_id → host_id

## Ballot & Results System
After the debate, the judge submits a ballot with position assignments, speaker scores, and winner selection. Debaters only know their side (Gov/Opp) — the judge reports who spoke which position.

### Position Assignment
- Teams decide their own speaker order during the debate
- Confirmation/round embeds show members without position names (just mentions)
- Judge assigns positions via dropdown menus when submitting the ballot

### Reply Speeches (AP only, not 1v1)
- Each side has a reply speaker (last speaker for each team)
- Reply speaker can be PM/LO or DPM/DLO, never a Whip
- Reply speeches scored 25-50 (half the 50-100 substantive range)
- Reply score counts toward team total

### Ballot Flow — 1v1
1. Judge clicks "Submit Ballot" → `WinnerSelectView` (dropdown)
2. "Continue to Scores" button → `ScoreModal1v1` (PM + LO scores, 50-100)
3. Validation + `finalize_ballot()`: stores ballot, DMs judge results, DMs debaters with "Rate Judge" button

### Ballot Flow — AP
1. Judge clicks "Submit Ballot" → `WinnerSelectView` (dropdown)
2. "Next: Assign Gov Positions" → `GovAssignmentView` (position selects + reply select)
3. "Next: Assign Opp Positions" → `OppAssignmentView` (position selects + reply select)
4. "Continue to Scores" → `GovScoreModal` (substantive 50-100 + reply 25-50)
5. `OppScoreContinueView` (bridge button — can't chain modals)
6. `OppScoreModal` (substantive 50-100 + reply 25-50) → validation + finalize

### Assignment Validation
- All position selects must be filled
- No duplicate member assignments (each member exactly one position)
- Reply speaker cannot be assigned to a Whip position

### Score Validation
- Substantive scores: 50-100
- Reply scores: 25-50
- Winner's total (including reply) must be higher than loser's total

### Judge Rating Flow
1. Debaters click "Rate Judge" in DM → `RateJudgeModal` (score 1-10, optional feedback)
2. After submitting rating, debater receives full ballot results DM
3. After ALL debaters rate, judge receives aggregated ratings DM (average + individual feedback)

### Channel Deletion (separate from ballot)
- After ballot submission, "Mark Round as Complete" button appears
- Clicking it shows ephemeral confirmation dialog → channels deleted on confirm

### Views in cogs/rounds.py
- `SubmitBallotView` (persistent, custom_id=`submit_ballot:{round_id}`)
- `WinnerSelectView` (ephemeral, timeout=300)
- `ScoreModal1v1` (modal, 1v1 only)
- `GovAssignmentView` / `OppAssignmentView` (ephemeral, timeout=300, AP only)
- `GovScoreModal` / `OppScoreModal` (modals, AP only)
- `OppScoreContinueView` (ephemeral bridge, timeout=300)
- `PostBallotRoundCompleteView` (persistent, custom_id=`post_ballot_complete:{round_id}`)
- `ChannelDeletionConfirmView` (ephemeral, timeout=60)
- `RateJudgeView` (DM, timeout=None)

### Discord UI Limits
- Modals: max 5 InputText fields (3v3: 3 substantive + 1 reply = 4 per team)
- Views: max 5 action rows (3v3 assignment: 3 position selects + 1 reply select + 1 button = 5)
- Cannot chain modals directly; use ephemeral button bridge between GovScoreModal and OppScoreModal

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
