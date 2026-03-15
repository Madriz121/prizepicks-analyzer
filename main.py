import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    # Per_page=250 to catch all the categories in your image
    url = "https://api.prizepicks.com/projections?league_id=7&per_page=250"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ API Error: {e}")
        return None

def build_slips():
    raw_data = get_data()
    if not raw_data: return

    # 1. Map Player IDs to Names
    player_map = {
        item.get('id'): item.get('attributes', {}).get('name') 
        for item in raw_data.get('included', []) 
        if item.get('type') == 'new_player'
    }

    # 2. Extract and Filter by 80% Consistency (4/5 Games)
    high_value_plays = []
    
    # These match the fields in your image (Points, Rebs+Asts, Blks+Stls, etc.)
    for p in raw_data.get('data', []):
        attr = p.get('attributes', {})
        player_id = p.get('relationships', {}).get('new_player', {}).get('data', {}).get('id')
        name = player_map.get(player_id)
        
        stat = attr.get('stat_type')
        line = attr.get('line_score')
        l5_data = attr.get('last_5_stats')

        # DATA VALIDATION
        if not name or line is None or not l5_data or len(l5_data) < 5:
            continue

        # 80% Consistency Check
        overs = sum(1 for val in l5_data if val is not None and val > line)
        unders = sum(1 for val in l5_data if val is not None and val < line)

        pick_type = None
        if overs >= 4: pick_type = "OVER"
        elif unders >= 4: pick_type = "UNDER"

        if pick_type:
            high_value_plays.append({
                "name": name, "stat": stat, "line": line, 
                "pick": pick_type, "l5": l5_data
            })

    # 3. Unique Slip Building (Max 6 man slips)
    slip_count = 1
    remaining = high_value_plays.copy()

    while len(remaining) >= 3:
        current_slip = []
        used_names = set()
        to_remove = []

        for i, play in enumerate(remaining):
            if len(current_slip) < 6 and play['name'] not in used_names:
                current_slip.append(play)
                used_names.add(play['name'])
                to_remove.append(i)

        for index in sorted(to_remove, reverse=True):
            remaining.pop(index)

        if len(current_slip) >= 3:
            send_to_discord(current_slip, len(current_slip), slip_count)
            slip_count += 1
        else:
            break

def send_to_discord(plays, size, slip_num):
    # CRITICAL FIX: Ensure variable is pulled directly from Env
    url = os.environ.get("DISCORD_WEBHOOK")
    
    if not url or url == "":
        print(f"❌ ERROR: Webhook URL is empty! Check GitHub Secrets.")
        return

    webhook = DiscordWebhook(url=url)
    embed = DiscordEmbed(
        title=f"🔥 80% Consistency Slip #{slip_num}",
        description=f"**{size}-Man NBA Flex**",
        color="00ff00"
    )

    for p in plays:
        emoji = "📈" if p['pick'] == "OVER" else "📉"
        l5_history = ", ".join(map(str, p['l5']))
        embed.add_embed_field(
            name=p['name'],
            value=f"{p['stat']}: **{p['line']}**\nPick: **{emoji} {p['pick']}**\nL5: `{l5_history}`",
            inline=True
        )

    webhook.add_embed(embed)
    webhook.execute()
    print(f"✅ Slip #{slip_num} sent to Discord.")

if __name__ == "__main__":
    build_slips()
