import os
import requests
import time
import random
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_nba_data():
    api_key = os.getenv("THE_ODDS_API_KEY")
    # Fetching with 'eu' region to ensure we get Pinnacle (the gold standard for sharp lines)
    events_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events_resp = requests.get(events_url, params={'apiKey': api_key})
    if events_resp.status_code != 200: return []

    events = events_resp.json()
    all_props = []
    # Focus on the next 10 games for high liquidity and fresh lines
    for e in events[:10]:
        eid = e['id']
        props_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        # We now pull from US (for PrizePicks/DraftKings) and EU (for Pinnacle) to compare
        params = {'apiKey': api_key, 'regions': 'us,eu', 'markets': 'player_points', 'oddsFormat': 'american'}
        resp = requests.get(props_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            data['home_team'] = e['home_team']
            data['away_team'] = e['away_team']
            all_props.append(data)
        time.sleep(0.5) 
    return all_props

def get_sharp_market_data(game_data):
    """Extracts Pinnacle lines to act as the 'Truth' benchmark."""
    sharp_lines = {}
    for book in game_data.get('bookmakers', []):
        if book['key'] == 'pinnacle':
            for market in book.get('markets', []):
                for opt in market['outcomes']:
                    sharp_lines[opt['description']] = float(opt['point'])
    return sharp_lines

def build_smart_slips(data):
    team_map = {}
    player_pool = []
    
    for game in data:
        sharp_benchmarks = get_sharp_market_data(game)
        
        for book in game.get('bookmakers', []):
            # Only use high-accuracy books to build our comparison pool
            if book['key'] in ['draftkings', 'fanduel', 'pinnacle']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        name = opt['description']
                        line = float(opt['point'])
                        
                        # Calculate Discrepancy: Difference between current book and Pinnacle
                        sharp_line = sharp_benchmarks.get(name, line)
                        diff = abs(line - sharp_line)
                        
                        p_obj = {
                            'name': name, 
                            'line': line, 
                            'sharp_diff': diff,
                            'team': game['home_team'] if name in str(game.get('home_team')) else game['away_team']
                        }
                        
                        # Add to team map for correlation
                        if p_obj['team'] not in team_map: team_map[p_obj['team']] = {}
                        team_map[p_obj['team']][name] = p_obj
                        player_pool.append(p_obj)

    # 1. Build Correlated Anchors
    correlated_pairs = []
    for team, players in team_map.items():
        sorted_p = sorted(players.values(), key=lambda x: x['line'], reverse=True)
        if len(sorted_p) >= 2:
            correlated_pairs.append({
                'more': {**sorted_p[0], 'pick': 'MORE'},
                'less': {**sorted_p[1], 'pick': 'LESS'}
            })

    # 2. Smart Waterfall: Prioritize High-Probability smaller slips [4, 3, 5, 6]
    # This helps break the losing streak by focusing on more attainable payouts first.
    final_slips = []
    used_globally = set()

    for target_size in [4, 3, 5, 6]:
        while len(final_slips) < 10:
            current_slip = []
            anchor = next((cp for cp in correlated_pairs if cp['more']['name'] not in used_globally 
                           and cp['less']['name'] not in used_globally), None)
            
            if not anchor: break
            
            current_slip.extend([anchor['more'], anchor['less']])
            temp_local_used = {anchor['more']['name'], anchor['less']['name']}
            
            # 3. SELECT FILLERS BY SHARP DISCREPANCY
            # Instead of random, we sort the entire pool by how much they differ from Pinnacle
            filler_pool = [p for p in player_pool if p['name'] not in used_globally and p['name'] not in temp_local_used]
            filler_pool.sort(key=lambda x: x['sharp_diff'], reverse=True)
            
            needed = target_size - len(current_slip)
            if len(filler_pool) >= needed:
                for i in range(needed):
                    f = filler_pool[i].copy()
                    # If line is LOWER than Pinnacle, go MORE. If HIGHER, go LESS.
                    f['pick'] = 'MORE' if f['sharp_diff'] > 0 else 'LESS' 
                    current_slip.append(f)
                
                final_slips.append(current_slip)
                for p in current_slip: used_globally.add(p['name'])
            else:
                break

    return final_slips

# (Keep your calculate_success_rate and alert_discord functions as they are, 
# but they will now receive much higher-quality data)
