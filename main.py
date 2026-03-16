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
    # Fetching 15 games to ensure a massive pool (60+ players) for 10 unique slips
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
        # Anchor legs (first 2) get a 3.5% correlation boost; fillers get 1% market edge
        leg_edge = 0.035 if i < 2 else 0.01 
        total_prob *= (base_hit_rate + leg_edge)
    
    # Scale to a 0-100 Confidence Score
    strength = (total_prob / (0.542**len(entry))) * 55
    return round(min(strength, 99.1), 1)

def build_waterfall_slips(data):
    # 1. Map Teams to unique players
    team_map = {}
    for game in data:
        for team in [game['home_team'], game['away_team']]:
            if team not in team_map: team_map[team] = {}
        
        for book in game.get('bookmakers', []):
            if book['key'] in ['draftkings', 'fanduel', 'pinnacle']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        p_name = opt['description']
                        # Determine if player belongs to home or away team
                        p_team = game['home_team'] if p_name in str(game.get('home_team')) else game['away_team']
                        team_map[p_team][p_name] = {'name': p_name, 'line': float(opt['point']), 'team': p_team}

    # 2. Create the Correlated Anchor Pool
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
    used_globally = set() # Master registry to prevent duplicate players across ALL slips

    # 3. WATERFALL LOGIC: Try 6, then 5, then 4, then 3 until 10 slips are built
    for target_size in [6, 5, 4, 3]:
        while len(final_slips) < 10:
            current_slip = []
            
            # Step A: Find an Anchor where both players are 100% unused
            anchor = next((cp for cp in correlated_pairs if cp['more']['name'] not in used_globally 
                           and cp['less']['name'] not in used_globally), None)
            
            if not anchor: break # No more pairs for this size, move down the waterfall
            
            current_slip.extend([anchor['more'], anchor['less']])
            # Add to a temporary local set to prevent filler from grabbing them
            temp_local_used = {anchor['more']['name'], anchor['less']['name']}
            
            # Step B: Gather fillers who aren't in the global blacklist OR this current anchor
            filler_pool = []
            for t_players in team_map.values():
                for p in t_players.values():
                    if p['name'] not in used_globally and p['name'] not in temp_local_used:
                        filler_pool.append(p)
            
            random.shuffle(filler_pool)
            needed = target_size - len(current_slip)
            
            if len(filler_pool) >= needed:
                for i in range(needed):
                    f = filler_pool[i].copy()
                    # Balance the slip by alternating MORE/LESS for fillers
                    f['pick'] = 'LESS' if i % 2 == 0 else 'MORE'
                    current_slip.append(f)
                
                # Step C: Finalize and lock players globally
                final_slips.append(current_slip)
                for p in current_slip:
                    used_globally.add(p['name'])
            else:
                break # Not enough fillers left for this size

    return final_slips

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not entries: 
        print("⚠️ No slips to send.")
        return
        
    webhook = DiscordWebhook(url=webhook_url)
    for i, entry in enumerate(entries):
        win_rate = calculate_success_rate(entry)
        size = len(entry)
        # Color coding: Green for high confidence, Yellow for standard
        embed = DiscordEmbed(title=f"🏆 Slip #{i+1} ({size}-Man Flex)", color="2ecc71" if win_rate > 58 else "f1c40f")
        embed.set_description(f"**Confidence Score: {win_rate}%**\n*Logic: Forced Usage Theft (Star MORE / Teammate LESS)*")
        
        for idx, p in enumerate(entry):
            type_label = "⚓ ANCHOR" if idx < 2 else "🎲 FILLER"
            icon = "📈" if p['pick'] == 'MORE' else "📉"
            embed.add_embed_field(name=f"{p['name']} ({type_label})", value=f"**{p['pick']} {p['line']}** {icon}\n{p['team']}", inline=True)
        
        webhook.add_embed(embed)
        # Send in batches of 5
        if (i+1) % 5 == 0:
            webhook.execute()
            webhook = DiscordWebhook(url=webhook_url)
            
    if entries: webhook.execute()
    print(f"🚀 Successfully sent {len(entries)} unique slips to Discord.")

if __name__ == "__main__":
    raw_data = get_nba_data()
    slips = build_waterfall_slips(raw_data)
    alert_discord(slips)
