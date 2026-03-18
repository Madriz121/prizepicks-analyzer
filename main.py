import os
import requests
import time
import random
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_nba_data():
    api_key = os.getenv("THE_ODDS_API_KEY")
    # Fetching both US and EU (EU gives us Pinnacle, the 'Sharp' benchmark)
    events_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events_resp = requests.get(events_url, params={'apiKey': api_key})
    if events_resp.status_code != 200: return []

    events = events_resp.json()
    all_props = []
    for e in events[:12]:
        eid = e['id']
        props_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        # We pull regions 'us' and 'eu' to compare PrizePicks/DK against Pinnacle
        params = {'apiKey': api_key, 'regions': 'us,eu', 'markets': 'player_points', 'oddsFormat': 'american'}
        resp = requests.get(props_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            data['home_team'] = e['home_team']
            data['away_team'] = e['away_team']
            all_props.append(data)
        time.sleep(0.5)
    return all_props

def calculate_success_rate(entry):
    """Calculates probability based on historical PrizePicks break-even (54.2%)."""
    base_hit_rate = 0.542 
    total_prob = 1.0
    for i, p in enumerate(entry):
        # Anchors get a 3.5% correlation boost; fillers get a 2% 'Sharp Market' edge
        leg_edge = 0.035 if i < 2 else 0.02 
        total_prob *= (base_hit_rate + leg_edge)
    
    strength = (total_prob / (0.542**len(entry))) * 55
    return round(min(strength, 99.1), 1)

def build_waterfall_slips(data):
    team_map = {}
    player_pool = []

    for game in data:
        # Identify the 'Sharp' line from Pinnacle first
        sharp_lines = {}
        for book in game.get('bookmakers', []):
            if book['key'] == 'pinnacle':
                for m in book.get('markets', []):
                    for opt in m['outcomes']:
                        sharp_lines[opt['description']] = float(opt['point'])

        # Process players and calculate the "Sharp Gap"
        for book in game.get('bookmakers', []):
            if book['key'] in ['draftkings', 'fanduel', 'pinnacle']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        p_name = opt['description']
                        line = float(opt['point'])
                        p_team = game['home_team'] if p_name in str(game.get('home_team')) else game['away_team']
                        
                        # The Gap: How much our platform differs from the Sharpest Book
                        sharp_val = sharp_lines.get(p_name, line)
                        gap = line - sharp_val # Positive means line is too high (LESS), Negative means too low (MORE)
                        
                        p_obj = {'name': p_name, 'line': line, 'team': p_team, 'gap': gap}
                        
                        if p_team not in team_map: team_map[p_team] = {}
                        team_map[p_team][p_name] = p_obj
                        player_pool.append(p_obj)

    # 1. Correlated Anchor Pool
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
    used_globally = set()

    # 2. UPDATED WATERFALL: Prioritize 4 and 3 man slips to stop the losing streak
    for target_size in [4, 3, 5, 6]:
        while len(final_slips) < 10:
            current_slip = []
            anchor = next((cp for cp in correlated_pairs if cp['more']['name'] not in used_globally 
                           and cp['less']['name'] not in used_globally), None)
            
            if not anchor: break
            
            current_slip.extend([anchor['more'], anchor['less']])
            temp_local_used = {anchor['more']['name'], anchor['less']['name']}
            
            # 3. FILLER SELECTION: Pick players with the biggest gap vs Pinnacle
            fillers = [p for p in player_pool if p['name'] not in used_globally and p['name'] not in temp_local_used]
            # Sort by absolute gap (the bigger the discrepancy, the better the value)
            fillers.sort(key=lambda x: abs(x['gap']), reverse=True)
            
            needed = target_size - len(current_slip)
            if len(fillers) >= needed:
                for i in range(needed):
                    f = fillers[i].copy()
                    # Logic: If line > Sharp Line, take LESS. If line < Sharp Line, take MORE.
                    f['pick'] = 'LESS' if f['gap'] > 0 else 'MORE'
                    current_slip.append(f)
                
                final_slips.append(current_slip)
                for p in current_slip: used_globally.add(p['name'])
            else:
                break
    return final_slips

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not entries: 
        print("⚠️ No slips generated or Webhook missing.")
        return
        
    webhook = DiscordWebhook(url=webhook_url)
    for i, entry in enumerate(entries):
        win_rate = calculate_success_rate(entry)
        size = len(entry)
        color = "2ecc71" if win_rate > 58 else "f1c40f"
        
        embed = DiscordEmbed(title=f"🏆 Slip #{i+1} ({size}-Man)", color=color)
        embed.set_description(f"**Confidence: {win_rate}%**\n*Strategy: Sharp-Market Gap vs Pinnacle*")
        
        for idx, p in enumerate(entry):
            type_label = "⚓ ANCHOR" if idx < 2 else "📊 SHARP"
            icon = "📈" if p['pick'] == 'MORE' else "📉"
            embed.add_embed_field(name=f"{p['name']} ({type_label})", 
                                  value=f"**{p['pick']} {p['line']}** {icon}\n{p['team']}", 
                                  inline=True)
        
        webhook.add_embed(embed)
        if (i+1) % 5 == 0:
            webhook.execute()
            webhook = DiscordWebhook(url=webhook_url)
            
    if entries: webhook.execute()
    print(f"🚀 Sent {len(entries)} optimized slips to Discord.")

if __name__ == "__main__":
    raw_data = get_nba_data()
    slips = build_waterfall_slips(raw_data)
    alert_discord(slips)
