import os
from curl_cffi import requests  # Mimics real browser TLS fingerprints
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    url = "https://api.prizepicks.com/projections?league_id=7" # NBA
    
    try:
        # 'impersonate' tells the library to exactly copy a real Chrome browser
        response = requests.get(url, impersonate="chrome110", timeout=15)
        
        if response.status_code == 403:
            print("Block Detected: PrizePicks is still blocking the GitHub IP.")
            return None
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Fetch Error: {e}")
        return None

def build_multiple_slips():
    raw_data = get_data()
    if not raw_data: return

    player_map = {}
    history_map = {} 

    for item in raw_data.get('included', []):
        if item['type'] == 'new_player':
            player_map[item['id']] = item['attributes']['name']
        if item['type'] == 'projection_line':
            perf = item['attributes'].get('last_5_performance', [])
            history_map[item['id']] = perf

    valid_plays = []
    for p in raw_data.get('data', []):
        attr = p['attributes']
        line = float(attr['line_score'])
        stat = attr['stat_type']
        history = history_map.get(p['id'], [])
        
        if len(history) >= 5:
            hits = sum(1 for score in history if float(score) > line)
            if hits >= 4:
                rel = p.get('relationships', {})
                player_id = rel.get('new_player', {}).get('data', {}).get('id')
                name = player_map.get(player_id, "Unknown Player")
                valid_plays.append({"name": name, "stat": stat, "line": line, "history": f"{hits}/5 L5"})

    print(f"Found {len(valid_plays)} high-probability plays.")
    field_limit = 25 
    for i in range(0, len(valid_plays), field_limit):
        chunk = valid_plays[i : i + field_limit]
        send_to_discord(chunk, (i // field_limit) + 1)

def send_to_discord(plays, part_num):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url: return

    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(
        title=f"🔥 NBA 80% Hit Rate (Part {part_num})",
        description=f"Showing {len(plays)} players who hit 4/5 of their last games.",
        color="00ff00"
    )
    for p in plays:
        embed.add_embed_field(name=f"✅ {p['name']}", value=f"{p['stat']}: **{p['line']}**\nTrend: **{p['history']}**", inline=True)
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    build_multiple_slips()
