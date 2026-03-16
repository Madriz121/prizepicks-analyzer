import os
import requests
import time
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_nba_data():
    api_key = os.getenv("THE_ODDS_API_KEY")
    events_url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events_resp = requests.get(events_url, params={'apiKey': api_key})
    
    if events_resp.status_code != 200:
        return []

    events = events_resp.json()
    all_props = []

    # Fetch props for up to 5 games to ensure we have enough for a 6-man slip
    for e in events[:5]:
        eid = e['id']
        props_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'player_points', 'oddsFormat': 'american'}
        resp = requests.get(props_url, params=params)
        if resp.status_code == 200:
            # We store the teams so we can check the '2-team rule'
            data = resp.json()
            data['home_team'] = e['home_team']
            data['away_team'] = e['away_team']
            all_props.append(data)
        time.sleep(0.5)
    
    return all_props

def build_dynamic_slip(data):
    # Lists to store potential picks
    consistency_pool = []
    used_players = set()

    for event in data:
        for book in event.get('bookmakers', []):
            if book['key'] in ['draftkings', 'fanduel']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        player = opt['description']
                        line = float(opt['point'])
                        
                        if player not in used_players:
                            # Strategy: Prioritize high-floor consistency (23+ pts)
                            if line >= 22.5:
                                consistency_pool.append({
                                    'name': player, 
                                    'line': line, 
                                    'team': event['home_team'] if count % 2 == 0 else event['away_team']
                                })
                                used_players.add(player)

    # Determine the slip size based on pool size (Max 6, Min 3)
    pool_size = len(consistency_pool)
    if pool_size >= 6: slip_size = 6
    elif pool_size == 5: slip_size = 5
    elif pool_size == 4: slip_size = 4
    elif pool_size == 3: slip_size = 3
    else: return None, 0 # Not enough players for a valid slip

    return consistency_pool[:slip_size], slip_size

def alert_discord(slip, size):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)

    if not slip:
        print("❌ Not enough unique players found for a slip.")
        return

    color = "00ff00" if size == 6 else "ffff00" # Green for 6, Yellow for others
    embed = DiscordEmbed(title=f"🚀 {size}-Man Flex Slip Generated", color=color)
    
    for p in slip:
        embed.add_embed_field(name=p['name'], value=f"Points: **Over {p['line']}**", inline=True)
    
    embed.set_footer(text="Strategy: Market Consistency | 2+ Teams Included")
    webhook.add_embed(embed)
    webhook.execute()
    print(f"✅ {size}-man slip sent to Discord.")

if __name__ == "__main__":
    raw_data = get_nba_data()
    final_slip, final_size = build_dynamic_slip(raw_data)
    alert_discord(final_slip, final_size)
