import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    # League ID 7 = NBA. per_page=250 to catch all prop types from your image
    url = "https://api.prizepicks.com/projections?league_id=7&per_page=250"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching PrizePicks: {e}")
        return None

def build_consistent_slips():
    raw_data = get_data()
    if not raw_data: return

    # 1. Map Player IDs to Names
    player_map = {
        item['id']: item['attributes']['name'] 
        for item in raw_data.get('included', []) 
        if item['type'] == 'new_player'
    }

    # 2. Filter for 80% Consistency (4/5 Games)
    high_confidence_plays = []
    for p in raw_data.get('data', []):
        attr = p['attributes']
        player_id = p.get('relationships', {}).get('new_player', {}).get('data', {}).get('id')
        name = player_map.get(player_id)
        
        stat = attr.get('stat_type')
        line = attr.get('line_score')
        l5_stats = attr.get('last_5_stats')

        # Skip if missing name, line, or valid L5 data
        if not name or line is None or not isinstance(l5_stats, list) or len(l5_stats) < 5:
            continue

        # Count hit rates (4/5 is 80%)
        overs = sum(1 for val in l5_stats if val is not None and val > line)
        unders = sum(1 for val in l5_stats if val is not None and val < line)

        pick = None
        if overs >= 4: pick = "OVER"
        elif unders >= 4: pick = "UNDER"

        if pick:
            high_confidence_plays.append({
                "name": name, "stat": stat, "line": line, 
                "pick": pick, "l5": l5_stats
            })

    # 3. Build Unique Slips (Limited to 10 Slips)
    slip_count = 1
    max_slips = 10  # Added the 10-slip limit here
    remaining = high_confidence_plays.copy()

    # Continue as long as we have players AND haven't reached the 10-slip limit
    while len(remaining) >= 3 and slip_count <= max_slips:
        current_slip = []
        players_in_slip = set()
        to_remove = []

        for i, play in enumerate(remaining):
            # One player per slip, max 6 per slip
            if len(current_slip) < 6 and play['name'] not in players_in_slip:
                current_slip.append(play)
                players_in_slip.add(play['name'])
                to_remove.append(i)

        # Remove used players so they don't repeat in the next slip
        for index in sorted(to_remove, reverse=True):
            remaining.pop(index)

        # Only send if we found at least 3 unique high-consistency players
        if len(current_slip) >= 3:
            send_to_discord(current_slip, len(current_slip), slip_count)
            slip_count += 1
        else:
            break

    print(f"🏁 Finished processing. Total slips generated: {slip_count - 1}")

def send_to_discord(plays, size, slip_num):
    # This pulls from your GitHub Actions Secrets
    webhook_url = os.environ.get("DISCORD_WEBHOOK")
    
    if not webhook_url:
        print(f"❌ Slip #{slip_num} failed: DISCORD_WEBHOOK is empty.")
        return

    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(
        title=f"🏀 NBA Consistency Slip #{slip_num}",
        description=f"**{size}-Man Flex** | Filter: 80%+ Hit Rate",
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
    print(f"✅ Slip #{slip_num} successfully posted.")

if __name__ == "__main__":
    build_consistent_slips()
