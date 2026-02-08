# Architecture Overview

This document explains the architecture and code structure of the AP Debate Matchmaking Bot.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Discord User                          │
│                    (Uses Slash Commands)                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                       Main Bot (main.py)                     │
│  - Event handling (on_ready, on_error)                      │
│  - Cog loading and management                               │
│  - Command error handling                                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
           ┌───────────┴───────────┐
           ▼                       ▼
┌──────────────────────┐  ┌──────────────────────┐
│  Matchmaking Cog     │  │   Adjustment Cog     │
│  ==================  │  │  ==================  │
│  - Queue management  │  │  - Allocation UI     │
│  - /queue command    │  │  - Swap controls     │
│  - /leave command    │  │  - Team toggles      │
│  - Threshold checks  │  │  - Motion input      │
│  - Round allocation  │  │  - Confirmation      │
│  - Host notifications│  │                      │
└──────────────────────┘  └──────────────────────┘
           │                       │
           └───────────┬───────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    Utility Modules                           │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  models.py   │  │  embeds.py   │  │  config.py   │      │
│  │  ==========  │  │  ==========  │  │  ==========  │      │
│  │  - Teams     │  │  - Lobby     │  │  - Settings  │      │
│  │  - Rounds    │  │  - Alerts    │  │  - Env vars  │      │
│  │  - Queue     │  │  - Allocs    │  │  - Constants │      │
│  │  - Judges    │  │  - Errors    │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Main Bot (`main.py`)

**Purpose**: Entry point and lifecycle management

**Key Responsibilities**:
- Initialize Discord bot with required intents
- Load cogs (plugins)
- Handle global errors
- Validate configuration on startup

**Key Classes**:
- `DebateBot(discord.Bot)`: Main bot class with event handlers

### 2. Matchmaking Cog (`cogs/matchmaking.py`)

**Purpose**: Queue management and round initialization

**Key Responsibilities**:
- Maintain the matchmaking queue
- Update lobby display in real-time
- Check for matchmaking thresholds (5, 6, 7+ users)
- Send host notifications when ready
- Randomly allocate users to teams and judge roles
- Clear queue after round starts

**Key Classes**:
- `Matchmaking(commands.Cog)`: Main cog class
- `HostControlView(discord.ui.View)`: Buttons for hosts to start rounds
- `LobbyView(discord.ui.View)`: Persistent lobby with leave button
- `StartRoundButton`: Initializes round allocation
- `WaitForPanelistsButton`: Keeps queue open for more judges

**Key Methods**:
- `initialize_lobby()`: Creates persistent lobby embed
- `update_lobby_display()`: Refreshes queue display
- `check_matchmaking_threshold()`: Checks if ready to start
- `create_round_allocation()`: Randomly assigns users to positions
- `show_allocation_interface()`: Displays adjustment UI

### 3. Adjustment Cog (`cogs/adjustment.py`)

**Purpose**: UI for adjusting round allocations

**Key Responsibilities**:
- Provide interactive controls for hosts
- Allow swapping members between positions
- Toggle teams between Full (3) and Iron (2) types
- Move members between debater and judge roles
- Handle motion input and round confirmation

**Key Classes**:
- `Adjustment(commands.Cog)`: Main cog class
- `AllocationAdjustmentView`: Main control panel with buttons
- `SwapMembersModal`: Modal for entering user IDs to swap
- `ToggleTeamTypeView`: Select which team to toggle
- `MoveToJudgeView`: Select debater to move to judge
- `MoveToDebaterView`: Select judge to move to team
- `TeamSelectionView`: Choose which team to join
- `MotionInputModal`: Enter debate motion and confirm

**UI Flow**:
```
Allocation Display
       │
       ├─> Swap Members → Modal → Refresh
       ├─> Toggle Team → Select Team → Refresh
       ├─> Move to Judge → Select Debater → Refresh
       ├─> Move to Debater → Select Judge → Select Team → Refresh
       └─> Confirm → Motion Modal → Final Embed
```

### 4. Data Models (`utils/models.py`)

**Purpose**: Data structures for debate system

**Key Classes**:

**`TeamType(Enum)`**
- `FULL`: 3 debaters
- `IRON`: 2 debaters

**`RoundType(Enum)`**
- `DOUBLE_IRON`: 5 people (2v2 + 1 judge)
- `SINGLE_IRON`: 6 people (3v2 or 2v3 + 1 judge)
- `STANDARD`: 7+ people (3v3 + judges)

**`DebateTeam`**
- Properties: `team_name`, `team_type`, `members`
- Methods: `add_member()`, `remove_member()`, `is_full()`, `get_position_name()`

**`JudgePanel`**
- Properties: `chair`, `panelists`
- Methods: `add_judge()`, `remove_judge()`, `get_all_judges()`

**`DebateRound`**
- Properties: `round_id`, `round_type`, `government`, `opposition`, `judges`, `motion`, `confirmed`
- Methods: `get_all_participants()`, `swap_members()`, `_find_member_location()`

**`MatchmakingQueue`**
- Properties: `users`, `lobby_message`
- Methods: `add_user()`, `remove_user()`, `clear()`, `size()`, `get_threshold_type()`

### 5. Embed Builders (`utils/embeds.py`)

**Purpose**: Generate Discord embeds for various displays

**Key Methods**:
- `create_lobby_embed()`: Shows queue status and thresholds
- `create_host_notification_embed()`: Alerts hosts when ready
- `create_allocation_embed()`: Displays team and judge assignments
- `create_confirmed_round_embed()`: Final round announcement
- `create_error_embed()`: Error messages
- `create_success_embed()`: Success confirmations

**Design Principles**:
- Consistent color scheme (blue for Gov, red for Opp)
- Clear hierarchy with field organization
- Mentions for user engagement
- Footer hints for user actions

### 6. Configuration (`config.py`)

**Purpose**: Centralized configuration management

**Key Features**:
- Loads environment variables from `.env`
- Validates required configuration on startup
- Defines team positions and judge roles
- Type-safe integer conversion for IDs

## Data Flow

### User Joins Queue

```
User: /queue
    ↓
Matchmaking.queue_command()
    ↓
queue.add_user(user) → Success?
    ↓ Yes
update_lobby_display() → Edit embed in lobby channel
    ↓
check_matchmaking_threshold() → Size >= 5?
    ↓ Yes
send_host_notification() → Send embed + buttons to host channel
```

### Host Starts Round

```
Host: Clicks "Start Round" button
    ↓
StartRoundButton.callback()
    ↓
create_round_allocation() → Shuffle users, assign to teams/judges
    ↓
queue.clear() + update_lobby_display()
    ↓
show_allocation_interface() → Send adjustment embed
```

### Host Adjusts and Confirms

```
Host: Interacts with adjustment controls
    ↓
AllocationAdjustmentView (Swap/Toggle/Move buttons)
    ↓
Modify debate_round object
    ↓
refresh_embed() → Show updated allocation
    ↓
Host: Clicks "Confirm & Start"
    ↓
MotionInputModal → Enter motion
    ↓
create_confirmed_round_embed() → Final announcement
    ↓
Clear current_round
```

## State Management

**Queue State**:
- Stored in: `Matchmaking.queue` (MatchmakingQueue object)
- Persists: In memory only (cleared on bot restart)
- Updated by: `/queue`, `/leave`, round starts

**Current Round State**:
- Stored in: `Matchmaking.current_round` (DebateRound object)
- Persists: Until round is confirmed or cancelled
- Updated by: Adjustment UI interactions

**Lobby Message**:
- Stored in: `queue.lobby_message` (discord.Message reference)
- Persists: Until manually deleted or bot restart
- Updated by: Queue changes

## Error Handling

**Command Errors**:
- Missing permissions → Ephemeral error message
- User errors (already in queue) → Friendly error embed
- System errors → Logged to console, generic user message

**View Timeouts**:
- Adjustment view: 10 minute timeout, disables buttons
- Selection views: 60 second timeout

**Message Not Found**:
- Lobby message deleted → Recreate automatically
- Graceful fallback for all message edits

## Extension Points

**Adding New Commands**:
1. Add method to appropriate Cog
2. Use `@discord.slash_command()` decorator
3. Use `EmbedBuilder` for consistent responses

**Adding New Round Types**:
1. Add to `RoundType` enum in models.py
2. Update `create_round_allocation()` logic
3. Add host control button variant
4. Update embed builders

**Custom Team Positions**:
- Edit `TEAM_POSITIONS` in config.py
- Supports any number of positions per team type

**Persistence**:
- Add SQLite database for queue persistence
- Store round history
- Implement queue position saving across restarts

## Performance Considerations

**Rate Limiting**:
- Discord API: Automatically handled by py-cord
- Edit operations: Batched in `refresh_embed()`

**Memory**:
- Queue size: Limited by user participation (typically < 20)
- Round history: Only current round stored
- Message references: Minimal memory footprint

**Scalability**:
- Single server design (one GUILD_ID)
- Can be extended to multi-server with per-guild state

## Security

**Permission Checks**:
- Admin commands: `@commands.has_permissions(administrator=True)`
- Host controls: Channel-based (only in host channel)

**Input Validation**:
- User IDs: Parsed and validated before use
- Member existence: Checked via `guild.get_member()`

**Data Exposure**:
- Sensitive data: Only in `.env` (not committed)
- User data: Only Discord IDs and mentions

## Testing Recommendations

**Unit Tests**:
- Test data models (DebateTeam, JudgePanel, DebateRound)
- Test queue logic (add, remove, thresholds)
- Test allocation algorithm (proper distribution)

**Integration Tests**:
- Test full queue → allocation → adjustment flow
- Test all button/modal interactions
- Test error handling paths

**Manual Testing**:
- Use multiple accounts or ask server members
- Test all round types (5, 6, 7+ users)
- Test edge cases (empty queue, full teams)

## Future Enhancements

**Potential Features**:
- ELO/MMR rating system
- Match history and statistics
- Motion database integration
- Automatic room creation (voice channels)
- Round timer and speech clock
- Feedback and rating system for rounds
- Queue priorities (e.g., waiting time)
- Multiple concurrent rounds
