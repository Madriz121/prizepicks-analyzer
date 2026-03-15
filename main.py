import os
from curl_cffi import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    url = "https://api.prizepicks.com/projections?league_id=7"
    proxy_url = os.getenv("PROXY_URL") 
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    # Step 1: Optional Proxy Test (Helps Debugging)
    if proxies:
        try:
            requests.get("https://httpbin.org/ip", proxies=proxies, timeout=10)
            print("✅ Proxy connection verified.")
        except Exception as e:
            print(f"⚠️ Proxy Test Failed (Check credentials): {e}")

    try:
        # Step 2: Fetch PrizePicks Data
        response = requests.get(
            url, 
            impersonate="chrome120", 
            proxies=proxies,
            timeout=30
        )
        
        if response.status_code == 403:
            print("❌ 403 Forbidden: PrizePicks blocked this IP/Proxy.")
            return None
        elif response.status_code == 407:
            print("❌ 407 Proxy Auth Error: Check your Webshare username/password.")
            return None
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Fetch Error: {e}")
        return None

def build_multiple_slips():
    raw_data = get_data()
    if not raw_data: 
        print("No data retrieved. Exiting.")
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

    # 2. Extract NBA Plays with 80% (4/5) Filter
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

    if not valid_plays:
        print("Found 0 plays matching the 80% criteria.")
        return

    print(f"Found {len(valid_plays)} plays. Sending to Discord...")

    # 3. Dynamic Chunking (Discord 25-field limit)
    field_limit = 25 
    for i in range(0, len(valid_plays), field_limit):
        chunk = valid_plays[i : i + field_limit]
        send_to_discord(chunk, (i // field_limit) + 1)

def send_to_discord(plays, part_num):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    
    # NEW FIX: Logic check to prevent 'MissingSchema' error
    if not webhook_url or not webhook_url.startswith("https"):
        print(f"❌ ERROR: Invalid DISCORD_WEBHOOK URL. Current value: {webhook_url}")
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
        print(f"❌ Webhook execute failed: {e}")

if __name__ == "__main__":
    build_multiple_slips()
