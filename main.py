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
    # 2. For each game, specifically ask for 'player_points'
    for e in events[:5]: # Let's check the first 5 games
        eid = e['id']
        # IMPORTANT: PrizePicks/Underdog are often under the 'us2' or 'us' regions
        prop_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {
            'apiKey': api_key,
            'regions': 'us,us2', 
            'markets': 'player_points',
            'oddsFormat': 'american'
        }
        
        resp = requests.get(prop_url, params=params).json()
        
        # Look specifically for PrizePicks or Underdog in the results
        for book in resp.get('bookmakers', []):
            if book['key'] in ['prizepicks', 'underdog', 'draftkings']:
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
    headers = {"Authorization": os.getenv("BDL_API_KEY", "")}
    try:
        p = requests.get(f"https://api.balldontlie.io/v1/players?search={name}", headers=headers).json()
        p_id = p['data'][0]['id']
        s = requests.get(f"https://api.balldontlie.io/v1/stats?player_ids[]={p_id}&seasons[]=2025&per_page=5", headers=headers).json()
        return [g['pts'] for g in s.get('data', [])]
    except:
        return None

def main():
    players = get_live_props()
    if not players:
        print("Still 0? Check if your API plan supports 'us2' region or 'player_props' endpoint.")
        return

    webhook = DiscordWebhook(url=os.getenv("DISCORD_WEBHOOK"))
    for p in players[:10]:
        last_5 = get_stats(p['name'])
        if last_5:
            embed = DiscordEmbed(title=f"📊 Scouting: {p['name']}", color="E74C3C")
            embed.add_embed_field(name=f"Current {p['book']} Line", value=f"**{p['line']} PTS**")
            embed.add_embed_field(name="Last 5 Games", value=f"`{last_5}`")
            webhook.add_embed(embed)
            if len(webhook.get_embeds()) >= 3:
                webhook.execute()
                webhook = DiscordWebhook(url=os.getenv("DISCORD_WEBHOOK"))
        time.sleep(12) # Stay under BallDontLie's 5 requests/min limit

if __name__ == "__main__":
    main()
