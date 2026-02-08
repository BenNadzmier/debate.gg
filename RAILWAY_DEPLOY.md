# Railway Deployment Guide (FREE)

This guide shows you how to deploy the bot to Railway for free hosting.

---

## Prerequisites

Before deploying to Railway, you must have:

- ✅ Completed Discord bot setup
- ✅ Collected all IDs (bot token, server ID, channel IDs)
- ✅ GitHub account (for Railway login)
- ✅ Code pushed to a GitHub repository

If you haven't done these yet, follow [SETUP_GUIDE.md](SETUP_GUIDE.md) Part 1 first.

---

## Deployment Steps

### Step 1: Push Code to GitHub

1. **Create a new repository** on GitHub (if you haven't already):
   - Go to https://github.com/new
   - Name it (e.g., "ap-debate-bot")
   - Make it Public or Private (your choice)
   - Don't add README, .gitignore, or license (already included)
   - Click "Create repository"

2. **Add GitHub as remote** (if not already done):
   ```bash
   git remote add origin https://github.com/YOUR_USERNAME/ap-debate-bot.git
   ```

3. **Push your code**:
   ```bash
   git push -u origin main
   ```

### Step 2: Create Railway Account

1. Go to: **https://railway.app/**

2. Click **"Login"** (top right)

3. Choose **"Login with GitHub"**

4. Click **"Authorize Railway"** when prompted

5. You'll see your Railway dashboard

### Step 3: Deploy from GitHub

1. Click the **"New Project"** button

2. Select **"Deploy from GitHub repo"**

3. **If prompted, click "Configure GitHub App"**:
   - Select your GitHub account
   - Choose "Only select repositories" and select your debate bot repo
   - Click "Install & Authorize"

4. **Select your repository** from the list

5. Railway will automatically:
   - Detect it's a Python project
   - Read `railway.json` and `nixpacks.toml`
   - Start building the bot

### Step 4: Add Environment Variables

1. In your Railway project, click on the service (the deployment card)

2. Click the **"Variables"** tab

3. Click **"New Variable"** for each of these:

   ```
   DISCORD_TOKEN=<your bot token from Discord>
   GUILD_ID=<your server ID>
   LOBBY_CHANNEL_ID=<your lobby channel ID>
   HOST_CHANNEL_ID=<your host channel ID>
   HOST_ROLE_ID=<your role ID or leave empty>
   ```

4. After adding all variables, Railway will automatically redeploy

### Step 5: Monitor Deployment

1. Click **"Deployments"** tab

2. Click on the latest deployment

3. Watch the build logs - should see:
   ```
   Loading extensions...
   ✓ Loaded cogs.matchmaking
   ✓ Loaded cogs.adjustment
   Logged in as YourBotName
   ```

4. Your bot should now be **online in Discord**!

---

## Managing Your Deployment

### View Logs

**Dashboard:**
1. Go to your project
2. Click the service
3. Click **"Deployments"**
4. Click the latest deployment
5. View logs in real-time

### Update Environment Variables

**Dashboard:**
1. Service > Variables tab
2. Edit or add variables
3. Bot will automatically redeploy

### Redeploy

Railway automatically redeploys when you push to GitHub.

**Manual redeploy:**
1. Service > Deployments tab
2. Click the three dots on a deployment
3. Click "Redeploy"

### Stop the Bot

**Dashboard:**
1. Service > Settings
2. Scroll to bottom
3. Click **"Remove Service"** (you can redeploy later)

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
1. Railway dashboard > Service > Deployments
2. Click latest deployment
3. Look for errors

Common issues:
- Invalid bot token
- Missing environment variables
- Python package installation errors

**Fix:**
1. Verify all environment variables are set correctly
2. Check Railway deployment status (should be green)
3. Redeploy if needed

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
- Make sure `requirements.txt` exists in repo
- Verify `railway.json` and `nixpacks.toml` are in the root folder
- Check Python version in `runtime.txt` is supported

### Bot Doesn't Respond to Commands

- Wait up to 1 hour for slash commands to register globally
- Check bot permissions in Discord channels
- Verify GUILD_ID matches your server

---

## Updating Your Bot

When you want to update the bot code:

1. **Make changes** to your local code

2. **Commit changes**:
   ```bash
   git add .
   git commit -m "Description of changes"
   ```

3. **Push to GitHub**:
   ```bash
   git push
   ```

4. **Railway automatically redeploys** with your changes!

---

## Next Steps

After successful deployment:

1. ✅ Test `/queue` command
2. ✅ Get 5 people to test matchmaking
3. ✅ Verify host controls work
4. ✅ Monitor Railway usage
5. ✅ Share commands with your server!

---

**Your bot is now deployed and running 24/7 for free! 🎉**
