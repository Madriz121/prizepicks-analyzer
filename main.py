import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    # Per_page=250 ensures we grab the full board
    url = "https://api.prizepicks.com/projections?league_id=7&per_page=250" 
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ API Error: {e}")
        return None

def build_unique_slips():
    raw_data = get_data()
    if not raw_data: return

    # 1. Map Player IDs to Names
    player_map = {}
    for item in raw_data.get('included', []):
        if item['type'] == 'new_player':
            player_map[item['id']] = item['attributes']['name']

    # 2. Extract and Filter by 80% Consistency
    all_plays = []
    for p in raw_data.get('data', []):
        attr = p['attributes']
        player_id = p.get('relationships', {}).get('new_player', {}).get('data', {}).get('id')
        name = player_map.get(player_id, "Unknown Player")
        stat = attr['stat_type']
        line = attr['line_score']
        
        # Get Last 5 Stats from PrizePicks
        l5_data = attr.get('last_5_stats')
        if not l5_data or not isinstance(l5_data, list) or len(l5_data) < 5:
            continue # Skip if no consistency data available

        # Calculate hit rates
        overs = sum(1 for val in l5_data if val > line)
        unders = sum(1 for val in l5_data if val < line)

        # 80% Logic (4/5 or 5/5)
        pick_type = None
        if overs >= 4: pick_type = "OVER"
        elif unders >= 4: pick_type = "UNDER"

        if pick_type:
            all_plays.append({
                "name": name, "stat": stat, "line": line, 
                "pick": pick_type, "l5": l5_data
            })

    # 3. Build Unique Slips (Your logic preserved)
    slip_count = 1
    remaining_plays = all_plays.copy()

    while len(remaining_plays) >= 3:
        current_slip = []
        players_in_this_slip = set()
        to_remove = []

        for i, play in enumerate(remaining_plays):
            if len(current_slip) < 6 and play['name'] not in players_in_this_slip:
                current_slip.append(play)
                players_in_this_slip.add(play['name'])
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
    if not webhook_url:
        print("❌ Webhook URL is missing!")
        return

    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(
        title=f"💎 High-Consistency Slip #{slip_num}",
        description=f"**{size}-Man Flex** | Consistency Filter: 80%+",
        color="00ff00"
    )

    for p in plays:
        emoji = "📈" if p['pick'] == "OVER" else "📉"
        l5_str = ", ".join(map(str, p['l5']))
        embed.add_embed_field(
            name=p['name'],
            value=f"{p['stat']}: **{p['line']}**\nPick: **{emoji} {p['pick']}**\nL5: `{l5_str}`",
            inline=True
        )

    webhook.add_embed(embed)
    webhook.execute()
    print(f"✅ Slip #{slip_num} sent.")

if __name__ == "__main__":
    build_unique_slips()
