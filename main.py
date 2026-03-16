import os
import requests
import time
import random
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_nba_data():
    api_key = os.getenv("THE_ODDS_API_KEY")
    # Step 1: Get the list of Event IDs
    events_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events_resp = requests.get(events_url, params={'apiKey': api_key})
    if events_resp.status_code != 200: return []

    events = events_resp.json()
    all_props = []

    # Quota Note: Fetching 8 games provides a large enough pool for multiple 6-man slips
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

def build_usage_slips(data):
    # This pool will hold all possible correlated pairs
    pair_pool = []
    
    for game in data:
        team_rosters = {}
        # Parse outcomes into rosters
        for book in game.get('bookmakers', []):
            if book['key'] in ['draftkings', 'fanduel']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        player = opt['description']
                        line = float(opt['point'])
                        # Determine team (simplified logic)
                        team = game['home_team'] 
                        if team not in team_rosters: team_rosters[team] = []
                        team_rosters[team].append({'name': player, 'line': line, 'team': team})

        # Create Negative Correlation Pairs (Alpha OVER, Beta UNDER)
        for team, players in team_rosters.items():
            sorted_p = sorted(players, key=lambda x: x['line'], reverse=True)
            if len(sorted_p) >= 2:
                pair_pool.append([
                    {'name': sorted_p[0]['name'], 'line': sorted_p[0]['line'], 'pick': 'MORE', 'team': team},
                    {'name': sorted_p[1]['name'], 'line': sorted_p[1]['line'], 'pick': 'LESS', 'team': team}
                ])

    random.shuffle(pair_pool)
    final_slips = []
    used_global_players = set()

    # Priority Loop: Try to build 10 slips
    for _ in range(10):
        current_entry = []
        current_teams = set()
        
        # We try to fill a 6-man slip first
        for target_size in [6, 5, 4, 3]:
            if current_entry: break # Already found a slip size for this entry
            
            # Reset search for this specific entry
            temp_slip = []
            temp_used_in_slip = set()
            
            # PrizePicks Rule: Slips are built in PAIRS here to maintain correlation
            for pair in pair_pool:
                p1, p2 = pair[0], pair[1]
                # Condition: No player repeat and maintain team diversity
                if p1['name'] not in used_global_players and p2['name'] not in used_global_players:
                    temp_slip.extend([p1, p2])
                    used_global_players.add(p1['name'])
                    used_global_players.add(p2['name'])
                    
                    if len(temp_slip) == target_size:
                        current_entry = temp_slip
                        break
            
            # If we couldn't fill the target size, release those players back to the pool
            if len(temp_slip) < target_size:
                for p in temp_slip:
                    used_global_players.remove(p['name'])
        
        if current_entry:
            final_slips.append(current_entry)

    return final_slips

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)
    
    for i, entry in enumerate(entries):
        size = len(entry)
        # 6-man slips get a special Gold color
        color = "FFD700" if size == 6 else "3498db"
        embed = DiscordEmbed(title=f"📝 Slip #{i+1} ({size}-Man Flex)", color=color)
        
        for p in entry:
            direction = "⬆️" if p['pick'] == "MORE" else "⬇️"
            embed.add_embed_field(name=f"{direction} {p['name']}", value=f"**{p['pick']} {p['line']}**", inline=True)
        
        webhook.add_embed(embed)
        if (i+1) % 5 == 0:
            webhook.execute()
            webhook = DiscordWebhook(url=webhook_url)
    
    if entries: webhook.execute()

if __name__ == "__main__":
    raw_data = get_nba_data()
    entries = build_usage_slips(raw_data)
    alert_discord(entries)
