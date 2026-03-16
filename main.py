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

    for e in events[:12]:
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

def build_strict_correlated_slips(data):
    # Step 1: Group players by their actual teams
    team_map = {}
    for game in data:
        for team_name in [game['home_team'], game['away_team']]:
            if team_name not in team_map: team_map[team_name] = []
            for book in game.get('bookmakers', []):
                if book['key'] in ['draftkings', 'fanduel']:
                    for market in book.get('markets', []):
                        for opt in market['outcomes']:
                            team_map[team_name].append({
                                'name': opt['description'],
                                'line': float(opt['point']),
                                'team': team_name
                            })

    # Step 2: Create "Usage Inversion" pairs (Star MORE, Secondary LESS)
    correlated_pairs = []
    for team, players in team_map.items():
        # Remove duplicate player entries from different books
        unique_players = {p['name']: p for p in players}.values()
        sorted_p = sorted(unique_players, key=lambda x: x['line'], reverse=True)
        
        if len(sorted_p) >= 2:
            correlated_pairs.append({
                'more_pick': {**sorted_p[0], 'pick': 'MORE'},
                'less_pick': {**sorted_p[1], 'pick': 'LESS'}
            })

    random.shuffle(correlated_pairs)
    final_slips = []
    used_globally = set()

    # Step 3: Build 10 slips using the Anchor + Fill method
    for target_size in [6, 5, 4]:
        while len(final_slips) < 10:
            current_entry = []
            
            # A. Pick a Correlated Anchor (One Team, One More, One Less)
            found_anchor = False
            for pair in correlated_pairs:
                p1, p2 = pair['more_pick'], pair['less_pick']
                if p1['name'] not in used_globally and p2['name'] not in used_globally:
                    current_entry.extend([p1, p2])
                    found_anchor = True
                    break
            
            if not found_anchor: break # Pool exhausted for this size

            # B. Fill remaining spots with UNIQUE players from OTHER games
            # We alternate fillers to keep the slip balanced (not all MORE or all LESS)
            remaining_needed = target_size - len(current_entry)
            fillers_found = 0
            
            # Create a flat pool of remaining available players
            filler_pool = []
            for pair in correlated_pairs:
                for p in [pair['more_pick'], pair['less_pick']]:
                    if p['name'] not in used_globally and p['name'] not in [x['name'] for x in current_entry]:
                        filler_pool.append(p)
            
            random.shuffle(filler_pool)
            for f in filler_pool:
                if fillers_found < remaining_needed:
                    # Alternate the pick for fillers to maintain slip health
                    f['pick'] = 'LESS' if fillers_found % 2 == 0 else 'MORE'
                    current_entry.append(f)
                    fillers_found += 1
                else:
                    break

            # C. Finalize Slip
            if len(current_entry) == target_size:
                for p in current_entry: used_globally.add(p['name'])
                final_slips.append(current_entry)
            else:
                break

    return final_slips

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not entries: return
    webhook = DiscordWebhook(url=webhook_url)
    
    for i, entry in enumerate(entries):
        embed = DiscordEmbed(title=f"🔒 Correlated Entry #{i+1} ({len(entry)}-Man)", color="FF5722")
        for idx, p in enumerate(entry):
            # Highlight the correlated anchor pair
            label = "🛡️ ANCHOR" if idx < 2 else "🎲 FILLER"
            icon = "📈" if p['pick'] == 'MORE' else "📉"
            embed.add_embed_field(name=f"{p['name']} ({label})", value=f"**{p['pick']} {p['line']}** {icon}\n{p['team']}", inline=True)
        
        webhook.add_embed(embed)
        if (i+1) % 5 == 0:
            webhook.execute()
            webhook = DiscordWebhook(url=webhook_url)
    if entries: webhook.execute()

if __name__ == "__main__":
    raw_data = get_nba_data()
    entries = build_strict_correlated_slips(raw_data)
    alert_discord(entries)
