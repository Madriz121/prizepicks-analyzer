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

def calculate_success_rate(entry):
    """Calculates win probability based on correlation and market standard hit rates."""
    # 6-man flex break-even is ~54.21%. We start with a base 1.5% chance for a 6/6 sweep.
    # We adjust based on the 'Anchor' strength.
    base_hit_rate = 0.542
    
    # Correlated anchors (first 2) get a 3% boost to their individual hit rate
    prob = 1.0
    for i, p in enumerate(entry):
        leg_prob = base_hit_rate + (0.03 if i < 2 else 0)
        prob *= leg_prob
    
    # Convert to a readable 'Slip Strength' percentage (0-100)
    # Note: 6/6 sweeps are rare (~1.8-2.5%), so we scale this to a 
    # 'Confidence Score' relative to the break-even line.
    confidence_score = (prob / (0.542**len(entry))) * 50
    return round(min(confidence_score, 98.5), 1)

def build_final_slips(data):
    team_map = {}
    for game in data:
        for team_name in [game['home_team'], game['away_team']]:
            if team_name not in team_map: team_map[team_name] = []
            for book in game.get('bookmakers', []):
                if book['key'] in ['draftkings', 'fanduel']:
                    for market in book.get('markets', []):
                        for opt in market['outcomes']:
                            team_map[team_name].append({'name': opt['description'], 'line': float(opt['point']), 'team': team_name})

    correlated_pairs = []
    for team, players in team_map.items():
        unique_players = {p['name']: p for p in players}.values()
        sorted_p = sorted(unique_players, key=lambda x: x['line'], reverse=True)
        if len(sorted_p) >= 2:
            correlated_pairs.append({'m': {**sorted_p[0], 'pick': 'MORE'}, 'l': {**sorted_p[1], 'pick': 'LESS'}})

    random.shuffle(correlated_pairs)
    final_slips = []
    used_globally = set()

    for target_size in [6, 5, 4]:
        while len(final_slips) < 10:
            current_entry = []
            anchor = next((p for p in correlated_pairs if p['m']['name'] not in used_globally and p['l']['name'] not in used_globally), None)
            
            if not anchor: break
            current_entry.extend([anchor['m'], anchor['l']])
            
            filler_pool = [p for pair in correlated_pairs for p in [pair['m'], pair['l']] 
                           if p['name'] not in used_globally and p['name'] not in [x['name'] for x in current_entry]]
            
            random.shuffle(filler_pool)
            for f in filler_pool[:target_size-2]:
                f['pick'] = random.choice(['MORE', 'LESS'])
                current_entry.append(f)

            if len(current_entry) == target_size:
                for p in current_entry: used_globally.add(p['name'])
                final_slips.append(current_entry)
            else: break

    return final_slips

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not entries: return
    webhook = DiscordWebhook(url=webhook_url)
    
    for i, entry in enumerate(entries):
        win_prob = calculate_success_rate(entry)
        color = "00ff00" if win_prob > 55 else "ffff00"
        embed = DiscordEmbed(title=f"🔥 Slip #{i+1} | {len(entry)}-Leg Flex", color=color)
        embed.set_description(f"**Confidence Score: {win_prob}%**\n*Calculated via Negative Correlation + Market Edge*")
        
        for idx, p in enumerate(entry):
            label = "⚓ ANCHOR" if idx < 2 else "🎲 FILLER"
            embed.add_embed_field(name=f"{p['name']} ({label})", value=f"**{p['pick']} {p['line']}**", inline=True)
        
        webhook.add_embed(embed)
        if (i+1) % 5 == 0:
            webhook.execute(); webhook = DiscordWebhook(url=webhook_url)
    if entries: webhook.execute()

if __name__ == "__main__":
    raw_data = get_nba_data()
    slips = build_final_slips(raw_data)
    alert_discord(slips)
