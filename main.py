import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    # Adding 'per_page' can sometimes help grab more data at once
    url = "https://api.prizepicks.com/projections?league_id=7&per_page=250" 
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Error: {e}")
        return None

def build_consistent_slips():
    raw_data = get_data()
    if not raw_data: return

    # 1. Map Player IDs to Names
    player_map = {}
    for item in raw_data.get('included', []):
        if item['type'] == 'new_player':
            player_map[item['id']] = item['attributes']['name']

    # 2. Extract and Filter by Consistency
    high_value_plays = []
    for p in raw_data.get('data', []):
        attr = p['attributes']
        player_id = p.get('relationships', {}).get('new_player', {}).get('data', {}).get('id')
        name = player_map.get(player_id, "Unknown Player")
        
        stat = attr['stat_type']
        line = attr['line_score']
        
        # PRIZEPICKS DATA TRICK: Check for 'last_5_stats' in the attributes
        # If not available, we skip to ensure only 'high confidence' picks make it.
        l5_data = attr.get('last_5_stats', []) 
        if not l5_data: continue 

        # Calculate how many times they went over the current line
        overs = sum(1 for game_val in l5_data if game_val > line)
        unders = sum(1 for game_val in l5_data if game_val < line)

        # CONDITION: Only take players with an 80% hit rate (4/5 or 5/5)
        pick_type = None
        if overs >= 4: pick_type = "OVER"
        elif unders >= 4: pick_type = "UNDER"

        if pick_type:
            high_value_plays.append({
                "name": name, "stat": stat, "line": line, 
                "pick": pick_type, "l5": l5_data
            })

    # 3. Build Unique Slips (Same logic as before)
    slip_count = 1
    while len(high_value_plays) >= 3:
        current_slip = []
        players_in_slip = set()
        to_remove = []

        for i, play in enumerate(high_value_plays):
            if len(current_slip) < 6 and play['name'] not in players_in_slip:
                current_slip.append(play)
                players_in_slip.add(play['name'])
                to_remove.append(i)

        for index in sorted(to_remove, reverse=True):
            high_value_plays.pop(index)

        if len(current_slip) >= 3:
            send_to_discord(current_slip, len(current_slip), slip_count)
            slip_count += 1
        else:
            break

def send_to_discord(plays, size, slip_num):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)
    
    embed = DiscordEmbed(
        title=f"💎 High-Consistency Slip #{slip_num}",
        description=f"**{size}-Man Flex** | Filter: 80%+ L5 Hit Rate",
        color="00ff00"
    )

    for p in plays:
        emoji = "📈" if p['pick'] == "OVER" else "📉"
        # Visualizing the last 5 games in the message
        l5_str = ", ".join(map(str, p['l5']))
        embed.add_embed_field(
            name=p['name'],
            value=f"{p['stat']}: **{p['line']}**\nPick: **{emoji} {p['pick']}**\nL5: `{l5_str}`",
            inline=True
        )

    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    build_consistent_slips()
