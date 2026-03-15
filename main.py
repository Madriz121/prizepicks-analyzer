import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    url = "https://api.prizepicks.com/projections?league_id=7" # NBA
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json()
    except:
        return None

def build_multiple_slips():
    raw_data = get_data()
    if not raw_data: return

    # 1. Map Player IDs to Names
    # PrizePicks puts names in the 'included' section
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
        
        # Consistency Logic (Example: Under if Rebounds/Assists, Over if Points)
        pick_type = "OVER" if stat == "Points" else "UNDER"
        
        all_plays.append({"name": name, "stat": stat, "line": line, "pick": pick_type})

    # 3. Split into Multiple Slips (Max 6 per slip)
    slip_size = 6
    if len(all_plays) < 6: slip_size = max(3, len(all_plays)) # Fallback
    
    # Create chunks of the chosen size
    for i in range(0, len(all_plays), slip_size):
        slip_chunk = all_plays[i : i + slip_size]
        if len(slip_chunk) >= 3: # Only send if there's enough for at least a 3-man
            send_to_discord(slip_chunk, len(slip_chunk), (i // slip_size) + 1)

def send_to_discord(plays, size, slip_num):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
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

if __name__ == "__main__":
    build_multiple_slips()
