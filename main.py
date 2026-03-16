import os
import requests
import time
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_nba_data():
    api_key = os.getenv("THE_ODDS_API_KEY")
    # Step 1: Get the list of Event IDs for upcoming NBA games
    events_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events_resp = requests.get(events_url, params={'apiKey': api_key})
    
    if events_resp.status_code != 200:
        print(f"❌ Failed to fetch events: {events_resp.status_code}")
        return []

    event_ids = [e['id'] for e in events_resp.json()]
    all_props = []

    # Step 2: Fetch props for the first 3 games (to save API credits)
    for eid in event_ids[:3]:
        props_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {
            'apiKey': api_key,
            'regions': 'us',
            'markets': 'player_points',
            'oddsFormat': 'american'
        }
        resp = requests.get(props_url, params=params)
        if resp.status_code == 200:
            all_props.append(resp.json())
        time.sleep(1) # Be gentle with the API
    
    return all_props

def build_unique_parlays(data):
    consistency_slip = []
    volatility_slip = []
    used_players = set()

    for event in data:
        for book in event.get('bookmakers', []):
            if book['key'] in ['draftkings', 'fanduel']:
                for market in book.get('markets', []):
                    # Sort outcomes by line value (high to low)
                    outcomes = sorted(market['outcomes'], key=lambda x: x['point'], reverse=True)
                    
                    for opt in outcomes:
                        player = opt['description']
                        line = float(opt['point'])
                        
                        if player not in used_players:
                            # CONSISTENCY: High-tier players (25+ pts)
                            if line >= 24.5 and len(consistency_slip) < 3:
                                consistency_slip.append({'name': player, 'line': line, 'type': 'OVER'})
                                used_players.add(player)
                            
                            # VOLATILITY: Mid-tier players (12-18 pts)
                            elif 11.5 <= line <= 18.5 and len(volatility_slip) < 3:
                                volatility_slip.append({'name': player, 'line': line, 'type': 'UNDER'})
                                used_players.add(player)

    return consistency_slip, volatility_slip

def alert_discord(safe, risky):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)

    if safe:
        safe_embed = DiscordEmbed(title="🛡️ CONSISTENCY PARLAY (Unique Players)", color="2ecc71")
        for p in safe:
            safe_embed.add_embed_field(name=p['name'], value=f"Points: **{p['type']} {p['line']}**")
        webhook.add_embed(safe_embed)

    if risky:
        risk_embed = DiscordEmbed(title="🎲 VOLATILITY PARLAY (Unique Players)", color="e74c3c")
        for p in risky:
            risk_embed.add_embed_field(name=p['name'], value=f"Points: **{p['type']} {p['line']}**")
        webhook.add_embed(risk_embed)

    webhook.execute()

if __name__ == "__main__":
    raw_data = get_nba_data()
    s1, s2 = build_unique_parlays(raw_data)
    alert_discord(s1, s2)
