import os
import requests
import time
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_data():
    # PrizePicks NBA League ID is 7. per_page=250 captures all prop categories.
    url = "https://api.prizepicks.com/projections?league_id=7&per_page=250"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ Error fetching PrizePicks: {e}")
        return None

def build_slips():
    raw_data = get_data()
    if not raw_data: return

    # 1. Map IDs to Player Names
    player_map = {
        item['id']: item['attributes']['name'] 
        for item in raw_data.get('included', []) 
        if item['type'] == 'new_player'
    }

    # 2. Filter for 80%+ Consistency (4/5 or 5/5 Hits)
    high_value_plays = []
    for p in raw_data.get('data', []):
        attr = p['attributes']
        player_id = p.get('relationships', {}).get('new_player', {}).get('data', {}).get('id')
        name = player_map.get(player_id)
        
        stat = attr.get('stat_type')
        line = attr.get('line_score')
        l5_data = attr.get('last_5_stats') # Uses internal PrizePicks trend data

        # Validate we have enough data to calculate consistency
        if not name or line is None or not isinstance(l5_data, list) or len(l5_data) < 5:
            continue

        # Logic: Count how many times they cleared the current line
        overs = sum(1 for val in l5_data if val is not None and val > line)
        unders = sum(1 for val in l5_data if val is not None and val < line)

        pick = None
        if overs >= 4: pick = "OVER"
        elif unders >= 4: pick = "UNDER"

        if pick:
            high_value_plays.append({
                "name": name, "stat": stat, "line": line, 
                "pick": pick, "l5": l5_data
            })

    # 3. Create Unique Slips with a 10-Slip Limit
    slip_count = 1
    max_slips = 10
    remaining = high_value_plays.copy()

    while len(remaining) >= 3 and slip_count <= max_slips:
        current_slip = []
        used_players = set()
        indices_to_remove = []

        for i, play in enumerate(remaining):
            # Fill 6-man slips, ensure player name isn't duplicated in the same slip
            if len(current_slip) < 6 and play['name'] not in used_players:
                current_slip.append(play)
                used_players.add(play['name'])
                indices_to_remove.append(i)

        for index in sorted(indices_to_remove, reverse=True):
            remaining.pop(index)

        if len(current_slip) >= 3:
            send_to_discord(current_slip, slip_count)
            slip_count += 1
        else:
            break

def send_to_discord(plays, slip_num):
    # This pulls the 'DISCORD_WEBHOOK' from your GitHub Secrets
    webhook_url = os.environ.get("DISCORD_WEBHOOK")
    
    if not webhook_url:
        print(f"❌ Webhook URL is missing from Environment! Cannot send Slip #{slip_num}")
        return

    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(
        title=f"🏀 NBA Pro Slip #{slip_num}",
        description=f"🔥 **{len(plays)}-Man Flex** | Filter: 80% Consistency",
        color="00ff00"
    )

    for p in plays:
        emoji = "📈" if p['pick'] == "OVER" else "📉"
        l5_history = ", ".join(map(str, p['l5']))
        embed.add_field(
            name=p['name'],
            value=f"{p['stat']}: **{p['line']}**\nSelection: **{emoji} {p['pick']}**\nL5: `{l5_history}`",
            inline=True
        )

    webhook.add_embed(embed)
    try:
        webhook.execute()
        print(f"✅ Slip #{slip_num} posted to Discord.")
    except Exception as e:
        print(f"❌ Failed to post Slip #{slip_num}: {e}")

if __name__ == "__main__":
    build_slips()
