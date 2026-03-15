import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_market_lines():
    # Get your FREE key at https://the-odds-api.com/
    API_KEY = os.getenv("THE_ODDS_API_KEY") 
    if not API_KEY:
        print("❌ Error: THE_ODDS_API_KEY is missing!")
        return []

    # This pulls NBA player points props
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
    params = {
        'apiKey': API_KEY,
        'regions': 'us',
        'markets': 'h2h,totals', # Pulling game lines for simplicity first
        'oddsFormat': 'american'
    }
    
    try:
        print("🎯 Fetching Vegas Market Lines...")
        response = requests.get(url, params=params)
        response.raise_for_status()
        return response.json() # This returns a LIST of games
    except Exception as e:
        print(f"❌ API Call Failed: {e}")
        return []

def alert_discord(games):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not games:
        print("⚠️ No data to send or Webhook missing.")
        return

    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title="🏀 NBA Vegas Market Watch", color="00ff00")

    # FIX: We slice the LIST of games, not the dictionary.
    for game in games[:10]: 
        home = game['home_team']
        away = game['away_team']
        
        # Extracting the Over/Under if available
        total = "N/A"
        for book in game.get('bookmakers', []):
            if book['key'] == 'draftkings': # Focus on DraftKings lines
                for market in book.get('markets', []):
                    if market['key'] == 'totals':
                        total = market['outcomes'][0].get('point', 'N/A')

        embed.add_embed_field(
            name=f"{away} @ {home}",
            value=f"Vegas Game Total: **{total}**",
            inline=True
        )
    
    webhook.add_embed(embed)
    webhook.execute()
    print("🚀 Sent data to Discord!")

if __name__ == "__main__":
    data = get_market_lines()
    alert_discord(data)
