"""
Store selection tools - REAL ACTIONS
Scraping, filtering, data manipulation with SQLite persistence
"""

import logging
import json
import time
from typing import List, Dict, Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from bs4 import BeautifulSoup

# Import shared database
from api.tools.shared import db

logger = logging.getLogger("store_tools")

def scrape_stores_at_address(address: str) -> str:
    """
    REAL ACTION: Scrape Bringo website for stores at address
    """
    logger.info(f"🔍 Scraping stores for: {address}")
    
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--user-agent=Mozilla/5.0")
    options.add_argument("--disable-blink-features=AutomationControlled")
    
    driver = webdriver.Chrome(
        service=ChromeService(ChromeDriverManager().install()),
        options=options
    )
    
    stores = []
    
    try:
        driver.get("https://www.bringo.ro/ro/stores-list")
        wait = WebDriverWait(driver, 15)
        
        # Reject cookies (try/except)
        try:
            cookie_btn = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler")))
            cookie_btn.click()
            time.sleep(1)
        except:
            pass
        
        # Type address
        address_input = wait.until(EC.element_to_be_clickable((By.ID, "address")))
        address_input.clear()
        for char in address:
            address_input.send_keys(char)
            time.sleep(0.05)
        time.sleep(2)
        
        # Select first autocomplete
        address_input.send_keys(Keys.ARROW_DOWN)
        time.sleep(0.5)
        address_input.send_keys(Keys.ENTER)
        time.sleep(2)
        
        # Submit
        for btn_id in ["view_stores", "change-address-location-submit"]:
            try:
                btn = driver.find_element(By.ID, btn_id)
                if btn.is_displayed():
                    driver.execute_script("arguments[0].click();", btn)
                    break
            except:
                continue
        
        # Wait for results
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#stores-list .box-store")))
        time.sleep(3)
        
        # Parse stores
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        store_elements = soup.find_all('div', class_='box-store')
        
        for elem in store_elements:
            try:
                name = elem.find('h4', class_='store-title').text.strip()
                category = elem.find('h6', class_='store-subtitle').text.strip()
                link = elem.find('a', class_='section')['href']
                url = f"https://bringo.ro{link}" if link.startswith('/') else link
                
                store_div = elem.find(lambda tag: 'store-div' in tag.get('class', []))
                status = 'Closed' if store_div and 'close-store' in store_div.get('class', []) else 'Open'
                
                schedule = {}
                for day in elem.find_all('div', class_='store-program-day'):
                    day_name = day.find('div', class_='store-program-week-day').text.strip()
                    hours = day.text.replace(day_name, '').strip()
                    schedule[day_name] = hours
                
                if schedule:
                    store_id = url.split('/')[-1] if url else None
                    if store_id:
                        db.save_store(store_id, name, category, url, status, schedule, address)
                    
                    stores.append({
                        'store_id': store_id,
                        'name': name,
                        'category': category,
                        'url': url,
                        'status': status,
                        'schedule': schedule
                    })
            except:
                continue
                
    except Exception as e:
        logger.error(f"❌ Scraping failed: {e}")
        return json.dumps({"status": "error", "message": str(e)})
    finally:
        driver.quit()
    
    logger.info(f"✅ Found {len(stores)} stores, saved to SQLite")
    
    return json.dumps({
        "status": "success",
        "address": address,
        "stores_count": len(stores),
        "stores": stores
    }, ensure_ascii=False, indent=2)

def filter_stores_by_category(stores_json: str, categories: List[str]) -> str:
    """REAL ACTION: Filter stores to only specified categories"""
    try:
        data = json.loads(stores_json)
        if data.get("status") != "success": return stores_json
        
        all_stores = data.get("stores", [])
        filtered = [s for s in all_stores if s['category'] in categories and s['status'] == 'Open']
        
        return json.dumps({
            "status": "success",
            "categories": categories,
            "stores_count": len(filtered),
            "stores": filtered
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

def get_stores_from_database(categories: str = "", status: str = "Open") -> str:
    """REAL ACTION: Get stores from SQLite database"""
    try:
        cat_list = json.loads(categories) if categories and categories != "" else None
        
        if cat_list:
            stores = db.get_stores_by_category(cat_list, status)
        else:
            stores = db.get_all_stores()
        
        formatted_stores = [{
            'store_id': s['store_id'],
            'name': s['store_name'],
            'category': s['category'], 
            'url': s['url'],
            'status': s['status'],
            'schedule': s.get('schedule', {})
        } for s in stores]
        
        return json.dumps({
            "status": "success",
            "stores_count": len(formatted_stores),
            "stores": formatted_stores
        }, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})

def get_configured_store() -> str:
    """REAL ACTION: Get the configured store (hardcoded fallback or from DB)"""
    try:
        # Default store for Bringo
        store_id = 'carrefour_park_lake' 
        store = db.get_store_by_id(store_id)
        
        if store:
            return json.dumps({
                "status": "success",
                "store_id": store['store_id'],
                "store_name": store['store_name'],
                "category": store['category'],
                "url": store['url'],
                "status": store['status']
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({
                "status": "success", 
                "store_id": store_id, 
                "message": "Store not in DB, using default"
            })
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
