import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def run_prizepicks_check():
    # 1. Get the Webhook from GitHub Secrets
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    
    if not webhook_url:
        print("❌ ERROR: DISCORD_WEBHOOK secret is missing or empty!")
        return

    # 2. Fetch PrizePicks Data
    url = "https://api.prizepicks.com/projections?league_id=7" # 7 = NBA
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Simple logic to grab the first available prop
        projection = data['data'][0]['attributes']
        stat = projection['stat_type']
        line = projection['line_score']
        
        msg_title = "✅ PrizePicks Connection Successful"
        msg_body = f"Found Live Prop: **{stat} at {line}**"
        color = "00FF00" # Green

    except Exception as e:
        msg_title = "⚠️ PrizePicks API Script Status"
        msg_body = f"Connected to Discord, but couldn't parse PrizePicks: {str(e)}"
        color = "FFA500" # Orange

    # 3. Execute Webhook
    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title=msg_title, description=msg_body, color=color)
    webhook.add_embed(embed)
    webhook.execute()
    print("🚀 Script finished and attempt sent to Discord.")

if __name__ == "__main__":
    run_prizepicks_check()
