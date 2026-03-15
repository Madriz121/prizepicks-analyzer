import os
import cloudscraper  # Replaces 'requests'
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    url = "https://api.prizepicks.com/projections?league_id=7" # NBA
    
    # Realistic browser headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json; charset=UTF-8",
        "Referer": "https://app.prizepicks.com/",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        # Create a scraper instance to handle Cloudflare
        scraper = cloudscraper.create_scraper()
        response = scraper.get(url, headers=headers, timeout=15)
        
        if response.status_code == 403:
            print("Error 403: PrizePicks blocked the connection. Try running locally or using a proxy.")
            return None
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Fetch Error: {e}")
        return None

def build_multiple_slips():
    raw_data = get_data()
    if not raw_data: 
        print("No data could be retrieved.")
        return

    player_map = {}
    history_map = {} 

    # 1. Map Player IDs and Stats
    for item in raw_data.get('included', []):
        if item['type'] == 'new_player':
            player_map[item['id']] = item['attributes']['name']
        
        if item['type'] == 'projection_line':
            perf = item['attributes'].get('last_5_performance', [])
            history_map[item['id']] = perf

    # 2. Extract Plays & Filter by 80% Hit Rate (4/5)
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
                
                valid_plays.append({
                    "name": name, 
                    "stat": stat, 
                    "line": line, 
                    "history": f"{hits}/5 L5"
                })

    # 3. Dynamic Chunking (Discord 25-field limit)
    field_limit = 25 
    for i in range(0, len(valid_plays), field_limit):
        chunk = valid_plays[i : i + field_limit]
        send_to_discord(chunk, (i // field_limit) + 1)

def send_to_discord(plays, part_num):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url:
        print("CRITICAL: DISCORD_WEBHOOK secret not found.")
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
