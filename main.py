import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    url = "https://api.prizepicks.com/projections?league_id=7&per_page=250"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ API Request Failed: {e}")
        return None

def build_unique_slips():
    raw_data = get_data()
    if not raw_data or 'data' not in raw_data:
        print("❌ No data received from PrizePicks.")
        return

    # 1. Improved Name Mapping
    player_map = {}
    for item in raw_data.get('included', []):
        if item.get('type') == 'new_player':
            player_id = item.get('id')
            player_name = item.get('attributes', {}).get('name')
            if player_id and player_name:
                player_map[player_id] = player_name

    # 2. Extract & Consistency Filter
    consistent_plays = []
    for p in raw_data['data']:
        attr = p.get('attributes', {})
        relationships = p.get('relationships', {})
        
        # Pull ID from the correct nested path
        player_id = relationships.get('new_player', {}).get('data', {}).get('id')
        name = player_map.get(player_id)
        
        stat = attr.get('stat_type')
        line = attr.get('line_score')
        
        # Check for Last 5 data
        l5_data = attr.get('last_5_stats')
        
        # VALIDATION: Skip if missing name, line, or if L5 data isn't a full list of 5
        if not name or line is None or not isinstance(l5_data, list) or len(l5_data) < 5:
            continue

        # Calculate Trends (Hit Rate)
        overs = sum(1 for val in l5_data if val is not None and val > line)
        unders = sum(1 for val in l5_data if val is not None and val < line)

        pick_type = None
        if overs >= 4: pick_type = "OVER"
        elif unders >= 4: pick_type = "UNDER"

        if pick_type:
            consistent_plays.append({
                "name": name, "stat": stat, "line": line, 
                "pick": pick_type, "l5": l5_data
            })

    # 3. Slip Generation Logic
    slip_count = 1
    remaining = consistent_plays.copy()

    while len(remaining) >= 3:
        current_slip = []
        used_players = set()
        to_remove_indices = []

        for i, play in enumerate(remaining):
            if len(current_slip) < 6 and play['name'] not in used_players:
                current_slip.append(play)
                used_players.add(play['name'])
                to_remove_indices.append(i)

        for index in sorted(to_remove_indices, reverse=True):
            remaining.pop(index)

        if len(current_slip) >= 3:
            send_to_discord(current_slip, len(current_slip), slip_count)
            slip_count += 1
        else:
            break

def send_to_discord(plays, size, slip_num):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url:
        print("❌ DISCORD_WEBHOOK variable is empty!")
        return

    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(
        title=f"📋 NBA Slip #{slip_num} ({size}-Man Flex)",
        description="🔥 **80%+ Consistency Trend Detected**",
        color="03b2f8"
    )

    for p in plays:
        emoji = "📈" if p['pick'] == "OVER" else "📉"
        l5_display = ", ".join(map(str, p['l5']))
        embed.add_embed_field(
            name=p['name'],
            value=f"{p['stat']}: **{p['line']}**\nPick: **{emoji} {p['pick']}**\nL5: `{l5_display}`",
            inline=True
        )

    webhook.add_embed(embed)
    webhook.execute()
    print(f"✅ Successfully sent Slip #{slip_num}")

if __name__ == "__main__":
    build_unique_slips()
