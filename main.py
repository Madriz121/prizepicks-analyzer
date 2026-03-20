import os
import requests
import time
import random
import pandas as pd
from discord_webhook import DiscordWebhook, DiscordEmbed
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players

def get_nba_data():
    api_key = os.getenv("THE_ODDS_API_KEY")
    # Using 2026 current date context for fresh lines
    events_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events_resp = requests.get(events_url, params={'apiKey': api_key})
    if events_resp.status_code != 200: return []

    events = events_resp.json()
    all_props = []
    for e in events[:8]: # Reduced to 8 games to ensure we don't hit NBA rate limits
        eid = e['id']
        props_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        # Specifically targeting player_points market
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'player_points', 'oddsFormat': 'american'}
        resp = requests.get(props_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            data['home_team'] = e['home_team']
            data['away_team'] = e['away_team']
            all_props.append(data)
        time.sleep(1.0) 
    return all_props

def get_last_5_pts_avg(player_name):
    """Fetches PPG over last 5 games for the 2025-26 Season."""
    try:
        search = players.find_players_by_full_name(player_name)
        if not search: return None
        p_id = search[0]['id']
        
        # Headers help prevent 403 Forbidden errors from NBA.com
        custom_headers = {
            'Host': 'stats.nba.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:72.0) Gecko/20100101 Firefox/72.0',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.5',
            'Referer': 'https://stats.nba.com/'
        }

        log = playergamelog.PlayerGameLog(
            player_id=p_id, 
            season='2025-26', 
            headers=custom_headers,
            timeout=30
        )
        df = log.get_data_frames()[0]
        
        if df.empty: return None
        # Return average of the 'PTS' column for top 5 rows
        return round(df.head(5)['PTS'].mean(), 1)
    except Exception as e:
        print(f"⚠️ Stat fetch failed for {player_name}: {e}")
        return None

def build_point_trend_slips(data):
    player_pool = []
    print("🏀 Analyzing Points Trends...")

    for game in data:
        for book in game.get('bookmakers', []):
            if book['key'] in ['draftkings', 'prizepicks', 'fanduel']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        name = opt['description']
                        line = float(opt['point'])
                        
                        avg_5 = get_last_5_pts_avg(name)
                        if avg_5 is None: continue
                        
                        diff = avg_5 - line
                        # YOUR LOGIC: Difference of at least 2 points
                        if abs(diff) >= 2.0:
                            player_pool.append({
                                'name': name,
                                'line': line,
                                'avg_5': avg_5,
                                'diff': round(diff, 1),
                                'pick': 'MORE' if diff > 0 else 'LESS',
                                'team': game['home_team'] if name in str(game.get('home_team')) else game['away_team']
                            })
                        # IMPORTANT: Heavy sleep to respect NBA.com
                        time.sleep(1.5)

    # Prioritize the biggest "Gaps" first
    player_pool.sort(key=lambda x: abs(x['diff']), reverse=True)
    
    # Build slips (strictly 2-4 man for better hit rates)
    final_slips = []
    used = set()
    for size in [3, 2, 4]:
        while len(final_slips) < 5:
            current = []
            for p in player_pool:
                if p['name'] not in used and len(current) < size:
                    current.append(p)
                    used.add(p['name'])
            if len(current) == size:
                final_slips.append(current)
            else: break
    return final_slips

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not entries: return
    
    webhook = DiscordWebhook(url=webhook_url)
    for i, entry in enumerate(entries):
        embed = DiscordEmbed(title=f"🏀 Point Trend Slip #{i+1}", color="FF5733")
        for p in entry:
            icon = "📈" if p['pick'] == 'MORE' else "📉"
            embed.add_embed_field(
                name=f"{p['name']} ({p['team']})",
                value=f"**{p['pick']} {p['line']}** {icon}\nL5 Avg: {p['avg_5']} (Diff: {p['diff']})",
                inline=True
            )
        webhook.add_embed(embed)
        webhook.execute()
        webhook = DiscordWebhook(url=webhook_url)

if __name__ == "__main__":
    raw_data = get_nba_data()
    slips = build_point_trend_slips(raw_data)
    alert_discord(slips)
