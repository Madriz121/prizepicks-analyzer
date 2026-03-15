import time
import json
import os
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc
from discord_webhook import DiscordWebhook, DiscordEmbed

class PrizePicksScraper:
    def __init__(self):
        self.url = "https://api.prizepicks.com/projections?league_id=7" # NBA
        self.webhook_url = os.getenv("DISCORD_WEBHOOK")
        
    def get_driver(self):
        options = uc.ChromeOptions()
        options.add_argument("--headless") # Run in background
        driver = uc.Chrome(options=options)
        return driver

    def fetch_data(self):
        driver = self.get_driver()
        print("🌐 Opening PrizePicks...")
        try:
            driver.get(self.url)
            time.sleep(5) # Allow Cloudflare to resolve
            
            # Extracting the raw JSON from the pre-tag the browser renders
            raw_content = driver.find_element("tag name", "body").text
            data = json.loads(raw_content)
            return data
        except Exception as e:
            print(f"❌ Extraction failed: {e}")
            return None
        finally:
            driver.quit()

    def parse_projections(self, data):
        if not data: return []
        
        # Build maps for easy lookup
        players = {i['id']: i['attributes']['name'] for i in data['included'] if i['type'] == 'new_player'}
        stats = {i['id']: i['attributes']['display_name'] for i in data['included'] if i['type'] == 'stat_type'}
        
        refined_list = []
        
        for item in data['data']:
            attr = item['attributes']
            rel = item['relationships']
            
            player_id = rel['new_player']['data']['id']
            stat_type_id = rel['stat_type']['data']['id']
            
            # New Logic: Identifying "Discounted" or "Promotional" lines
            is_promo = attr.get('is_promo', False)
            
            refined_list.append({
                "player": players.get(player_id),
                "stat": stats.get(stat_type_id),
                "line": attr['line_score'],
                "is_promo": is_promo,
                "description": attr.get('description', 'NBA')
            })
            
        return refined_list

    def find_best_slips(self, plays):
        # STRATEGY: Prioritize Promos and High-Value Stat Categories
        # In a real-world scenario, you would compare 'plays' against an Odds API here.
        recommended = [p for p in plays if p['is_promo']]
        
        # Logic: If no promos, grab high-volume stats (Points)
        if len(recommended) < 3:
            pts_plays = [p for p in plays if p['stat'] == 'Points'][:5]
            recommended.extend(pts_plays)
            
        return recommended

    def send_to_discord(self, slips):
        if not self.webhook_url: return
        
        webhook = DiscordWebhook(url=self.webhook_url)
        embed = DiscordEmbed(title="🔥 NEW PRIZEPICKS SLIP SEED", color="FF4500")
        
        for s in slips[:10]: # Limit to top 10
            status = "⭐ PROMO" if s['is_promo'] else "📊 Market"
            embed.add_embed_field(
                name=f"{s['player']} ({s['stat']})",
                value=f"Line: **{s['line']}** | Type: {status}",
                inline=False
            )
        
        webhook.add_embed(embed)
        webhook.execute()
        print("🚀 Slip seeds sent to Discord.")

if __name__ == "__main__":
    scraper = PrizePicksScraper()
    raw = scraper.fetch_data()
    all_plays = scraper.parse_projections(raw)
    top_picks = scraper.find_best_slips(all_plays)
    scraper.send_to_discord(top_picks)
