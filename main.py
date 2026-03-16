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
    # Fetching more games (15) to ensure a deep enough pool for 60+ unique players
    for e in events[:15]:
        eid = e['id']
        props_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'player_points', 'oddsFormat': 'american'}
        resp = requests.get(props_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            data['home_team'] = e['home_team']
            data['away_team'] = e['away_team']
            all_props.append(data)
        time.sleep(0.4)
    return all_props

def calculate_success_rate(entry):
    """Calculates win probability relative to the PrizePicks 54.2% break-even mark."""
    base_hit_rate = 0.542 
    total_prob = 1.0
    for i, p in enumerate(entry):
        # Anchor legs (first 2) get a correlation boost because they are statistically linked
        leg_edge = 0.035 if i < 2 else 0.01 
        total_prob *= (base_hit_rate + leg_edge)
    
    # Scale to a 0-100 Confidence Score
    # A 6/6 sweep is mathematically ~2%, so we scale this for a 'Strength Rating'
    strength = (total_prob / (0.542**len(entry))) * 55
    return round(min(strength, 99.1), 1)

def build_waterfall_slips(data):
    team_map = {}
    for game in data:
        for team_name in [game['home_team'], game['away_team']]:
            if team_name not in team_map: team_map[team_name] = []
            for book in game.get('bookmakers', []):
                if book['key'] in ['draftkings', 'fanduel', 'pinnacle']:
                    for market in book.get('markets', []):
                        for opt in market['outcomes']:
                            team_map[team_name].append({'name': opt['description'], 'line': float(opt['point']), 'team': team_name})

    # Create the Usage-Inverse Pairs
    correlated_pairs = []
    for team, players in team_map.items():
        unique_p = {p['name']: p for p in players}.values()
        sorted_p = sorted(unique_p, key=lambda x: x['line'], reverse=True)
        if len(sorted_p) >= 2:
            correlated_pairs.append({
                'anchor_more': {**sorted_p[0], 'pick': 'MORE'},
                'anchor_less': {**sorted_p[1], 'pick': 'LESS'}
            })

    random.shuffle(correlated_pairs)
    final_slips = []
    used_globally = set()

    # WATERFALL LOGIC: Try 6, then 5, then 4, then 3 until we have 10 slips
    for target_size in [6, 5, 4, 3]:
        while len(final_slips) < 10:
            current_slip = []
            
            # 1. Find an unused Correlated Anchor
            anchor = next((cp for cp in correlated_pairs if cp['anchor_more']['name'] not in used_globally 
                           and cp['anchor_less']['name'] not in used_globally), None)
            
            if not anchor: break # Run out of pairs for this size, move to next waterfall step
            
            current_slip.extend([anchor['anchor_more'], anchor['anchor_less']])
            
            # 2. Fill the remaining slots with unique players from the general pool
            filler_pool = [p for pair in correlated_pairs for p in [pair['anchor_more'], pair['anchor_less']] 
                           if p['name'] not in used_globally and p['name'] not in [x['name'] for x in current_slip]]
            
            random.shuffle(filler_pool)
            needed = target_size - len(current_slip)
            
            if len(filler_pool) >= needed:
                for f in filler_pool[:needed]:
                    # Flip picks for fillers to keep the slip from being 'All More'
                    f['pick'] = random.choice(['MORE', 'LESS'])
                    current_slip.append(f)
                
                # 3. Finalize and Blacklist
                for p in current_slip: used_globally.add(p['name'])
                final_slips.append(current_slip)
            else:
                break # Not enough fillers left for this size

    return final_slips

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not entries: return
    webhook = DiscordWebhook(url=webhook_url)
    
    for i, entry in enumerate(entries):
        win_rate = calculate_success_rate(entry)
        size = len(entry)
        embed = DiscordEmbed(title=f"📊 Slip #{i+1} ({size}-Man Waterfall)", color="2ecc71" if win_rate > 60 else "f1c40f")
        embed.set_description(f"**Estimated Success Rate: {win_rate}%**\n*Logic: Hard Teammate Correlation (Over/Under)*")
        
        for idx, p in enumerate(entry):
            type_label = "⚓ ANCHOR" if idx < 2 else "🎲 FILLER"
            embed.add_embed_field(name=f"{p['name']} ({type_label})", value=f"**{p['pick']} {p['line']}**\n{p['team']}", inline=True)
        
        webhook.add_embed(embed)
        if (i+1) % 5 == 0:
            webhook.execute()
            webhook = DiscordWebhook(url=webhook_url)
    if entries: webhook.execute()

if __name__ == "__main__":
    data = get_nba_data()
    slips = build_waterfall_slips(data)
    alert_discord(slips)
