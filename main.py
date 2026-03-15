import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    # Per_page=250 ensures we grab the whole board
    url = "https://api.prizepicks.com/projections?league_id=7&per_page=250"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

def build_slips():
    raw_data = get_data()
    if not raw_data: return

    # 1. Map Player IDs to Names (The 'included' section)
    player_map = {}
    for item in raw_data.get('included', []):
        if item.get('type') == 'new_player':
            player_map[item.get('id')] = item.get('attributes', {}).get('name')

    # 2. Extract and Filter by 80% Consistency (4/5 Games)
    high_value_plays = []
    for p in raw_data.get('data', []):
        attr = p.get('attributes', {})
        player_id = p.get('relationships', {}).get('new_player', {}).get('data', {}).get('id')
        name = player_map.get(player_id)
        
        stat = attr.get('stat_type')
        line = attr.get('line_score')
        l5_data = attr.get('last_5_stats') # This is the PrizePicks L5 data

        # Skip if data is missing or incomplete
        if not name or not l5_data or len(l5_data) < 5:
            continue

        # Consistency Logic: 80% Hit Rate (4 of 5 games)
        overs = sum(1 for val in l5_data if val > line)
        unders = sum(1 for val in l5_data if val < line)

        pick_type = None
        if overs >= 4:
            pick_type = "OVER"
        elif unders >= 4:
            pick_type = "UNDER"

        if pick_type:
            high_value_plays.append({
                "name": name, "stat": stat, "line": line, 
                "pick": pick_type, "l5": l5_data
            })

    # 3. Build Unique Slips (Max 6 players, one per player name)
    slip_count = 1
    remaining_plays = high_value_plays.copy()

    while len(remaining_plays) >= 3:
        current_slip = []
        players_in_slip = set()
        to_remove = []

        for i, play in enumerate(remaining_plays):
            if len(current_slip) < 6 and play['name'] not in players_in_slip:
                current_slip.append(play)
                players_in_slip.add(play['name'])
                to_remove.append(i)

        for index in sorted(to_remove, reverse=True):
            remaining_plays.pop(index)

        if len(current_slip) >= 3:
            send_to_discord(current_slip, len(current_slip), slip_count)
            slip_count += 1
        else:
            break

def send_to_discord(plays, size, slip_num):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url: return

    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(
        title=f"💎 80% Consistency Slip #{slip_num}",
        description=f"**{size}-Man Flex** | Filter: 4/5 Last Games",
        color="00ff00"
    )

    for p in plays:
        emoji = "📈" if p['pick'] == "OVER" else "📉"
        l5_str = ", ".join(map(str, p['l5']))
        embed.add_embed_field(
            name=p['name'],
            value=f"{p['stat']}: **{p['line']}**\nSelection: **{emoji} {p['pick']}**\nL5: `{l5_str}`",
            inline=True
        )

    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    build_slips()
