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

    # Get data for 10 games to have a large pool of teammates
    for e in events[:10]:
        eid = e['id']
        props_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'player_points', 'oddsFormat': 'american'}
        resp = requests.get(props_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            # We must know who plays for who
            data['home_team'] = e['home_team']
            data['away_team'] = e['away_team']
            all_props.append(data)
        time.sleep(0.5)
    return all_props

def build_usage_theft_slips(data):
    slips = []
    used_players = set()

    # Step 1: Organize players by team
    for game in data:
        team_rosters = {}
        for book in game.get('bookmakers', []):
            if book['key'] in ['draftkings', 'fanduel']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        player = opt['description']
                        line = float(opt['point'])
                        # This logic assumes the API returns enough info to map teams
                        # (In a production env, you'd use a mapping dict)
                        team = game['home_team'] # Simplified for logic
                        if team not in team_rosters: team_rosters[team] = []
                        team_rosters[team].append({'name': player, 'line': line})

        # Step 2: Correlation Logic - Find the "Alpha" and "Beta"
        for team, players in team_rosters.items():
            # Sort by highest line
            sorted_players = sorted(players, key=lambda x: x['line'], reverse=True)
            
            if len(sorted_players) >= 2:
                alpha = sorted_players[0] # High usage star
                beta = sorted_players[1]  # The "robbed" teammate
                
                if alpha['name'] not in used_players and beta['name'] not in used_players:
                    # Logic: If Star goes OVER, Teammate likely goes UNDER
                    correlated_pair = [
                        {'name': alpha['name'], 'line': alpha['line'], 'pick': 'MORE', 'type': 'Star'},
                        {'name': beta['name'], 'line': beta['line'], 'pick': 'LESS', 'type': 'Usage-Theft'}
                    ]
                    slips.append(correlated_pair)
                    used_players.add(alpha['name'])
                    used_players.add(beta['name'])

    # Step 3: Bundle pairs into 4-man or 6-man slips
    final_entries = []
    for i in range(0, len(slips), 2): # Take 2 pairs (4 players total)
        if i + 1 < len(slips):
            final_entries.append(slips[i] + slips[i+1])
            
    return final_entries[:10] # Return up to 10 entries

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)
    
    for i, entry in enumerate(entries):
        embed = DiscordEmbed(title=f"📉 Usage Theft Entry #{i+1}", color="e67e22")
        for p in entry:
            tag = "⭐" if p['type'] == 'Star' else "📉"
            embed.add_embed_field(name=f"{tag} {p['name']}", value=f"**{p['pick']} {p['line']}**", inline=True)
        webhook.add_embed(embed)
        if (i+1) % 5 == 0: # Send in batches of 5 to avoid Discord limits
            webhook.execute()
            webhook = DiscordWebhook(url=webhook_url)
    
    if len(entries) > 0:
        webhook.execute()

if __name__ == "__main__":
    raw_data = get_nba_data()
    entries = build_usage_theft_slips(raw_data)
    alert_discord(entries)
