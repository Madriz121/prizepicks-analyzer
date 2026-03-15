import os
import time
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    token = os.getenv("SCRAPE_DO_TOKEN")
    target_url = "https://api.prizepicks.com/projections?league_id=7"
    
    # Logic: super=true (Residential IP) + render=true (Solves Cloudflare)
    # These parameters ensure the highest success rate against PrizePicks security.
    api_url = f"https://api.scrape.do?token={token}&url={target_url}&render=true&super=true"

    # Retry loop to handle 502 Bad Gateway and other temporary hiccups
    for attempt in range(3):
        try:
            print(f"🚀 Fetching PrizePicks data (Attempt {attempt + 1})...")
            response = requests.get(api_url, timeout=60)
            
            # 1. Handle Bad Gateways (Proxy connection failure)
            if response.status_code == 502:
                print("⚠️ 502 Bad Gateway: Connection timed out. Retrying in 15s...")
                time.sleep(15)
                continue
            
            # 2. Handle 403 Forbidden (Blocked IP)
            if response.status_code == 403:
                print("❌ 403 Forbidden: Cloudflare blocked this IP. Trying again in 15s...")
                time.sleep(15)
                continue

            # 3. SAFETY CHECK: Verify JSON Content-Type
            # This prevents 'JSONDecodeError' when receiving an HTML block page.
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                print(f"❌ Error: Expected JSON but received {content_type}.")
                print(f"Raw Snippet (to debug): {response.text[:200]}")
                return None
                
            response.raise_for_status()
            print("✅ Data successfully retrieved!")
            return response.json()
            
        except Exception as e:
            print(f"❌ Attempt {attempt + 1} failed: {e}")
            time.sleep(15)
            
    print("🛑 All attempts failed. Check Scrape.do credits or PrizePicks API status.")
    return None

def build_multiple_slips():
    raw_data = get_data()
    if not raw_data: 
        print("Stopping script: No valid data to process.")
        return

    player_map = {}
    history_map = {} 

    # 1. Map Player Names and Stats
    # Included section contains player metadata
    for item in raw_data.get('included', []):
        if item['type'] == 'new_player':
            player_map[item['id']] = item['attributes']['name']
        if item['type'] == 'projection_line':
            history_map[item['id']] = item['attributes'].get('last_5_performance', [])

    # 2. Extract NBA Plays with 80% (4/5) Filter
    valid_plays = []
    for p in raw_data.get('data', []):
        attr = p['attributes']
        line = float(attr['line_score'])
        stat = attr['stat_type']
        history = history_map.get(p['id'], [])
        
        if len(history) >= 5:
            # Check how many times they went OVER the line in the last 5 games
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

    if not valid_plays:
        print("No 80%+ hit rate plays found right now.")
        return

    print(f"✅ Found {len(valid_plays)} valid plays. Sending to Discord...")

    # 3. Send to Discord in chunks (Discord limit is 25 fields per embed)
    for i in range(0, len(valid_plays), 25):
        send_to_discord(valid_plays[i : i + 25], (i // 25) + 1)

def send_to_discord(plays, part_num):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not webhook_url.startswith("https"):
        print("❌ Error: DISCORD_WEBHOOK is missing or invalid.")
        return

    try:
        webhook = DiscordWebhook(url=webhook_url)
        embed = DiscordEmbed(
            title=f"📋 NBA 80% Hit Rate (Part {part_num})", 
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
        print(f"🚀 Success: Part {part_num} sent to Discord.")
    except Exception as e:
        print(f"❌ Webhook failed: {e}")

if __name__ == "__main__":
    build_multiple_slips()
