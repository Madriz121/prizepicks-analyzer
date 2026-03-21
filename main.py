import os
import requests
import time
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_today_scouting_data():
    api_key = os.getenv("THE_ODDS_API_KEY")
    # Step 1: Get Game IDs
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events = requests.get(url, params={'apiKey': api_key}).json()
    
    if not events:
        print("❌ No NBA games found for today.")
        return []

    all_props = []
    # Step 2: Deep Scan first 5 games for PrizePicks/Underdog
    for e in events[:5]:
        eid = e['id']
        print(f"🔎 Scanning Game: {e['away_team']} @ {e['home_team']}...")
        
        # We check us2 region specifically for PrizePicks/Underdog
        prop_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {
            'apiKey': api_key,
            'regions': 'us,us2', 
            'markets': 'player_points',
            'oddsFormat': 'american'
        }
        
        resp = requests.get(prop_url, params=params).json()
        
        for book in resp.get('bookmakers', []):
            # Check specifically for the books you are seeing lines on
            if book['key'] in ['prizepicks', 'underdog', 'draftkings']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        all_props.append({
                            'name': opt['description'],
                            'line': float(opt['point']),
                            'book': book['title'],
                            'matchup': f"{e['away_team']} @ {e['home_team']}"
                        })
        time.sleep(1) # API Safety
    return all_props

def get_stats(name):
    """Step 3: Get last 5 games raw points (BallDontLie)."""
    headers = {"Authorization": os.getenv("BDL_API_KEY", "")}
    try:
        # Search Player
        p = requests.get(f"https://api.balldontlie.io/v1/players?search={name}", headers=headers, timeout=10).json()
        if not p.get('data'): return None
        p_id = p['data'][0]['id']

        # Get Stats (2025-26 season)
        s = requests.get(f"https://api.balldontlie.io/v1/stats?player_ids[]={p_id}&seasons[]=2025&per_page=5", headers=headers, timeout=10).json()
        return [g['pts'] for g in s.get('data', [])]
    except:
        return None

def main():
    players = get_today_scouting_data()
    print(f"📊 Found {len(players)} total lines across all books.")
    
    if not players:
        print("⚠️ Still 0 players. This means your Odds-API key likely doesn't have 'Player Prop' access enabled.")
        return

    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)

    # Process first 10 players found
    for p in players[:10]:
        print(f"📈 Fetching history for {p['name']}...")
        last_5 = get_stats(p['name'])
        
        if last_5:
            embed = DiscordEmbed(title=f"🏀 Scouting: {p['name']}", color="E74C3C")
            embed.add_embed_field(name=f"{p['book']} Line", value=f"**{p['line']} PTS**", inline=True)
            embed.add_embed_field(name="Last 5 Games", value=f"`{last_5}`", inline=True)
            embed.set_footer(text=f"Game: {p['matchup']}")
            webhook.add_embed(embed)
            
            if len(webhook.get_embeds()) >= 3:
                webhook.execute()
                webhook = DiscordWebhook(url=webhook_url)
                time.sleep(2)
        
        # Rate limit for BallDontLie Free Tier
        time.sleep(12) 

if __name__ == "__main__":
    main()
