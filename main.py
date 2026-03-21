import os
import requests
import time
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_market_lines():
    """Fetches today's player point lines from DraftKings/PrizePicks."""
    api_key = os.getenv("THE_ODDS_API_KEY")
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    resp = requests.get(url, params={'apiKey': api_key})
    
    if resp.status_code != 200: return []
    
    events = resp.json()
    scout_list = []
    
    for e in events[:5]: # Scouting first 5 games to save API credits
        eid = e['id']
        prop_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'player_points'}
        p_resp = requests.get(prop_url, params=params)
        
        if p_resp.status_code == 200:
            data = p_resp.json()
            for book in data.get('bookmakers', []):
                if book['key'] in ['draftkings', 'prizepicks']:
                    for market in book.get('markets', []):
                        for opt in market['outcomes']:
                            scout_list.append({
                                'name': opt['description'],
                                'line': float(opt['point']),
                                'matchup': f"{e['away_team']} @ {e['home_team']}"
                            })
        time.sleep(1)
    return scout_list

def get_player_history(player_name, current_line):
    """Checks last 5 games against TODAY'S line."""
    headers = {"Authorization": os.getenv("BDL_API_KEY", "")}
    try:
        # 1. Get Player ID
        p_search = requests.get(f"https://api.balldontlie.io/v1/players?search={player_name}", headers=headers).json()
        if not p_search['data']: return None
        p_id = p_search['data'][0]['id']

        # 2. Get Last 5 Stats (2025-26 season is '2025')
        s_url = f"https://api.balldontlie.io/v1/stats?player_ids[]={p_id}&seasons[]=2025&per_page=5"
        stats = requests.get(s_url, headers=headers).json().get('data', [])
        
        if not stats: return None
        pts = [g['pts'] for g in stats]
        
        # 3. Calculate 'Hit Rate' vs today's line
        overs = sum(1 for p in pts if p > current_line)
        avg_5 = round(sum(pts) / len(pts), 1)
        
        return {
            'pts_log': pts,
            'avg_5': avg_5,
            'hit_rate': f"{overs}/5 Over",
            'is_consistent': overs >= 4 or overs <= 1 # Flag if 80%+ consistent
        }
    except:
        return None

def run_scout():
    raw_players = get_market_lines()
    interesting_plays = []

    print(f"🔎 Scouting {len(raw_players)} lines...")
    for p in raw_players:
        history = get_player_history(p['name'], p['line'])
        if history and history['is_consistent']:
            p.update(history)
            interesting_plays.append(p)
        
        # Slow down for BallDontLie Free Tier (5 requests/min)
        time.sleep(12)

    send_to_discord(interesting_plays)

def send_to_discord(reports):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not reports: return
    
    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title="📊 Player Prop Consistency Report", color="2ECC71")
    
    for r in reports[:10]: # Top 10 most consistent players
        embed.add_embed_field(
            name=f"{r['name']} - Line: {r['line']}",
            value=f"**Today's Matchup:** {r['matchup']}\n**Hit Rate:** {r['hit_rate']}\n**Last 5 Scores:** {r['pts_log']}\n**L5 Average:** {r['avg_5']}",
            inline=False
        )
    
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    run_scout()
