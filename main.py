import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    url = "https://api.prizepicks.com/projections?league_id=7" # NBA
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
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
            # Check how many times the player beat the current line
            hits = sum(1 for score in history if float(score) > line)
            
            # 80% Rule (4 out of 5 games hit)
            if hits >= 4:
                rel = p.get('relationships', {})
                player_id = rel.get('new_player', {}).get('data', {}).get('id')
                name = player_map.get(player_id, "Unknown Player")
                
                valid_plays.append({
                    "name": name,
                    "stat": stat,
                    "line": line,
                    "history": f"{hits}/5 L5"
                })

    print(f"Found {len(valid_plays)} high-probability plays.")

    # 3. Dynamic Chunking (Discord limits each embed to 25 fields)
    field_limit = 25 
    for i in range(0, len(valid_plays), field_limit):
        chunk = valid_plays[i : i + field_limit]
        send_to_discord(chunk, (i // field_limit) + 1)

def send_to_discord(plays, part_num):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url:
        print("CRITICAL: DISCORD_WEBHOOK is not set.")
        return

    try:
        webhook = DiscordWebhook(url=webhook_url)
        embed = DiscordEmbed(
            title=f"🔥 NBA 80% Hit Rate Plays (Part {part_num})",
            description=f"Showing {len(plays)} players who hit 4/5 of their last games.",
            color="00ff00"
        )

        for p in plays:
            embed.add_embed_field(
                name=f"✅ {p['name']}",
                value=f"{p['stat']}: **{p['line']}**\nTrend: **{p['history']}**",
                inline=True
            )

        webhook.add_embed(embed)
        webhook.execute()
        print(f"Sent Part {part_num} to Discord.")
    except Exception as e:
        print(f"Webhook Error: {e}")

if __name__ == "__main__":
    build_multiple_slips()
