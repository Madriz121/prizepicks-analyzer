import os
import requests
import time
import random
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_nba_data():
    api_key = os.getenv("THE_ODDS_API_KEY")
    events_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events_resp = requests.get(events_url, params={'apiKey': api_key})
    
    if events_resp.status_code != 200:
        return []

    events = events_resp.json()
    all_props = []

    # Quota Tip: Fetching 6 games gives us enough for ~2-3 unique slips
    for e in events[:6]:
        eid = e['id']
        props_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'player_points', 'oddsFormat': 'american'}
        resp = requests.get(props_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            data['home_team'] = e['home_team']
            data['away_team'] = e['away_team']
            all_props.append(data)
        time.sleep(0.5)
    
    return all_props

def build_multiple_slips(data):
    pool = []
    used_players = set()
    count = 0

    for event in data:
        for book in event.get('bookmakers', []):
            if book['key'] in ['draftkings', 'fanduel']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        player = opt['description']
                        line = float(opt['point'])
                        if player not in used_players and line >= 20.5:
                            team = event['home_team'] if count % 2 == 0 else event['away_team']
                            pool.append({'name': player, 'line': line, 'team': team})
                            used_players.add(player)
                            count += 1

    # Shuffle the pool to ensure different slips every time the script runs
    random.shuffle(pool)
    
    slips = []
    # Dynamic partitioning logic (Try to build 6-man, then 5, then 4)
    for size in [6, 5, 4]:
        if len(pool) >= size:
            # Check for team diversity in the sub-slice
            current_slice = pool[:size]
            if len(set(p['team'] for p in current_slice)) >= 2:
                slips.append(current_slice)
                pool = pool[size:] # Remove used players from the pool

    return slips

def alert_discord(slips):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not slips:
        print("⚠️ No valid slips generated.")
        return

    webhook = DiscordWebhook(url=webhook_url)
    
    for i, slip in enumerate(slips):
        size = len(slip)
        color = ["00ff00", "7cfc00", "ffd700"][i] if i < 3 else "ffffff"
        
        embed = DiscordEmbed(title=f"📊 NBA Entry #{i+1} ({size}-Man Flex)", color=color)
        for p in slip:
            embed.add_embed_field(name=f"{p['name']} ({p['team']})", value=f"Points: **Over {p['line']}**", inline=True)
        
        embed.set_footer(text="Unique Entry | Market Consensus Strategy")
        webhook.add_embed(embed)

    webhook.execute()
    print(f"🚀 Sent {len(slips)} unique slips to Discord.")

if __name__ == "__main__":
    raw_data = get_nba_data()
    all_slips = build_multiple_slips(raw_data)
    alert_discord(all_slips)
