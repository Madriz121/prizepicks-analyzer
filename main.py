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

    # Fetching up to 10 games to ensure enough players for ten 6-man slips
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
    pair_pool = []
    for game in data:
        # Organize by team to find Alpha/Beta pairs
        for team_key in ['home_team', 'away_team']:
            team_name = game[team_key]
            players = []
            for book in game.get('bookmakers', []):
                if book['key'] in ['draftkings', 'fanduel']:
                    for market in book.get('markets', []):
                        for opt in market['outcomes']:
                            players.append({'name': opt['description'], 'line': float(opt['point']), 'team': team_name})
            
            # Create Over/Under pairs for each team
            sorted_p = sorted(players, key=lambda x: x['line'], reverse=True)
            if len(sorted_p) >= 2:
                pair_pool.append([
                    {'name': sorted_p[0]['name'], 'line': sorted_p[0]['line'], 'pick': 'MORE', 'team': team_name},
                    {'name': sorted_p[1]['name'], 'line': sorted_p[1]['line'], 'pick': 'LESS', 'team': team_name}
                ])

    random.shuffle(pair_pool)
    final_slips = []
    used_global_players = set()

    # Step-down Logic: Prioritize 6-man, then 5, then 4
    for target_size in [6, 5, 4]:
        while True:
            current_entry = []
            potential_pairs = []
            
            # Find enough pairs to reach the target size
            for pair in pair_pool:
                p1, p2 = pair[0], pair[1]
                if p1['name'] not in used_global_players and p2['name'] not in used_global_players:
                    # PrizePicks needs at least 2 teams; our pair logic handles this as we add pairs from diff games
                    potential_pairs.append(pair)
                    if len(potential_pairs) * 2 >= target_size:
                        break
            
            # If we found enough pairs for this specific target size
            if len(potential_pairs) * 2 >= target_size:
                for pair in potential_pairs:
                    current_entry.extend(pair)
                    used_global_players.add(pair[0]['name'])
                    used_global_players.add(pair[1]['name'])
                
                # Truncate if we hit 6-man limit (since we add in pairs)
                final_slips.append(current_entry[:target_size])
                if len(final_slips) >= 10: return final_slips
            else:
                # Move to next smaller slip size (e.g., from 6 to 5)
                break

    return final_slips

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not entries: return

    webhook = DiscordWebhook(url=webhook_url)
    for i, entry in enumerate(entries):
        size = len(entry)
        color = "FFD100" if size == 6 else "C0C0C0" # Gold for 6, Silver for others
        embed = DiscordEmbed(title=f"🚀 Entry #{i+1} ({size}-Man Flex)", color=color)
        
        for p in entry:
            direction = "MORE 📈" if p['pick'] == "MORE" else "LESS 📉"
            embed.add_embed_field(name=p['name'], value=f"**{direction} {p['line']}** ({p['team']})", inline=True)
        
        webhook.add_embed(embed)
        if (i+1) % 5 == 0:
            webhook.execute()
            webhook = DiscordWebhook(url=webhook_url)
    
    if entries: webhook.execute()

if __name__ == "__main__":
    raw_data = get_nba_data()
    entries = build_usage_slips(raw_data)
    alert_discord(entries)
