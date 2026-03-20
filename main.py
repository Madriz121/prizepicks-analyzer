import os
import requests
import time
import random
from discord_webhook import DiscordWebhook, DiscordEmbed
from nba_api.stats.static import players

def get_nba_data():
    api_key = os.getenv("THE_ODDS_API_KEY")
    events_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events_resp = requests.get(events_url, params={'apiKey': api_key})
    if events_resp.status_code != 200: return []

    events = events_resp.json()
    all_props = []
    # Reduced to 5 games to stay under the radar
    for e in events[:5]:
        eid = e['id']
        props_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'player_points', 'oddsFormat': 'american'}
        resp = requests.get(props_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            data.update({'home_team': e['home_team'], 'away_team': e['away_team']})
            all_props.append(data)
        time.sleep(1.5) 
    return all_props

def fetch_from_balldontlie(player_name):
    """Fallback if NBA.com blocks us."""
    try:
        # Search for player
        search_r = requests.get(f"https://api.balldontlie.io/v1/players?search={player_name}", timeout=10)
        p_data = search_r.json().get('data')
        if not p_data: return None
        p_id = p_data[0]['id']

        # Get stats (2025 season)
        stats_r = requests.get(f"https://api.balldontlie.io/v1/stats?player_ids[]={p_id}&seasons[]=2025&per_page=5", timeout=10)
        games = stats_r.json().get('data', [])
        if not games: return None
        
        pts = [g['pts'] for g in games]
        return round(sum(pts) / len(pts), 1)
    except:
        return None

def get_last_5_pts_avg(player_name):
    """Main fetch with Anti-Bot protection."""
    try:
        search = players.find_players_by_full_name(player_name)
        if not search: return None
        p_id = search[0]['id']

        # Rotate headers to look human
        headers = {
            'Host': 'stats.nba.com',
            'User-Agent': random.choice([
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            ]),
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.nba.com/',
            'Connection': 'keep-alive'
        }

        # URL for the direct JSON endpoint (more reliable than the library wrapper)
        url = f"https://stats.nba.com/stats/playergamelog?PlayerID={p_id}&Season=2025-26&SeasonType=Regular Season"
        
        # STRICT 10s TIMEOUT - prevents the "Stuck" issue
        resp = requests.get(url, headers=headers, timeout=10)
        
        if resp.status_code == 200:
            rows = resp.json()['resultSets'][0]['rowSet']
            pts = [row[24] for row in rows[:5]] # 24 is the PTS index
            return round(sum(pts)/len(pts), 1)
        else:
            return fetch_from_balldontlie(player_name)
    except:
        return fetch_from_balldontlie(player_name)

def build_slips(data):
    pool = []
    print("🏀 Scanning for Point Discrepancies...")
    for game in data:
        for book in game.get('bookmakers', []):
            if book['key'] in ['draftkings', 'prizepicks']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        name, line = opt['description'], float(opt['point'])
                        avg = get_last_5_pts_avg(name)
                        
                        if avg and abs(avg - line) >= 2.0:
                            pool.append({'name': name, 'line': line, 'avg': avg, 'diff': round(avg - line, 1), 'pick': 'MORE' if avg > line else 'LESS'})
                        time.sleep(random.uniform(2, 4)) # Jittered delay to bypass bots

    # Filter and sort by highest confidence (biggest diff)
    pool.sort(key=lambda x: abs(x['diff']), reverse=True)
    
    slips = []
    used = set()
    for size in [3, 2]: # Prioritize smaller, safer slips
        current = []
        for p in pool:
            if p['name'] not in used and len(current) < size:
                current.append(p)
                used.add(p['name'])
        if len(current) == size: slips.append(current)
    return slips

def alert_discord(slips):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not slips: return
    webhook = DiscordWebhook(url=webhook_url)
    for i, slip in enumerate(slips[:3]):
        embed = DiscordEmbed(title=f"🔥 Points Trend Slip #{i+1}", color="E74C3C")
        for p in slip:
            embed.add_embed_field(name=f"{p['name']}", value=f"**{p['pick']} {p['line']}** (Avg: {p['avg']})", inline=True)
        webhook.add_embed(embed)
        webhook.execute()
        webhook = DiscordWebhook(url=webhook_url)

if __name__ == "__main__":
    raw = get_nba_data()
    final_slips = build_slips(raw)
    alert_discord(final_slips)
