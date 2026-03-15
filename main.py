import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    url = "https://api.prizepicks.com/projections?league_id=7" # NBA
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def build_multiple_slips():
    raw_data = get_data()
    if not raw_data: 
        print("No data received.")
        return

    # 1. Map Player IDs and Stats
    player_map = {}
    for item in raw_data.get('included', []):
        if item['type'] == 'new_player':
            player_map[item['id']] = item['attributes']['name']

    # 2. Extract Plays & Filter by 80% Hit Rate (4/5)
    all_plays = []
    for p in raw_data.get('data', []):
        attr = p['attributes']
        relationships = p.get('relationships', {})
        player_id = relationships.get('new_player', {}).get('data', {}).get('id')
        
        # Extract 'Last 5' data from the attributes
        # Note: PrizePicks API usually provides 'last_5_performance' or similar in attributes
        last_5_stats = attr.get('last_5_performance', []) 
        
        # If last_5 data is missing, we skip to be safe
        if not last_5_stats or len(last_5_stats) < 5:
            continue

        line = attr['line_score']
        stat = attr['stat_type']
        
        # Calculate Hit Rate (How many times they went OVER the current line in last 5)
        hits = sum(1 for game_score in last_5_stats if float(game_score) > float(line))
        hit_rate = (hits / 5) * 100

        # FILTER: Only 80% hit rate (4 out of 5)
        if hits >= 4:
            name = player_map.get(player_id, "Unknown Player")
            all_plays.append({
                "name": name, 
                "stat": stat, 
                "line": line, 
                "pick": "OVER", 
                "history": f"{hits}/5 L5"
            })

    print(f"Filtered {len(all_plays)} high-probability plays.")

    # 3. Split into Multiple Slips (Max 10 per slip)
    slip_size = 10
    for i in range(0, len(all_plays), slip_size):
        slip_chunk = all_plays[i : i + slip_size]
        if len(slip_chunk) >= 3: 
            send_to_discord(slip_chunk, len(slip_chunk), (i // slip_size) + 1)

def send_to_discord(plays, size, slip_num):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    
    if not webhook_url:
        print(f"CRITICAL: 'DISCORD_WEBHOOK' is missing. Cannot send Slip #{slip_num}")
        return

    try:
        webhook = DiscordWebhook(url=webhook_url)
        embed = DiscordEmbed(
            title=f"🔥 High-Probability Slip #{slip_num} ({size}-Man)",
            description="All players have an 80%+ hit rate (4/5) on their current line.",
            color="ff4747"
        )

        for p in plays:
            embed.add_embed_field(
                name=f"✅ {p['name']}",
                value=f"{p['stat']}: **{p['line']}**\nL5 Rate: **{p['history']}**",
                inline=True
            )

        webhook.add_embed(embed)
        webhook.execute()
        print(f"Sent Slip #{slip_num} to Discord.")
    except Exception as e:
        print(f"Webhook Error: {e}")

if __name__ == "__main__":
    build_multiple_slips()
