import requests
from bs4 import BeautifulSoup
import time
import re
import logging

# ================= LOGGING SETUP =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# ================= CONFIGURATION =================
PRODUCT_URL = "https://shop.weverse.io/en/shop/USD/artists/2/sales/65102"
KNOWN_SIZES = ["M", "L", "XL", "XXL"]
CHECK_INTERVAL = 300  # 5 minutes (avoid rate limits)

# Discord Webhook URL
DISCORD_WEBHOOK = "https://discord.com/api/webhooks/1530629908290605126/_s41YhRHLncmwGa633DbKUBkYhL4tvOFJfzTOjQGdmfvd-cP5iJV1sRhxntXSTOgV32N"

# ================= DISCORD ALERT FUNCTION =================
def send_discord_alert(message):
    """Send alert to Discord channel via webhook"""
    try:
        data = {"content": f"🚨 {message}"}
        response = requests.post(DISCORD_WEBHOOK, json=data, timeout=10)
        
        if response.status_code == 429:
            # Rate limited - wait and retry
            retry_after = int(response.headers.get('Retry-After', 5))
            logging.warning(f"Rate limited! Waiting {retry_after} seconds...")
            time.sleep(retry_after)
            response = requests.post(DISCORD_WEBHOOK, json=data, timeout=10)
        
        response.raise_for_status()
        logging.info(f"✅ Discord alert sent: {message}")
    except Exception as e:
        logging.error(f"❌ Failed to send Discord alert: {e}")

# ================= MAIN CHECK FUNCTION =================
def check_product():
    """Check product page for stock and size changes"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
        
        # PythonAnywhere-specific: Don't use proxies
        response = requests.get(
            PRODUCT_URL, 
            headers=headers, 
            timeout=30,
            verify=True
        )
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for sold out
        sold_out_text = soup.find(string=re.compile("SOLD OUT|품절|OUT OF STOCK", re.I))
        is_sold_out = sold_out_text is not None
        
        # Check for sizes (simplified for PythonAnywhere)
        size_patterns = ['M', 'L', 'XL', 'XXL']
        current_sizes = []
        
        # Look for size text in the page
        page_text = soup.get_text()
        for size in size_patterns:
            if size in page_text:
                current_sizes.append(size)
        
        # Find new sizes
        new_sizes = [size for size in current_sizes if size not in KNOWN_SIZES]
        
        return {
            'is_sold_out': is_sold_out,
            'new_sizes': new_sizes,
            'all_sizes': current_sizes
        }
        
    except requests.exceptions.RequestException as e:
        logging.error(f"Network error: {e}")
        return None
    except Exception as e:
        logging.error(f"Error parsing page: {e}")
        return None

# ================= SINGLE CHECK VERSION (for scheduled tasks) =================
def run_single_check():
    """Run one check and exit - for PythonAnywhere scheduled tasks"""
    logging.info("Starting single check...")
    
    result = check_product()
    
    if result is None:
        logging.error("Check failed")
        return
    
    logging.info(f"Status: {'SOLD OUT' if result['is_sold_out'] else 'IN STOCK'}")
    logging.info(f"Sizes found: {', '.join(result['all_sizes']) if result['all_sizes'] else 'None'}")
    
    # Send alerts if there are changes
    if not result['is_sold_out']:
        send_discord_alert(f"🔥 RESTOCKED! {PRODUCT_URL}")
    
    if result['new_sizes']:
        send_discord_alert(f"📏 NEW SIZES: {', '.join(result['new_sizes'])}")

# ================= CONTINUOUS MONITORING VERSION =================
def run_continuous():
    """Run continuous monitoring - for always-on tasks"""
    logging.info("Starting continuous monitoring...")
    send_discord_alert("🟢 Monitoring started!")
    
    check_count = 0
    last_status = None
    
    while True:
        check_count += 1
        logging.info(f"Check #{check_count}")
        
        result = check_product()
        
        if result is None:
            logging.warning("Check failed. Will retry...")
            time.sleep(CHECK_INTERVAL)
            continue
        
        current_status = {
            'sold_out': result['is_sold_out'],
            'sizes': tuple(sorted(result['all_sizes']))
        }
        
        # Only send alerts if status changed
        if last_status is None:
            last_status = current_status
        elif current_status != last_status:
            if not result['is_sold_out']:
                send_discord_alert(f"🔥 RESTOCKED! {PRODUCT_URL}")
            
            if result['new_sizes']:
                send_discord_alert(f"📏 NEW SIZES: {', '.join(result['new_sizes'])}")
            
            last_status = current_status
        
        logging.info(f"Sleeping {CHECK_INTERVAL} seconds...")
        time.sleep(CHECK_INTERVAL)

# ================= MAIN =================
if __name__ == "__main__":
    # Choose which mode to run
    # For scheduled tasks on PythonAnywhere, use run_single_check()
    # For always-on tasks, use run_continuous()
    run_single_check()  # Change to run_continuous() if you have always-on