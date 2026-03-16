import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_nba_props():
    API_KEY = os.getenv("THE_ODDS_API_KEY")
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/props"
    params = {
        'apiKey': API_KEY,
        'regions': 'us',
        'markets': 'player_points', 
        'oddsFormat': 'american'
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"❌ API Error: {e}")
        return []

def build_parlays(events):
    # Dictionaries to track player data
    all_props = []
    used_players = set()
    
    for event in events:
        for book in event.get('bookmakers', []):
            market = next((m for m in book.get('markets', []) if m['key'] == 'player_points'), None)
            if market:
                for outcome in market.get('outcomes', []):
                    all_props.append({
                        'player': outcome['description'],
                        'line': float(outcome['point']),
                        'book': book['title']
                    })

    # 1. Build Consistency Slip (High Lines where books agree)
    # Strategy: Find players with lines > 25.5 (Star players with high floors)
    consistency_slip = []
    for p in sorted(all_props, key=lambda x: x['line'], reverse=True):
        if p['player'] not in used_players and len(consistency_slip) < 3:
            consistency_slip.append(p)
            used_players.add(p['player'])

    # 2. Build Volatility Slip (Lower lines that are likely to fluctuate)
    # Strategy: Players in the 15-20 point range who are "Inconsistent" scorers
    volatility_slip = []
    for p in sorted(all_props, key=lambda x: x['line']):
        if p['player'] not in used_players and 14 < p['line'] < 22 and len(volatility_slip) < 3:
            volatility_slip.append(p)
            used_players.add(p['player'])

    return consistency_slip, volatility_slip

def send_parlays_to_discord(safe, risky):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)

    # Embed 1: The Safety Parlay
    safe_embed = DiscordEmbed(title="🛡️ The Consistency Slip (High Floor)", color="2ecc71")
    for p in safe:
        safe_embed.add_embed_field(name=p['player'], value=f"Points: **Over {p['line']}**", inline=True)
    
    # Embed 2: The Volatility Parlay
    risk_embed = DiscordEmbed(title="🎲 The Volatility Slip (High Variance)", color="e74c3c")
    for p in risky:
        risk_embed.add_embed_field(name=p['player'], value=f"Points: **Under {p['line']}**", inline=True)

    webhook.add_embed(safe_embed)
    webhook.add_embed(risk_embed)
    webhook.execute()

if __name__ == "__main__":
    data = get_nba_props()
    if data:
        safe_slip, risky_slip = build_parlays(data)
        send_parlays_to_discord(safe_slip, risky_slip)
