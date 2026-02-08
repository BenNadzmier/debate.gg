"""Quick test to check if cogs load properly"""
import sys
sys.path.insert(0, '.')

print("Testing cog imports...")

try:
    print("\n1. Testing config import...")
    from config import Config
    print("[OK] Config imported")

    print("\n2. Testing models import...")
    from utils.models import MatchmakingQueue
    print("[OK] Models imported")

    print("\n3. Testing embeds import...")
    from utils.embeds import EmbedBuilder
    print("[OK] Embeds imported")

    print("\n4. Attempting to import matchmaking cog...")
    import cogs.matchmaking
    print("[OK] Matchmaking cog imported")

    print("\n5. Attempting to import adjustment cog...")
    import cogs.adjustment
    print("[OK] Adjustment cog imported")

    print("\n[SUCCESS] ALL IMPORTS SUCCESSFUL")
    print("\nThe issue is likely with Discord.py command registration, not imports.")

except Exception as e:
    print(f"\n[ERROR] IMPORT ERROR: {e}")
    import traceback
    traceback.print_exc()
