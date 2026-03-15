import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    url = "https://api.prizepicks.com/projections?league_id=7" # NBA
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Check for HTTP errors
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def build_multiple_slips():
    raw_data = get_data()
    if not raw_data: 
        print("No data received from PrizePicks.")
        return

    # 1. Map Player IDs to Names
    player_map = {}
    for item in raw_data.get('included', []):
        if item['type'] == 'new_player':
            player_map[item['id']] = item['attributes']['name']

    # 2. Extract Valid NBA Plays
    all_plays = []
    for p in raw_data.get('data', []):
        attr = p['attributes']
        relationships = p.get('relationships', {})
        player_id = relationships.get('new_player', {}).get('data', {}).get('id')
        
        name = player_map.get(player_id, "Unknown Player")
        stat = attr['stat_type']
        line = attr['line_score']
        
        # Consistency Logic
        pick_type = "OVER" if stat == "Points" else "UNDER"
        all_plays.append({"name": name, "stat": stat, "line": line, "pick": pick_type})

    # 3. Split into Multiple Slips (Max 6 per slip)
    slip_size = 6
    if len(all_plays) < 6: 
        slip_size = max(3, len(all_plays))
    
    for i in range(0, len(all_plays), slip_size):
        slip_chunk = all_plays[i : i + slip_size]
        if len(slip_chunk) >= 3:
            send_to_discord(slip_chunk, len(slip_chunk), (i // slip_size) + 1)

def send_to_discord(plays, size, slip_num):
    # Fetch the Webhook URL from Environment Variables
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    
    # FIX: Safety check to prevent the 'MissingSchema' error
    if not webhook_url or webhook_url.strip() == "":
        print(f"CRITICAL ERROR: 'DISCORD_WEBHOOK' environment variable is missing or empty.")
        return

    try:
        webhook = DiscordWebhook(url=webhook_url)
        
        embed = DiscordEmbed(
            title=f"📋 Slip #{slip_num}: {size}-Man NBA Flex",
            color="03b2f8"
        )

        for p in plays:
            emoji = "📈" if p['pick'] == "OVER" else "📉"
            embed.add_embed_field(
                name=p['name'],
                value=f"{p['stat']}: **{p['line']}**\nPick: **{emoji} {p['pick']}**",
                inline=True
            )

        webhook.add_embed(embed)
        webhook.execute()
        print(f"Successfully sent Slip #{slip_num} to Discord.")
        
    except Exception as e:
        print(f"Failed to send to Discord: {e}")

if __name__ == "__main__":
    build_multiple_slips()
