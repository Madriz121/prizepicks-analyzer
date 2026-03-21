import os
import requests
import time
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_live_props():
    api_key = os.getenv("THE_ODDS_API_KEY")
    # 1. Get the list of IDs for today's games
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events = requests.get(url, params={'apiKey': api_key}).json()
    
    found_players = []
    # Check games for props
    for e in events[:5]: 
        eid = e['id']
        prop_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {
            'apiKey': api_key,
            'regions': 'us_dfs', # CHANGED: PrizePicks/Underdog are in 'us_dfs'
            'markets': 'player_points',
            'oddsFormat': 'american'
        }
        
        resp = requests.get(prop_url, params=params).json()
        
        for book in resp.get('bookmakers', []):
            # Bookmaker keys are lowercase: 'prizepicks', 'underdog'
            if book['key'] in ['prizepicks', 'underdog']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        found_players.append({
                            'name': opt['description'],
                            'line': float(opt['point']),
                            'book': book['title']
                        })
        time.sleep(1)
    return found_players

def get_stats(name):
    """Fetches the last 5 games raw scores."""
    # Use your BDL_API_KEY from your GitHub Secrets
    headers = {"Authorization": os.getenv("BDL_API_KEY", "")}
    try:
        # BallDontLie uses '2025' to represent the 2025-26 Season
        p = requests.get(f"https://api.balldontlie.io/v1/players?search={name}", headers=headers).json()
        p_id = p['data'][0]['id']
        s = requests.get(f"https://api.balldontlie.io/v1/stats?player_ids[]={p_id}&seasons[]=2025&per_page=5", headers=headers).json()
        return [g['pts'] for g in s.get('data', [])]
    except:
        return None

def main():
    players = get_live_props()
    print(f"✅ Found {len(players)} lines in us_dfs region.") # Debug print

    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)

    for p in players[:10]:
        last_5 = get_stats(p['name'])
        if last_5:
            embed = DiscordEmbed(title=f"🏀 Scouting: {p['name']}", color="E74C3C")
            embed.add_embed_field(name=f"{p['book']} Line", value=f"**{p['line']} PTS**", inline=True)
            embed.add_embed_field(name="Last 5 Games", value=f"`{last_5}`", inline=True)
            webhook.add_embed(embed)
            
            # Execute every 3 players to avoid Discord character limits
            if len(webhook.get_embeds()) >= 3:
                webhook.execute()
                webhook = DiscordWebhook(url=webhook_url)
        
        # MUST STAY: 12s sleep to avoid BallDontLie 429 errors (Rate Limiting)
        time.sleep(12) 

if __name__ == "__main__":
    main()
