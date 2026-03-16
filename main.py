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

    # Fetch 10+ games. We need 60 unique players for ten 6-man slips.
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

def build_strict_unique_slips(data):
    # Flatten everything into a single master pool of players
    master_pool = []
    for game in data:
        for book in game.get('bookmakers', []):
            if book['key'] in ['draftkings', 'fanduel']:
                for market in book.get('markets', []):
                    # Sort players by line to keep correlation info
                    outcomes = sorted(market['outcomes'], key=lambda x: float(x['point']), reverse=True)
                    for i, opt in enumerate(outcomes):
                        master_pool.append({
                            'name': opt['description'],
                            'line': float(opt['point']),
                            'team': game['home_team'] if i % 2 == 0 else game['away_team'],
                            'rank': i # 0 is Alpha (Star), 1+ are Betas
                        })

    random.shuffle(master_pool)
    final_slips = []
    # THIS IS THE KEY: Players in this set can NEVER be picked again.
    blacklisted_players = set()

    # Step-down priority: 6-man > 5-man > 4-man
    for target_size in [6, 5, 4]:
        while len(final_slips) < 10:
            current_entry = []
            
            # Find unique players for this slip
            for p in master_pool:
                if p['name'] not in blacklisted_players:
                    # Assign MORE/LESS based on usage rank (0 = MORE, others = LESS)
                    p['pick'] = 'MORE' if p['rank'] == 0 else 'LESS'
                    current_entry.append(p)
                    blacklisted_players.add(p['name']) # Immediately blacklist
                    
                    if len(current_entry) == target_size:
                        break
            
            if len(current_entry) == target_size:
                final_slips.append(current_entry)
            else:
                # Not enough unique players left for this size, try next size down
                break

    return final_slips

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not entries: return

    webhook = DiscordWebhook(url=webhook_url)
    for i, entry in enumerate(entries):
        size = len(entry)
        embed = DiscordEmbed(title=f"💎 Unique Entry #{i+1} ({size}-Man)", color="2ecc71")
        
        for p in entry:
            emoji = "🔥" if p['pick'] == 'MORE' else "❄️"
            embed.add_embed_field(
                name=f"{p['name']}", 
                value=f"**{p['pick']} {p['line']}** {emoji}\n_{p['team']}_", 
                inline=True
            )
        
        webhook.add_embed(embed)
        if (i+1) % 5 == 0:
            webhook.execute()
            webhook = DiscordWebhook(url=webhook_url)
    
    if entries: webhook.execute()

if __name__ == "__main__":
    raw_data = get_nba_data()
    entries = build_strict_unique_slips(raw_data)
    alert_discord(entries)
