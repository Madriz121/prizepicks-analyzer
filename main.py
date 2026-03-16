import os
import requests
import time
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_nba_data():
    api_key = os.getenv("THE_ODDS_API_KEY")
    # Step 1: Get NBA Event IDs
    events_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events_resp = requests.get(events_url, params={'apiKey': api_key})
    
    if events_resp.status_code != 200:
        print(f"❌ API Error {events_resp.status_code}: Check your API Key.")
        return []

    events = events_resp.json()
    all_props = []

    # Step 2: Fetch props for the first 8 games to ensure a large pool
    for e in events[:8]:
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

def build_dynamic_slip(data):
    pool = []
    used_players = set()
    # Fixed: initializing 'count' for the team toggle logic
    count = 0 

    for event in data:
        for book in event.get('bookmakers', []):
            if book['key'] in ['draftkings', 'fanduel']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        player = opt['description']
                        line = float(opt['point'])
                        
                        if player not in used_players:
                            # Selection Strategy: High volume players (21.5+ line)
                            if line >= 21.5:
                                team = event['home_team'] if count % 2 == 0 else event['away_team']
                                pool.append({'name': player, 'line': line, 'team': team})
                                used_players.add(player)
                                count += 1

    # Check for team diversity (Must have at least 2 different teams)
    unique_teams = len(set(p['team'] for p in pool))
    if unique_teams < 2:
        print("⚠️ Slip invalid: All players from the same team.")
        return None, 0

    # Dynamic Waterfall: 6 -> 5 -> 4 -> 3
    num_players = len(pool)
    if num_players >= 6: size = 6
    elif num_players == 5: size = 5
    elif num_players == 4: size = 4
    elif num_players == 3: size = 3
    else: return None, 0

    return pool[:size], size

def alert_discord(slip, size):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not slip:
        print("⚠️ Not enough data for a slip.")
        return

    webhook = DiscordWebhook(url=webhook_url)
    # Color coding based on slip size
    colors = {6: "00ff00", 5: "7cfc00", 4: "ffd700", 3: "ffa500"}
    
    embed = DiscordEmbed(
        title=f"🔥 NBA {size}-Man Flex Projection", 
        color=colors.get(size, "ffffff")
    )
    
    for p in slip:
        embed.add_embed_field(
            name=f"✅ {p['name']} ({p['team']})", 
            value=f"Points: **Over {p['line']}**", 
            inline=True
        )
    
    embed.set_footer(text=f"Vegas Market Consensus | Valid {size}-Leg Slip")
    webhook.add_embed(embed)
    webhook.execute()
    print(f"🚀 Successfully sent {size}-man slip to Discord.")

if __name__ == "__main__":
    raw_data = get_nba_data()
    final_slip, final_size = build_dynamic_slip(raw_data)
    alert_discord(final_slip, final_size)
