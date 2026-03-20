import os
import requests
import time
import random
from discord_webhook import DiscordWebhook, DiscordEmbed
# New Import for Stats
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players

def get_nba_data():
    api_key = os.getenv("THE_ODDS_API_KEY")
    events_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events_resp = requests.get(events_url, params={'apiKey': api_key})
    if events_resp.status_code != 200: return []

    events = events_resp.json()
    all_props = []
    for e in events[:10]: # Limited to 10 games to avoid API timeouts
        eid = e['id']
        props_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'player_points', 'oddsFormat': 'american'}
        resp = requests.get(props_url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            data['home_team'] = e['home_team']
            data['away_team'] = e['away_team']
            all_props.append(data)
        time.sleep(0.6) # Standard rate limiting
    return all_props

def get_last_5_avg(player_name):
    """Fetches the PPG over the last 5 games using nba_api."""
    try:
        search = players.find_players_by_full_name(player_name)
        if not search: return None
        p_id = search[0]['id']
        
        # Fetch logs (last_n_games_stats is key here)
        log = playergamelog.PlayerGameLog(player_id=p_id, season='2023-24') # Update season as needed
        df = log.get_data_frames()[0]
        
        if df.empty: return None
        last_5 = df.head(5)
        return round(last_5['PTS'].mean(), 1)
    except Exception as e:
        print(f"Error fetching stats for {player_name}: {e}")
        return None

def calculate_success_rate(entry):
    base_hit_rate = 0.542 
    total_prob = 1.0
    for i, p in enumerate(entry):
        # Higher edge if the Trend Gap is massive (> 4 points)
        trend_edge = 0.04 if abs(p.get('trend_diff', 0)) > 4 else 0.02
        total_prob *= (base_hit_rate + trend_edge)
    
    strength = (total_prob / (0.542**len(entry))) * 55
    return round(min(strength, 99.1), 1)

def build_trend_slips(data):
    player_pool = []
    
    print("📊 Analyzing Player Trends (Last 5 Games)...")
    for game in data:
        for book in game.get('bookmakers', []):
            # Focus on PrizePicks or DraftKings lines
            if book['key'] in ['draftkings', 'prizepicks']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        p_name = opt['description']
                        line = float(opt['point'])
                        
                        avg_5 = get_last_5_avg(p_name)
                        if avg_5 is None: continue
                        
                        diff = avg_5 - line
                        
                        # LOGIC: Difference must be at least 2
                        if abs(diff) >= 2:
                            pick = 'MORE' if diff > 0 else 'LESS'
                            player_pool.append({
                                'name': p_name,
                                'line': line,
                                'avg_5': avg_5,
                                'trend_diff': round(diff, 1),
                                'pick': pick,
                                'team': game['home_team'] if p_name in str(game.get('home_team')) else game['away_team']
                            })
                        # Slow down to avoid NBA.com blocking your IP
                        time.sleep(0.8)

    # Sort pool by the biggest discrepancies
    player_pool.sort(key=lambda x: abs(x['trend_diff']), reverse=True)
    
    final_slips = []
    used_players = set()

    # Build 4-man and 3-man slips for safety
    for target_size in [4, 3]:
        while len(final_slips) < 5: # Generate up to 5 high-quality slips
            current_slip = []
            for p in player_pool:
                if p['name'] not in used_players and len(current_slip) < target_size:
                    current_slip.append(p)
                    used_players.add(p['name'])
            
            if len(current_slip) == target_size:
                final_slips.append(current_slip)
            else:
                break
                
    return final_slips

def alert_discord(entries):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    if not webhook_url or not entries: 
        print("⚠️ No trend-based slips found.")
        return
        
    webhook = DiscordWebhook(url=webhook_url)
    for i, entry in enumerate(entries):
        win_rate = calculate_success_rate(entry)
        embed = DiscordEmbed(title=f"📈 Trend Slip #{i+1}", color="3498db")
        embed.set_description(f"**Confidence: {win_rate}%**\n*Strategy: Last 5 Games Avg vs Line (Min Δ2.0)*")
        
        for p in entry:
            icon = "🔥" if p['pick'] == 'MORE' else "❄️"
            embed.add_embed_field(
                name=f"{p['name']} ({p['team']})", 
                value=f"**{p['pick']} {p['line']}** {icon}\nL5 Avg: {p['avg_5']} (Δ{p['trend_diff']})", 
                inline=True
            )
        
        webhook.add_embed(embed)
        webhook.execute()
        webhook = DiscordWebhook(url=webhook_url)
    
    print(f"🚀 Sent {len(entries)} trend-based slips to Discord.")

if __name__ == "__main__":
    raw_data = get_nba_data()
    slips = build_trend_slips(raw_data)
    alert_discord(slips)
