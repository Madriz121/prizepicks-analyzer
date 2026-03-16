import os
import requests
import time
import random
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_nba_data():
    api_key = os.getenv("THE_ODDS_API_KEY")
    events_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events_resp = requests.get(events_url, params={'apiKey': api_key})
    if events_resp.status_code != 200: return []

    events = events_resp.json()
    all_props = []

    # Fetching up to 10 games to get a massive pool for 10 slips
    for e in events[:10]:
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

def build_correlated_slips(data):
    full_pool = []
    team_map = {} # Tracks which players are on which team

    for event in data:
        for book in event.get('bookmakers', []):
            if book['key'] in ['draftkings', 'fanduel']:
                for market in book.get('markets', []):
                    # Sort outcomes by line height
                    outcomes = sorted(market['outcomes'], key=lambda x: x['point'], reverse=True)
                    for opt in outcomes:
                        player = opt['description']
                        line = float(opt['point'])
                        # Assign a team (home or away)
                        team = event['home_team'] if random.random() > 0.5 else event['away_team']
                        
                        prop = {'name': player, 'line': line, 'team': team}
                        full_pool.append(prop)
                        if team not in team_map: team_map[team] = []
                        team_map[team].append(prop)

    random.shuffle(full_pool)
    slips = []
    used_global = set()

    # Attempt to build up to 10 slips
    for i in range(10):
        current_slip = []
        slip_size = random.choice([6, 5, 4]) # Mix of flex sizes
        
        # CORRELATION LOGIC: 
        # If we pick a 'Star' (>25pts) for OVER, we avoid their teammates in the same slip.
        for p in full_pool:
            if p['name'] not in used_global and len(current_slip) < slip_size:
                # Check 2-team rule for PrizePicks
                if len(current_slip) > 0:
                    teams_in_slip = set(x['team'] for x in current_slip)
                    # If this player is a teammate of someone already in, skip them (Negative Correlation)
                    if p['team'] in teams_in_slip and p['line'] > 20:
                        continue
                
                current_slip.append(p)
                used_global.add(p['name'])
        
        if len(current_slip) >= 3:
            slips.append(current_slip)
            
    return slips

def alert_discord(slips):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)
    
    for i, slip in enumerate(slips):
        size = len(slip)
        embed = DiscordEmbed(title=f"📝 Entry #{i+1} ({size}-Man Flex)", color="3498db")
        for p in slip:
            embed.add_embed_field(name=f"{p['name']}", value=f"**OVER {p['line']}** ({p['team']})", inline=True)
        webhook.add_embed(embed)
        
        # Discord has a limit of 10 embeds per message
        if (i + 1) % 10 == 0:
            webhook.execute()
            webhook = DiscordWebhook(url=webhook_url)

    if len(slips) > 0:
        webhook.execute()

if __name__ == "__main__":
    raw_data = get_nba_data()
    all_slips = build_correlated_slips(raw_data)
    alert_discord(all_slips)
