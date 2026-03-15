import os
import requests
from discord_webhook import DiscordWebhook, DiscordEmbed

def get_nba_projections():
    url = "https://api.prizepicks.com/projections?league_id=7" # NBA ID
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        return response.json()
    except:
        return None

def build_slips():
    data = get_nba_projections()
    if not data: return

    # Parse players and their lines
    projections = data.get('data', [])
    valid_plays = []

    for p in projections:
        attr = p['attributes']
        # Consistency Logic: 
        # For now, we lean 'Over' if it's a 'Points' prop and 'Under' for 'Rebounds' 
        # (This is a placeholder for your custom logic or secondary API data)
        pick_type = "OVER" if attr['stat_type'] == "Points" else "UNDER"
        
        valid_plays.append({
            "name": attr.get("description", "Unknown Player"),
            "stat": attr['stat_type'],
            "line": attr['line_score'],
            "pick": pick_type
        })

    # Determine Slip Size (6 -> 5 -> 4 -> 3)
    count = len(valid_plays)
    slip_size = 0
    if count >= 6: slip_size = 6
    elif count == 5: slip_size = 5
    elif count == 4: slip_size = 4
    elif count >= 3: slip_size = 3

    if slip_size > 0:
        send_to_discord(valid_plays[:slip_size], slip_size)

def send_to_discord(plays, size):
    webhook_url = os.getenv("DISCORD_WEBHOOK")
    webhook = DiscordWebhook(url=webhook_url)
    
    embed = DiscordEmbed(
        title=f"🔥 New {size}-Man Flex Slip Builder",
        description="Priority: NBA Consistency Model",
        color="ffcc00"
    )

    for i, play in enumerate(plays, 1):
        emoji = "📈" if play['pick'] == "OVER" else "📉"
        embed.add_embed_field(
            name=f"Pick #{i}: {play['name']}",
            value=f"{play['stat']}: **{play['line']}**\nSelection: **{emoji} {play['pick']}**",
            inline=True
        )

    embed.set_footer(text="Automated by PrizePicks-Repo")
    webhook.add_embed(embed)
    webhook.execute()

if __name__ == "__main__":
    build_slips()
