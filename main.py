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

    # Get up to 10 games to have a massive pool (60 unique players needed for 10 6-man slips)
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

def build_unique_slips(data):
    pair_pool = []
    # 1. Create the pool of Alpha/Beta pairs
    for game in data:
        for team_key in ['home_team', 'away_team']:
            team_name = game[team_key]
            players = []
            for book in game.get('bookmakers', []):
                if book['key'] in ['draftkings', 'fanduel']:
                    for market in book.get('markets', []):
                        for opt in market['outcomes']:
                            players.append({'name': opt['description'], 'line': float(opt['point']), 'team': team_name})
            
            sorted_p = sorted(players, key=lambda x: x['line'], reverse=True)
            if len(sorted_p) >= 2:
                pair_pool.append([
                    {'name': sorted_p[0]['name'], 'line': sorted_p[0]['line'], 'pick': 'MORE', 'team': team_name},
                    {'name': sorted_p[1]['name'], 'line': sorted_p[1]['line'], 'pick': 'LESS', 'team': team_name}
                ])

    random.shuffle(pair_pool)
    final_slips = []
    used_globally = set()

    # 2. Priority Waterfall (6 -> 5 -> 4)
    for target_size in [6, 5, 4]:
        while len(final_slips) < 10:
            current_entry = []
            used_in_this_slip = set() # Local unique check
            
            # Identify pairs that fit the unique constraints
            for pair in pair_pool:
                p1, p2 = pair[0], pair[1]
                
                # Check Global AND Local sets
                if p1['name'] not in used_globally and p2['name'] not in used_globally:
                    if p1['name'] not in used_in_this_slip and p2['name'] not in used_in_this_slip:
                        current_entry.extend([p1, p2])
                        used_in_this_slip.add(p1['name'])
                        used_in_this_slip.add(p2['name'])
                        
                        if len(current_entry) >= target_size:
                            break
            
            # If we hit the target size, lock the players and save the slip
            if len(current_entry) >= target_size:
                final_entry = current_entry[:target_size]
                for p in final_entry:
                    used_globally.add(p['name'])
                final_slips.append(final_entry)
            else:
                # No more possible slips of this size, try next size down
                break

    return final_slips

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not entries: return

    webhook = DiscordWebhook(url=webhook_url)
    for i, entry in enumerate(entries):
        size = len(entry)
        color = "FFD100" if size == 6 else "3498db"
        embed = DiscordEmbed(title=f"🏆 Slip #{i+1} ({size}-Man Flex)", color=color)
        
        for p in entry:
            emoji = "📈" if p['pick'] == "MORE" else "📉"
            embed.add_embed_field(name=f"{p['name']} ({p['team']})", value=f"**{p['pick']} {p['line']}** {emoji}", inline=True)
        
        webhook.add_embed(embed)
        # Send in batches of 5 to respect Discord's embed limit per message
        if (i+1) % 5 == 0:
            webhook.execute()
            webhook = DiscordWebhook(url=webhook_url)
    
    if entries: webhook.execute()

if __name__ == "__main__":
    raw_data = get_nba_data()
    entries = build_unique_slips(raw_data)
    alert_discord(entries)
