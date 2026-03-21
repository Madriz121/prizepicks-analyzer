import os
import requests
import time
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_today_lines():
    """Step 1: Get the current point lines for today's players."""
    api_key = os.getenv("THE_ODDS_API_KEY")
    # Fetching NBA events for today, March 21, 2026
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events = requests.get(url, params={'apiKey': api_key}).json()
    
    if not events:
        print("No NBA games found in the API for today.")
        return []

    scout_list = []
    # Loop through games like Wizards vs Thunder or Pelicans vs Cavaliers
    for e in events[:5]: 
        eid = e['id']
        prop_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        # Specifically requesting the player_points market
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'player_points'}
        p_data = requests.get(prop_url, params=params).json()
        
        for book in p_data.get('bookmakers', []):
            if book['key'] in ['draftkings', 'prizepicks']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        scout_list.append({
                            'name': opt['description'],
                            'line': float(opt['point']),
                            'matchup': f"{e['away_team']} @ {e['home_team']}"
                        })
        time.sleep(1) # Respecting API rate limits
    return scout_list

def get_last_5(player_name):
    """Step 2: Get the raw points from the last 5 games."""
    headers = {"Authorization": os.getenv("BDL_API_KEY", "")}
    try:
        # Searching for the player on BallDontLie (GitHub Action safe)
        p_search = requests.get(f"https://api.balldontlie.io/v1/players?search={player_name}", headers=headers).json()
        if not p_search.get('data'): return None
        p_id = p_search['data'][0]['id']

        # Fetching 2025-26 season stats
        s_url = f"https://api.balldontlie.io/v1/stats?player_ids[]={p_id}&seasons[]=2025&per_page=5"
        stats = requests.get(s_url, headers=headers).json().get('data', [])
        return [g['pts'] for g in stats]
    except:
        return None

def run_scout():
    players = get_today_lines()
    if not players:
        print("⚠️ No lines found. Try running again closer to tip-off (after 2PM EST).")
        return

    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)

    for p in players[:10]: # Sending the first 10 players found
        last_5 = get_last_5(p['name'])
        if last_5:
            embed = DiscordEmbed(title=f"🏀 Scouting: {p['name']}", color="3498DB")
            embed.add_embed_field(name="Current Line", value=f"**{p['line']} PTS**", inline=True)
            embed.add_embed_field(name="Last 5 Games", value=f"`{last_5}`", inline=True)
            embed.set_footer(text=f"Game: {p['matchup']}")
            webhook.add_embed(embed)
            
            # Send in batches to avoid Discord rate limits
            if len(webhook.get_embeds()) >= 3:
                webhook.execute()
                webhook = DiscordWebhook(url=webhook_url)
                time.sleep(2)
        
        # Mandatory 12s delay for BallDontLie Free Tier (5 requests/min)
        time.sleep(12) 

if __name__ == "__main__":
    run_scout()
