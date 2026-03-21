import os
import requests
import time
import random
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_today_lines():
    """Fetches the current Point lines for today's NBA games."""
    api_key = os.getenv("THE_ODDS_API_KEY")
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    resp = requests.get(url, params={'apiKey': api_key})
    if resp.status_code != 200: return []

    all_lines = []
    events = resp.json()
    for e in events[:8]: # Check the first 8 games of the day
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
                            all_lines.append({
                                'name': opt['description'],
                                'line': float(opt['point']),
                                'team': e['home_team'] if opt['description'] in str(e['home_team']) else e['away_team']
                            })
        time.sleep(1) # Small delay to be nice to The-Odds-API
    return all_lines

def get_historical_stats(player_name):
    """Pulls last 10 games and calculates L5 and L10 averages."""
    headers = {"Authorization": os.getenv("BDL_API_KEY", "")}
    try:
        # Search Player
        p_search = requests.get(f"https://api.balldontlie.io/v1/players?search={player_name}", headers=headers, timeout=10)
        p_id = p_search.json()['data'][0]['id']

        # Get Stats (2025-26 season is '2025' in BDL)
        s_url = f"https://api.balldontlie.io/v1/stats?player_ids[]={p_id}&seasons[]=2025&per_page=10"
        s_resp = requests.get(s_url, headers=headers, timeout=10)
        games = s_resp.json().get('data', [])
        
        if not games: return None
        pts = [g['pts'] for g in games]
        
        return {
            'avg_5': round(sum(pts[:5]) / 5, 1) if len(pts) >= 5 else None,
            'avg_10': round(sum(pts) / len(pts), 1),
            'last_5_raw': pts[:5]
        }
    except:
        return None

def run_scouting_report():
    players_to_check = get_today_lines()
    flags = []

    print(f"🔎 Scouting {len(players_to_check)} players...")
    for p in players_to_check:
        stats = get_historical_stats(p['name'])
        if not stats or not stats['avg_5']: continue

        # FLAG LOGIC: If L5 average is 3+ points away from the current line
        diff = stats['avg_5'] - p['line']
        if abs(diff) >= 3.0:
            p.update(stats)
            p['diff'] = round(diff, 1)
            flags.append(p)
        
        # Respect BDL Free Tier (5 requests/min)
        time.sleep(12.5) 

    send_scouting_discord(flags)

def send_scouting_discord(flags):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not flags: return
    
    webhook = DiscordWebhook(url=webhook_url)
    embed = DiscordEmbed(title="🏀 Player Prop Scouting Report", color="3498DB")
    
    for p in flags[:10]: # Send the top 10 most interesting flags
        trend = "🔥 HOT" if p['diff'] > 0 else "❄️ COLD"
        embed.add_embed_field(
            name=f"{p['name']} ({p['team']}) - Line: {p['line']}",
            value=f"**Trend:** {trend} (Diff: {p['diff']})\n**L5 Avg:** {p['avg_5']} | **L10 Avg:** {p['avg_10']}\n**Recent:** {p['last_5_raw']}",
            inline=False
        )
    
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    run_scouting_report()
