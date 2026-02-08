# Quick Reference Card

## Important Links

- **Discord Developer Portal**: https://discord.com/developers/applications
- **Railway Dashboard**: https://railway.app/dashboard
- **Railway Docs**: https://docs.railway.app/

## Discord IDs You Need

Before deploying, collect these IDs (enable Developer Mode in Discord first):

| What | How to Get | Example |
|------|------------|---------|
| **Bot Token** | Discord Dev Portal > Bot > Reset Token | `MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.Gk9x...` |
| **Server ID** | Right-click server icon > Copy Server ID | `123456789012345678` |
| **Lobby Channel ID** | Right-click lobby channel > Copy Channel ID | `234567890123456789` |
| **Host Channel ID** | Right-click host channel > Copy Channel ID | `345678901234567890` |
| **Host Role ID** (optional) | Server Settings > Roles > Right-click role > Copy ID | `456789012345678901` |

## Bot Commands

### For Everyone
- `/queue` - Join the matchmaking queue
- `/leave` - Leave the queue

### For Admins Only
- `/clearqueue` - Clear the entire queue

## Matchmaking Thresholds

| Players | Round Type | Configuration |
|---------|------------|---------------|
| **5** | Double Iron | 2v2 + 1 Judge |
| **6** | Single Iron | 3v2 + 1 Judge (one team is iron) |
| **7+** | Standard | 3v3 + Judges |

## Host Controls

When threshold is reached, hosts can:

1. **Start Round** - Click the button in host channel
2. **Adjust Allocation**:
   - Swap Members - Switch any two people
   - Toggle Team Type - Change between Full (3) and Iron (2)
   - Move to Judge - Convert debater to judge
   - Move to Debater - Convert judge to debater
3. **Confirm & Start** - Enter motion and launch the round

## Railway Free Tier

- **Credits**: $5/month free
- **Uptime**: ~500 hours/month (~21 days continuous)
- **Bandwidth**: 100 GB/month
- **Resources**: Shared CPU, 512MB RAM

**This is enough for most small-to-medium debate servers!**

## Deployment Checklist

- [ ] Created Discord bot application
- [ ] Enabled Server Members Intent
- [ ] Enabled Message Content Intent
- [ ] Copied bot token
- [ ] Invited bot to server with correct permissions
- [ ] Collected all IDs (server, channels, role)
- [ ] Created Railway account
- [ ] Created Railway project from GitHub repo
- [ ] Set all environment variables in Railway
- [ ] Deployed the bot
- [ ] Verified bot is online in Discord
- [ ] Tested `/queue` command

## File Structure

```
debate.gg/
├── main.py              # Bot entry point
├── config.py            # Configuration
├── .env                 # YOUR SETTINGS (fill this out!)
├── START_HERE.md        # Start here!
├── SETUP_GUIDE.md       # Complete setup instructions
├── QUICK_REFERENCE.md   # This file
├── requirements.txt     # Python dependencies
├── railway.json         # Railway configuration
├── cogs/
│   ├── matchmaking.py   # Queue and round logic
│   └── adjustment.py    # Allocation adjustment UI
└── utils/
    ├── models.py        # Data structures
    └── embeds.py        # Discord embeds
```

## Common Issues & Fixes

| Problem | Solution |
|---------|----------|
| Bot offline | Check Railway logs, verify token |
| Commands don't show | Wait 1 hour, or kick/re-invite bot |
| "Configuration Error" | Check all env vars are set correctly |
| Can't see embeds | Give bot "Embed Links" permission |
| Can't start round | Check bot has permission in host channel |

## Environment Variable Template

Copy this to Railway:

```
DISCORD_TOKEN=paste_your_bot_token_here
GUILD_ID=paste_your_server_id_here
LOBBY_CHANNEL_ID=paste_lobby_channel_id_here
HOST_CHANNEL_ID=paste_host_channel_id_here
HOST_ROLE_ID=paste_role_id_here_or_leave_blank
```

## Getting Help

1. Check [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed instructions
2. Check Railway deployment logs for error messages
3. Verify all IDs are correct
4. Make sure bot has proper permissions
5. Check [README.md](README.md) for technical details

## Tips for Success

✅ Enable Developer Mode in Discord first
✅ Copy IDs carefully (no extra spaces)
✅ Don't share your bot token with anyone
✅ Make sure bot has permissions in all relevant channels
✅ Test with `/queue` before gathering users
✅ Monitor Railway usage to stay in free tier

---

**Ready to deploy?** Follow [SETUP_GUIDE.md](SETUP_GUIDE.md) step by step!
