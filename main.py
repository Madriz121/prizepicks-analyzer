import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_market_lines():
    API_KEY = os.getenv("THE_ODDS_API_KEY")
    # Fetching NBA Player Points from DraftKings/FanDuel
    url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    params = {
        'apiKey': API_KEY,
        'regions': 'us',
        'markets': 'player_points', # You can change this to rebounds, assists, etc.
        'oddsFormat': 'decimal'
    }
    
    print("🎯 Fetching Vegas Market Lines...")
    response = requests.get(url, params=params)
    return response.json()

def alert_discord(data):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)
    
    embed = DiscordEmbed(title="📊 Vegas Market Projections (NBA)", color="00ff00")
    
    # Logic: List the first 5 games and their main player props
    for game in data[:5]:
        home = game['home_team']
        away = game['away_team']
        embed.add_embed_field(name=f"🏀 {away} @ {home}", value="Check Props Below", inline=False)
        
    webhook.add_embed(embed)
    webhook.execute()
    print("🚀 Sent Vegas data to Discord!")

if __name__ == "__main__":
    market_data = get_market_lines()
    alert_discord(market_data)
