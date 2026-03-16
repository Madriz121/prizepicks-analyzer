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

    # Fetching up to 10 games to ensure a massive pool of unique players
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

def build_usage_slips(data):
    # Step 1: Flatten all unique teammate pairs from the slate
    pair_pool = []
    for game in data:
        for team_key in ['home_team', 'away_team']:
            team_name = game[team_key]
            players = []
            for book in game.get('bookmakers', []):
                if book['key'] in ['draftkings', 'fanduel']:
                    for market in book.get('markets', []):
                        for opt in market['outcomes']:
                            players.append({'name': opt['description'], 'line': float(opt['point']), 'team': team_name})
            
            # Sort by highest line to find the Alpha/Beta usage correlation
            sorted_p = sorted(players, key=lambda x: x['line'], reverse=True)
            if len(sorted_p) >= 2:
                pair_pool.append([
                    {'name': sorted_p[0]['name'], 'line': sorted_p[0]['line'], 'pick': 'MORE', 'team': team_name},
                    {'name': sorted_p[1]['name'], 'line': sorted_p[1]['line'], 'pick': 'LESS', 'team': team_name}
                ])

    random.shuffle(pair_pool)
    final_slips = []
    used_globally = set()

    # Step 2: Priority Waterfall (6 -> 5 -> 4)
    for target_size in [6, 5, 4]:
        while True:
            current_entry = []
            used_in_this_slip = set() # Local check to prevent image_e5ebf3.png error
            
            # Identify pairs that haven't been used globally or locally
            for pair in pair_pool:
                p1, p2 = pair[0], pair[1]
                
                # STRICT UNIQUE CHECK
                if p1['name'] not in used_globally and p2['name'] not in used_globally:
                    if p1['name'] not in used_in_this_slip and p2['name'] not in used_in_this_slip:
                        current_entry.extend([p1, p2])
                        used_in_this_slip.add(p1['name'])
                        used_in_this_slip.add(p2['name'])
                        
                        if len(current_entry) >= target_size:
                            break
            
            # If we successfully built a full slip of the target size
            if len(current_entry) >= target_size:
                final_entry = current_entry[:target_size]
                final_slips.append(final_entry)
                # Lock players globally so they never appear in another slip today
                for p in final_entry:
                    used_globally.add(p['name'])
                
                if len(final_slips) >= 10: return final_slips
            else:
                # No more possible slips of this size, move to the next size down
                break

    return final_slips

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not entries: return

    webhook = DiscordWebhook(url=webhook_url)
    for i, entry in enumerate(entries):
        size = len(entry)
        color = "FFD100" if size == 6 else "3498db"
        embed = DiscordEmbed(title=f"📊 Entry #{i+1} ({size}-Man Flex)", color=color)
        
        for p in entry:
            direction = "MORE 📈" if p['pick'] == "MORE" else "LESS 📉"
            embed.add_embed_field(name=p['name'], value=f"**{direction} {p['line']}**\n{p['team']}", inline=True)
        
        webhook.add_embed(embed)
        if (i+1) % 5 == 0:
            webhook.execute()
            webhook = DiscordWebhook(url=webhook_url)
    
    if entries: webhook.execute()

if __name__ == "__main__":
    raw_data = get_nba_data()
    entries = build_usage_slips(raw_data)
    alert_discord(entries)
