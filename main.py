import os
import requests  # We can use standard requests now!
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    token = os.getenv("SCRAPE_DO_TOKEN")
    target_url = "https://api.prizepicks.com/projections?league_id=7"
    
    # We send the request TO Scrape.do, and they fetch PrizePicks for us
    # render=true ensures it handles JavaScript/Cloudflare perfectly
    api_url = f"https://api.scrape.do?token={token}&url={target_url}&render=true"

    try:
        print("🚀 Fetching data via Scrape.do bypass...")
        response = requests.get(api_url, timeout=60)
        
        if response.status_code == 401:
            print("❌ API Token invalid. Check SCRAPE_DO_TOKEN.")
            return None
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Bypass Failed: {e}")
        return None

def send_to_discord(plays, part_num):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not webhook_url.startswith("https"):
        print("❌ Invalid Discord Webhook.")
        return

    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title=f"📋 NBA 80% Hit Rate (Part {part_num})", color="00ff00")
    for p in plays:
        embed.add_embed_field(name=f"✅ {p['name']}", value=f"{p['stat']}: **{p['line']}**\nL5: **{p['history']}**", inline=True)
    webhook.add_embed(embed)
    webhook.execute()

def build_multiple_slips():
    raw_data = get_data()
    if not raw_data: return

    player_map = {}
    history_map = {} 

    # Logic to map players and lines
    for item in raw_data.get('included', []):
        if item['type'] == 'new_player':
            player_map[item['id']] = item['attributes']['name']
        if item['type'] == 'projection_line':
            history_map[item['id']] = item['attributes'].get('last_5_performance', [])

    valid_plays = []
    for p in raw_data.get('data', []):
        attr = p['attributes']
        line = float(attr['line_score'])
        history = history_map.get(p['id'], [])
        
        if len(history) >= 5:
            hits = sum(1 for score in history if float(score) > line)
            if hits >= 4:
                player_id = p['relationships']['new_player']['data']['id']
                valid_plays.append({
                    "name": player_map.get(player_id, "Unknown"),
                    "stat": attr['stat_type'],
                    "line": line,
                    "history": f"{hits}/5 L5"
                })

    # Send in chunks of 25
    for i in range(0, len(valid_plays), 25):
        send_to_discord(valid_plays[i:i+25], (i//25)+1)

if __name__ == "__main__":
    build_multiple_slips()
