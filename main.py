import time
import json
import os
import undetected_chromedriver as uc
from discord_webhook import DiscordWebhook, DiscordEmbed

class PrizePicksScraper:
    def __init__(self):
        self.url = "https://api.prizepicks.com/projections?league_id=7"
        self.webhook_url = os.getenv("DISCORD_WEBHOOK")
        
    def get_driver(self):
        options = uc.ChromeOptions()
        options.add_argument("--headless")
        # Mandatory flags for GitHub Actions / Linux environments
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        
        # use_subprocess=True is the fix for SessionNotCreatedException
        driver = uc.Chrome(options=options, use_subprocess=True)
        return driver

    def fetch_data(self):
        driver = self.get_driver()
        print("🌐 Opening PrizePicks via Headless Chrome...")
        try:
            driver.get(self.url)
            time.sleep(10) # Give Cloudflare extra time to resolve
            
            raw_content = driver.find_element("tag name", "body").text
            data = json.loads(raw_content)
            print("✅ Data successfully captured.")
            return data
        except Exception as e:
            print(f"❌ Extraction failed: {e}")
            return None
        finally:
            driver.quit()

    def parse_projections(self, data):
        if not data or 'included' not in data: 
            return []
        
        players = {i['id']: i['attributes']['name'] for i in data['included'] if i['type'] == 'new_player'}
        stats = {i['id']: i['attributes']['display_name'] for i in data['included'] if i['type'] == 'stat_type'}
        
        refined_list = []
        for item in data['data']:
            try:
                attr = item['attributes']
                rel = item['relationships']
                player_id = rel['new_player']['data']['id']
                stat_id = rel['stat_type']['data']['id']
                
                refined_list.append({
                    "player": players.get(player_id, "Unknown"),
                    "stat": stats.get(stat_id, "Stat"),
                    "line": attr['line_score'],
                    "is_promo": attr.get('is_promo', False)
                })
            except KeyError:
                continue
        return refined_list

    def send_to_discord(self, plays):
        if not self.webhook_url or not plays:
            print("⚠️ No plays found or Webhook missing.")
            return
        
        webhook = DiscordWebhook(url=self.webhook_url)
        embed = DiscordEmbed(title="🚀 PrizePicks Board Update", color="00ff00")
        
        # Focus on Promos first, then top 5 lines
        for p in plays[:10]:
            label = "⭐ PROMO" if p['is_promo'] else "📊 Standard"
            embed.add_embed_field(
                name=f"{p['player']} - {p['stat']}",
                value=f"Line: **{p['line']}** | {label}",
                inline=False
            )
        
        webhook.add_embed(embed)
        webhook.execute()
        print("📨 Sent to Discord!")

if __name__ == "__main__":
    scraper = PrizePicksScraper()
    raw_data = scraper.fetch_data()
    parsed_plays = scraper.parse_projections(raw_data)
    scraper.send_to_discord(parsed_plays)
