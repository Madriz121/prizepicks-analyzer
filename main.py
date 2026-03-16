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
    # Fetch 15 games to ensure we have enough unique players for 10 slips
    for e in events[:15]:
        eid = e['id']
        props_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'player_points', 'oddsFormat': 'american'}
        resp = requests.get(props_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            # Canonical game teams
            data['home_team'] = e['home_team']
            data['away_team'] = e['away_team']
            all_props.append(data)
        time.sleep(0.4)
    return all_props

def build_waterfall_slips(data):
    # 1. Create a clean map of Team -> List of Unique Players
    team_map = {}
    for game in data:
        home, away = game['home_team'], game['away_team']
        for team in [home, away]:
            if team not in team_map: team_map[team] = {}
        
        for book in game.get('bookmakers', []):
            for market in book.get('markets', []):
                for opt in market['outcomes']:
                    p_name = opt['description']
                    # Use a simple heuristic: if the player's name is in the team_map already, keep it
                    # otherwise, we assign based on common sense (or just use the game data)
                    # To be safe, we'll associate them with the game context
                    p_data = {'name': p_name, 'line': float(opt['point']), 'team': home if p_name in str(game) else away}
                    
                    # Store unique player per team to avoid duplicate names in different games
                    team_map[p_data['team']][p_name] = p_data

    # 2. Convert to list of potential anchor pairs
    correlated_pairs = []
    for team, players in team_map.items():
        sorted_p = sorted(players.values(), key=lambda x: x['line'], reverse=True)
        if len(sorted_p) >= 2:
            correlated_pairs.append({
                'more': {**sorted_p[0], 'pick': 'MORE'},
                'less': {**sorted_p[1], 'pick': 'LESS'}
            })

    random.shuffle(correlated_pairs)
    final_slips = []
    used_globally = set() # This is the master list of names

    # 3. Waterfall logic (6-5-4-3) to get 10 slips
    for target_size in [6, 5, 4, 3]:
        while len(final_slips) < 10:
            current_slip = []
            
            # Find an anchor where BOTH players are unused
            anchor = next((cp for cp in correlated_pairs if cp['more']['name'] not in used_globally 
                           and cp['less']['name'] not in used_globally), None)
            
            if not anchor: break
            
            current_slip.extend([anchor['more'], anchor['less']])
            # Immediately mark as used so fillers can't grab them
            temp_used = {anchor['more']['name'], anchor['less']['name']}
            
            # Fill remaining slots from any team, provided they aren't used globally
            filler_pool = []
            for team_players in team_map.values():
                for p in team_players.values():
                    if p['name'] not in used_globally and p['name'] not in temp_used:
                        filler_pool.append(p)
            
            random.shuffle(filler_pool)
            needed = target_size - len(current_slip)
            
            if len(filler_pool) >= needed:
                for i in range(needed):
                    f = filler_pool[i].copy()
                    f['pick'] = 'LESS' if i % 2 == 0 else 'MORE'
                    current_slip.append(f)
                
                # Success! Save slip and update global blacklist
                final_slips.append(current_slip)
                for p in current_slip:
                    used_globally.add(p['name'])
            else:
                break 

    return final_slips

# (The calculate_success_rate and alert_discord functions remain the same)
