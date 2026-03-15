import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    url = "https://api.prizepicks.com/projections?league_id=7" # NBA
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json()
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None

def build_unique_slips():
    raw_data = get_data()
    if not raw_data: return

    # 1. Map Player IDs to Names accurately
    player_map = {}
    for item in raw_data.get('included', []):
        if item['type'] == 'new_player':
            player_map[item['id']] = item['attributes']['name']

    # 2. Extract and organize all NBA Plays
    all_plays = []
    for p in raw_data.get('data', []):
        attr = p['attributes']
        player_id = p.get('relationships', {}).get('new_player', {}).get('data', {}).get('id')
        
        name = player_map.get(player_id, "Unknown Player")
        stat = attr['stat_type']
        line = attr['line_score']
        
        # Simple Logic: Points/Threes = Over, Defensive stats = Under
        pick_type = "OVER" if stat in ["Points", "3-PT Made"] else "UNDER"
        
        all_plays.append({"name": name, "stat": stat, "line": line, "pick": pick_type})

    # 3. Build Unique Slips
    # We loop until all plays are exhausted or we can't make a valid slip
    slip_count = 1
    remaining_plays = all_plays.copy()

    while len(remaining_plays) >= 3:
        current_slip = []
        players_in_this_slip = set()
        to_remove = []

        for i, play in enumerate(remaining_plays):
            # Condition: Max 6 per slip AND player name must be unique in this slip
            if len(current_slip) < 6 and play['name'] not in players_in_this_slip:
                current_slip.append(play)
                players_in_this_slip.add(play['name'])
                to_remove.append(i)

        # Remove used plays from the master list so next slip gets new data
        for index in sorted(to_remove, reverse=True):
            remaining_plays.pop(index)

        # Send if it meets the minimum requirement (3-man)
        if len(current_slip) >= 3:
            send_to_discord(current_slip, len(current_slip), slip_count)
            slip_count += 1
        else:
            break # Not enough unique players left to form a slip

def send_to_discord(plays, size, slip_num):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)
    
    embed = DiscordEmbed(
        title=f"📋 NBA Slip #{slip_num} ({size}-Man Flex)",
        description="*Each player is unique to this slip.*",
        color="03b2f8"
    )

    for p in plays:
        emoji = "📈" if p['pick'] == "OVER" else "📉"
        embed.add_embed_field(
            name=p['name'],
            value=f"{p['stat']}: **{p['line']}**\nPick: **{emoji} {p['pick']}**",
            inline=True
        )

    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    build_unique_slips()
