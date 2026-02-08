# Complete Setup Guide for AP Debate Bot

This guide will walk you through **every single step** to get your debate bot running for FREE on Railway. No prior experience needed!

---

## Part 1: Discord Bot Setup (Browser)

### Step 1: Create a Discord Bot Application

1. **Open your web browser** and go to: https://discord.com/developers/applications

2. **Log in** with your Discord account if you're not already logged in

3. **Click the blue "New Application" button** (top right corner)

4. **Enter a name** for your bot (e.g., "AP Debate Matchmaking Bot")

5. **Check the agreement box** and click "Create"

### Step 2: Configure the Bot

1. **You should now see your application dashboard.** On the left sidebar, click **"Bot"**

2. **Click "Add Bot"** button, then click **"Yes, do it!"** to confirm

3. **Scroll down to "Privileged Gateway Intents"** section

4. **Enable these two intents** by toggling them ON (blue):
   - ✅ **SERVER MEMBERS INTENT**
   - ✅ **MESSAGE CONTENT INTENT**

5. **Click "Save Changes"** at the bottom

6. **Scroll back up to the "TOKEN" section**

7. **Click "Reset Token"** button, then **"Yes, do it!"** to confirm

8. **Copy the token** that appears (it's a long string of letters and numbers)
   - ⚠️ **IMPORTANT**: Save this somewhere safe! You'll need it later. Don't share it with anyone!
   - ⚠️ If you lose it, you'll have to reset it again

### Step 3: Invite the Bot to Your Server

1. **On the left sidebar, click "OAuth2"**, then click **"URL Generator"**

2. **In the "SCOPES" section**, check these boxes:
   - ✅ **bot**
   - ✅ **applications.commands**

3. **In the "BOT PERMISSIONS" section**, check these boxes:
   - ✅ **Read Messages/View Channels**
   - ✅ **Send Messages**
   - ✅ **Embed Links**
   - ✅ **Attach Files**
   - ✅ **Read Message History**
   - ✅ **Use Slash Commands**
   - ✅ **Mention Everyone** (optional, for host pings)

4. **Scroll down** and you'll see a **"GENERATED URL"** at the bottom

5. **Click "Copy"** to copy the URL

6. **Open a new browser tab** and **paste the URL** in the address bar, press Enter

7. **Select your server** from the dropdown

8. **Click "Continue"**, then **"Authorize"**

9. **Complete the CAPTCHA** if prompted

10. **Your bot should now appear in your server** (offline/gray)

### Step 4: Get Your Server and Channel IDs

1. **Open Discord** (app or browser at https://discord.com/app)

2. **Enable Developer Mode**:
   - Click the ⚙️ **User Settings** (bottom left, next to your username)
   - Go to **Advanced** (in the left sidebar under "App Settings")
   - Toggle **Developer Mode** to ON (blue)
   - Close settings

3. **Get your Server ID**:
   - **Right-click your server icon** (left sidebar)
   - Click **"Copy Server ID"**
   - Paste it somewhere safe (Notepad, Notes app, etc.)

4. **Get your Lobby Channel ID**:
   - Go to the channel where you want the queue lobby to appear
   - **Right-click the channel name**
   - Click **"Copy Channel ID"**
   - Paste it somewhere safe with a label like "Lobby Channel ID"

5. **Get your Host Channel ID**:
   - Go to the channel where hosts/admins should receive notifications
   - **Right-click the channel name**
   - Click **"Copy Channel ID"**
   - Paste it somewhere safe with a label like "Host Channel ID"

6. **(Optional) Get your Host Role ID**:
   - Go to **Server Settings** > **Roles**
   - **Right-click the role** you want to ping for host notifications
   - Click **"Copy Role ID"**
   - Paste it somewhere safe with a label like "Host Role ID"

✅ **You've completed the Discord setup!** Now let's deploy the bot.

---

## Part 2: Deploy to Railway (FREE Hosting)

### Step 1: Create a Railway Account

1. **Go to**: https://railway.app/

2. **Click "Login"** (top right)

3. **Sign in with GitHub** (recommended) or use your email
   - If you don't have a GitHub account, click "Sign up" at https://github.com/ first
   - Then come back and sign in with GitHub

4. **Authorize Railway** when prompted

### Step 2: Create a New Project

1. **Click "New Project"** on your Railway dashboard

2. **Select "Deploy from GitHub repo"**

3. **If prompted, click "Configure GitHub App"**:
   - Select your GitHub account
   - Choose "All repositories" or select the specific repo
   - Click "Install & Authorize"

4. **If you haven't pushed the code to GitHub yet**, choose **"Empty Project"** instead

### Step 3: Set Up the Project

**Option A: If you have the code in a GitHub repo:**

1. Select your repository from the list
2. Click "Deploy Now"
3. Railway will automatically detect it's a Python app

**Option B: If you don't have a GitHub repo (we'll use local deployment):**

1. **First, install Railway CLI**:
   - Go to: https://docs.railway.app/develop/cli
   - Follow the installation instructions for your operating system:
     - **Windows**: Run this in PowerShell (as Administrator):
       ```powershell
       iwr https://railway.app/install.ps1 -useb | iex
       ```
     - **Mac**: Run this in Terminal:
       ```bash
       brew install railway
       ```
     - **Linux**: Run this in Terminal:
       ```bash
       bash <(curl -fsSL https://railway.app/install.sh)
       ```

2. **After installation, close and reopen your terminal/command prompt**

3. **Navigate to the bot folder**:
   ```bash
   cd "c:\Users\bnkyl\OneDrive\Desktop\debate.gg"
   ```

4. **Login to Railway**:
   ```bash
   railway login
   ```
   - This will open a browser window
   - Click "Authorize" to allow CLI access

5. **Initialize the project**:
   ```bash
   railway init
   ```
   - Enter a project name (e.g., "ap-debate-bot")

6. **Deploy the code**:
   ```bash
   railway up
   ```

### Step 4: Configure Environment Variables

1. **In Railway dashboard**, click on your project

2. **Click on the service** (your bot)

3. **Click the "Variables" tab**

4. **Click "Add Variable"** and add each of these:

   | Variable Name | Value | Where to get it |
   |---------------|-------|-----------------|
   | `DISCORD_TOKEN` | Your bot token | From Step 2.8 of Discord setup |
   | `GUILD_ID` | Your server ID | From Step 4.3 of Discord setup |
   | `LOBBY_CHANNEL_ID` | Your lobby channel ID | From Step 4.4 of Discord setup |
   | `HOST_CHANNEL_ID` | Your host channel ID | From Step 4.5 of Discord setup |
   | `HOST_ROLE_ID` | Your host role ID (optional) | From Step 4.6 of Discord setup |

5. **After adding all variables, click "Deploy"**

### Step 5: Verify Deployment

1. **Click the "Deployments" tab** in Railway

2. **Watch the deployment logs** - you should see:
   ```
   Loading extensions...
   ✓ Loaded cogs.matchmaking
   ✓ Loaded cogs.adjustment
   Matchmaking cog loaded
   Adjustment cog loaded
   Logged in as YourBotName
   ```

3. **If you see errors**, check:
   - All environment variables are set correctly
   - No extra spaces in the values
   - The bot token is valid

4. **In Discord, your bot should now be online (green)!**

---

## Part 3: Test the Bot

### Step 1: Test Basic Commands

1. **In your Discord server, go to any channel**

2. **Type `/queue`** and press Enter
   - The bot should respond confirming you joined the queue
   - In your lobby channel, you should see an embed showing you in the queue

3. **Type `/leave`** and press Enter
   - The bot should confirm you left the queue

### Step 2: Test Matchmaking

1. **Get 5 people** to type `/queue` (or use multiple accounts)

2. **When 5 people are in queue**, check your **host channel**
   - You should see a notification with a button to start the round

3. **Click the "Start Double Iron Round" button**

4. **You'll see an allocation embed** with:
   - Government team (2 debaters)
   - Opposition team (2 debaters)
   - Judge

5. **Test the adjustment buttons**:
   - Click "Swap Members" to try swapping positions
   - Click "Toggle Team Type" to switch team sizes
   - Click "Move to Judge" or "Move to Debater"

6. **Click "✅ Confirm & Start Round"**

7. **Enter a motion** (e.g., "This house supports universal basic income")

8. **The final round announcement should appear!**

✅ **Your bot is fully operational!**

---

## Part 4: Railway Free Tier Information

### What's Included in Free Tier

- **$5 credit per month** (enough for a small bot)
- **500 hours of execution time per month** (~21 days of continuous uptime)
- **100 GB bandwidth**
- **Shared CPU and 512MB RAM**

### Tips to Stay Within Free Tier

1. **Your bot will stay online 24/7** within the free tier limits
2. **If you run out of credits**, the bot will pause until next month
3. **Monitor usage** in Railway dashboard under "Usage"
4. **You can add a credit card** for $5/month if you exceed free tier (but it's optional)

### Making the Bot Sleep (Optional)

If you want to conserve Railway credits:

1. **In Railway dashboard**, click on your service
2. **Click the "Settings" tab**
3. **Scroll to "Environment"**
4. **Click "Delete Service"** to stop it temporarily
5. **Redeploy when needed** by clicking "Deploy"

---

## Troubleshooting

### Bot is offline in Discord

- Check Railway deployment logs for errors
- Verify all environment variables are set correctly
- Make sure you enabled both privileged intents

### Slash commands don't appear

- Wait up to 1 hour for Discord to register commands globally
- Try kicking and re-inviting the bot
- Make sure you invited with `applications.commands` scope

### "Configuration Error" in Railway logs

- Double-check all environment variable names (case-sensitive)
- Make sure IDs are just numbers (no < > or extra characters)
- Verify DISCORD_TOKEN has no extra spaces

### Bot responds but features don't work

- Check that channel IDs match the actual channels you want to use
- Verify bot has permissions in those channels
- Make sure bot role is above other roles (Server Settings > Roles)

---

## Need Help?

1. **Check Railway logs** for error messages
2. **Verify all IDs** are correct in environment variables
3. **Make sure bot has permissions** in the channels
4. **Try redeploying** in Railway

---

## Summary

You've successfully:
- ✅ Created a Discord bot
- ✅ Configured permissions and intents
- ✅ Invited the bot to your server
- ✅ Deployed to Railway for FREE
- ✅ Set up environment variables
- ✅ Tested the matchmaking system

**Your AP Debate Matchmaking Bot is now live and running 24/7 for free!**

Anyone in your server can now use `/queue` to join debates, and hosts can manage rounds from the host channel.
