import os
import requests
import time
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_today_prop_lines():
    """Fetches today's player point lines (Step 1)."""
    api_key = os.getenv("THE_ODDS_API_KEY")
    # Get active NBA games for March 21, 2026
    url = "https://api.the-odds-api.com/v4/sports/basketball_nba/events"
    events = requests.get(url, params={'apiKey': api_key}).json()
    
    report_data = []
    # Check lines for the first 5 games (to avoid hitting API limits)
    for e in events[:5]:
        eid = e['id']
        prop_url = f"https://api.the-odds-api.com/v4/sports/basketball_nba/events/{eid}/odds"
        params = {'apiKey': api_key, 'regions': 'us', 'markets': 'player_points'}
        props = requests.get(prop_url, params=params).json()
        
        for book in props.get('bookmakers', []):
            if book['key'] in ['draftkings', 'prizepicks']:
                for market in book.get('markets', []):
                    for opt in market['outcomes']:
                        report_data.append({
                            'name': opt['description'],
                            'line': float(opt['point']),
                            'matchup': f"{e['away_team']} vs {e['home_team']}"
                        })
        time.sleep(1) # Rate limit protection
    return report_data

def get_last_5_stats(player_name):
    """Fetches actual points from the last 5 games (Step 2)."""
    headers = {"Authorization": os.getenv("BDL_API_KEY", "")}
    try:
        # Search for player to get BDL ID
        p_search = requests.get(f"https://api.balldontlie.io/v1/players?search={player_name}", headers=headers).json()
        p_id = p_search['data'][0]['id']

        # Get stats for the 2025-26 season
        s_url = f"https://api.balldontlie.io/v1/stats?player_ids[]={p_id}&seasons[]=2025&per_page=5"
        stats_resp = requests.get(s_url, headers=headers).json()
        
        # Return only the points as a list
        return [g['pts'] for g in stats_resp.get('data', [])]
    except:
        return None

def run_report():
    print("📋 Generating Scouting Report for March 21, 2026...")
    players = get_today_prop_lines()
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)

    # We only process the top 12 players to avoid Discord embed limits
    for p in players[:12]:
        last_5 = get_last_5_stats(p['name'])
        
        if last_5:
            avg_5 = round(sum(last_5) / len(last_5), 1)
            # Create a clean scouting embed
            embed = DiscordEmbed(title=f"🏀 {p['name']} Scouting Report", color="3498DB")
            embed.add_embed_field(name="Today's Line", value=f"**{p['line']} Points**", inline=True)
            embed.add_embed_field(name="Last 5 Games (Raw)", value=f"`{last_5}`", inline=True)
            embed.add_embed_field(name="L5 Average", value=f"**{avg_5}**", inline=True)
            embed.set_footer(text=f"Matchup: {p['matchup']}")
            
            webhook.add_embed(embed)
            
            # Send in batches of 3 to avoid rate limits
            if len(webhook.get_embeds()) >= 3:
                webhook.execute()
                webhook = DiscordWebhook(url=webhook_url)
                time.sleep(2)
        
        # Respect BallDontLie Free Tier (5 requests/min)
        time.sleep(12) 

if __name__ == "__main__":
    run_report()
