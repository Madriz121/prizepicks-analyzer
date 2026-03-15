import os
from curl_cffi import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    url = "https://api.prizepicks.com/projections?league_id=7"
    
    # Format: http://username:password@ip:port
    # You will get this URL from a provider like Webshare or Scrape.do
    proxy_url = os.getenv("PROXY_URL") 
    proxies = {"http": proxy_url, "https": proxy_url} if proxy_url else None

    # Realistic Headers to match the 'impersonate' fingerprint
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://app.prizepicks.com/",
        "Origin": "https://app.prizepicks.com"
    }

    try:
        # 'chrome120' mimics the latest TLS fingerprints
        response = requests.get(
            url, 
            headers=headers,
            impersonate="chrome120", 
            proxies=proxies,
            timeout=30
        )
        
        if response.status_code == 403:
            print("403 Forbidden: Cloudflare blocked the GitHub IP. Proxy required.")
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

    # 1. Map Player IDs and Stats from 'included' section
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
            # Count how many times they beat the current line
            hits = sum(1 for score in history if float(score) > line)
            
            # 80% Filter (4/5)
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

    # 3. Dynamic Chunking (No limit, but split into 25-field messages)
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
        description=f"Found {len(plays)} plays with 4/5 historical hit rates.",
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

if __name__ == "__main__":
    build_multiple_slips()
