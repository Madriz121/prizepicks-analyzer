import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def run_prizepicks_check():
    # 1. Fetch PrizePicks Data
    url = "https://api.prizepicks.com/projections?league_id=7" # 7 is NBA
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        # For this example, let's just grab the first player's line
        first_play = data['data'][0]['attributes']
        player_name = "Player" # You'd parse the 'included' section for names
        stat_type = first_play['stat_type']
        line_value = first_play['line_score']

        # 2. Send to Discord
        webhook_url = os.getenv("DISCORD_WEBHOOK")
        webhook = DiscordWebhook(url=webhook_url)
        embed = DiscordEmbed(title="🚀 PrizePicks Opportunity", color="03b2f8")
        embed.add_embed_field(name="Prop", value=f"{stat_type}: {line_value}")
        webhook.add_embed(embed)
        webhook.execute()

if __name__ == "__main__":
    run_prizepicks_check()
