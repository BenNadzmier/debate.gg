# Railway Deployment Guide (FREE)

This guide shows you how to deploy the bot to Railway for free hosting.

---

## Prerequisites

Before deploying to Railway, you must have:

- ✅ Completed Discord bot setup
- ✅ Collected all IDs (bot token, server ID, channel IDs)
- ✅ GitHub account (for Railway login)

If you haven't done these yet, follow [SETUP_GUIDE.md](SETUP_GUIDE.md) Part 1 first.

---

## Method 1: Deploy via Railway Dashboard (Easiest)

### Step 1: Create Railway Account

1. Go to: **https://railway.app/**

2. Click **"Login"** (top right)

3. Choose **"Login with GitHub"**
   - If you don't have GitHub, create an account at https://github.com first

4. Click **"Authorize Railway"** when prompted

5. You'll see your Railway dashboard

### Step 2: Create a New Project

1. Click the **"New Project"** button

2. Select **"Empty Project"**

3. Give it a name (e.g., "ap-debate-bot")

### Step 3: Add GitHub Repository

**Option A: If you have the code in a GitHub repo**

1. Click **"New"** > **"GitHub Repo"**
2. Select your repository
3. Railway will auto-detect it's a Python app

**Option B: Deploy without GitHub (using CLI)**

We'll use Method 2 below for this

### Step 4: Add Environment Variables

1. In your Railway project, click on the service

2. Click the **"Variables"** tab

3. Click **"New Variable"** for each of these:

   ```
   DISCORD_TOKEN=<paste your bot token>
   GUILD_ID=<paste your server ID>
   LOBBY_CHANNEL_ID=<paste lobby channel ID>
   HOST_CHANNEL_ID=<paste host channel ID>
   HOST_ROLE_ID=<paste role ID or leave empty>
   ```

4. After adding all variables, click **"Deploy"**

### Step 5: Monitor Deployment

1. Click **"Deployments"** tab

2. Watch the build logs - should see:
   ```
   Loading extensions...
   ✓ Loaded cogs.matchmaking
   ✓ Loaded cogs.adjustment
   Logged in as YourBotName
   ```

3. Your bot should now be **online in Discord**!

---

## Method 2: Deploy via Railway CLI (For Local Deployment)

### Step 1: Install Railway CLI

**Windows (PowerShell as Administrator):**
```powershell
iwr https://railway.app/install.ps1 -useb | iex
```

**Mac (Terminal):**
```bash
brew install railway
```

**Linux (Terminal):**
```bash
bash <(curl -fsSL https://railway.app/install.sh)
```

### Step 2: Login to Railway

Close and reopen your terminal, then:

```bash
railway login
```

This opens your browser - click **"Authorize"**

### Step 3: Navigate to Bot Folder

```bash
cd "c:\Users\bnkyl\OneDrive\Desktop\debate.gg"
```

### Step 4: Initialize Project

```bash
railway init
```

- Enter a project name when prompted

### Step 5: Set Environment Variables

```bash
railway variables set DISCORD_TOKEN="your_bot_token_here"
railway variables set GUILD_ID="your_server_id_here"
railway variables set LOBBY_CHANNEL_ID="your_lobby_channel_id_here"
railway variables set HOST_CHANNEL_ID="your_host_channel_id_here"
railway variables set HOST_ROLE_ID="your_role_id_here"
```

### Step 6: Deploy

```bash
railway up
```

This uploads your code to Railway and starts the bot!

### Step 7: View Logs

```bash
railway logs
```

You should see the bot starting up!

---

## Verifying Deployment

### Check Railway Dashboard

1. Go to **https://railway.app/dashboard**
2. Click your project
3. You should see:
   - ✅ **Status**: Running (green)
   - ✅ **Deployments**: Latest deployment successful
   - ✅ **Logs**: Bot login message visible

### Check Discord

1. Open your Discord server
2. The bot should be **online (green status)**
3. Type `/queue` to test
4. Check the lobby channel for the queue embed

---

## Managing Your Deployment

### View Logs

**Dashboard:**
1. Go to your project
2. Click the service
3. Click **"Deployments"**
4. Click the latest deployment
5. View logs in real-time

**CLI:**
```bash
railway logs
```

### Update Environment Variables

**Dashboard:**
1. Service > Variables tab
2. Edit or add variables
3. Bot will automatically redeploy

**CLI:**
```bash
railway variables set VARIABLE_NAME="new_value"
```

### Redeploy

**Dashboard:**
- Click **"Deploy"** button

**CLI:**
```bash
railway up
```

### Stop the Bot

**Dashboard:**
1. Service > Settings
2. Scroll to bottom
3. Click **"Delete Service"**

**CLI:**
```bash
railway down
```

---

## Free Tier Details

### What You Get for Free

- **$5 in credits per month**
- **500 execution hours** (~21 days of 24/7 uptime)
- **100 GB bandwidth**
- **Shared CPU, 512MB RAM**

### Monitoring Usage

1. Go to Railway dashboard
2. Click your project
3. Click **"Usage"** tab
4. See your current month's usage

### What Happens If You Exceed Free Tier?

- Railway will **pause your service** at the end of the month
- Next month, it resumes automatically
- **Optional**: Add a payment method for $5/month to remove limits

---

## Troubleshooting

### Bot Offline in Discord

**Check Logs:**
```bash
railway logs
```

Look for errors. Common issues:
- Invalid bot token
- Missing environment variables
- Python package installation errors

**Fix:**
1. Verify all environment variables are set correctly
2. Check Railway deployment status (should be green)
3. Restart deployment: `railway up` or click Deploy in dashboard

### "Configuration Error" in Logs

**Cause**: Missing or incorrect environment variables

**Fix:**
1. Check all required variables are set:
   - DISCORD_TOKEN
   - GUILD_ID
   - LOBBY_CHANNEL_ID
   - HOST_CHANNEL_ID

2. Verify IDs are correct (no extra spaces or characters)

### Build Fails

**Check logs for the error**

Common fixes:
- Make sure `requirements.txt` exists
- Verify `railway.json` and `nixpacks.toml` are in the root folder
- Try deleting and redeploying

### Bot Doesn't Respond to Commands

- Wait up to 1 hour for slash commands to register globally
- Check bot permissions in Discord channels
- Verify GUILD_ID matches your server

---

## Advanced: Custom Domain (Optional)

Railway allows custom domains:

1. Service > Settings
2. Scroll to **"Networking"**
3. Click **"Generate Domain"**
4. Use this for webhooks or APIs (not needed for Discord bots)

---

## Next Steps

After successful deployment:

1. ✅ Test `/queue` command
2. ✅ Get 5 people to test matchmaking
3. ✅ Verify host controls work
4. ✅ Monitor Railway usage
5. ✅ Share commands with your server!

---

## Quick Commands Reference

```bash
# Login
railway login

# Initialize project
railway init

# Set variable
railway variables set KEY="value"

# Deploy
railway up

# View logs
railway logs

# Check status
railway status

# Open dashboard
railway open
```

---

## Support

- **Railway Docs**: https://docs.railway.app/
- **Railway Discord**: https://discord.gg/railway
- **Railway Status**: https://status.railway.app/

---

**Your bot is now deployed and running 24/7 for free! 🎉**
