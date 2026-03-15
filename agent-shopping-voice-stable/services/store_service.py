"""
Store Selection Service
Logic for finding and selecting stores, scraping Bringo
"""
import logging
import json
import time
from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

from database import db_adapter as db
from config.settings import settings

logger = logging.getLogger(__name__)

class StoreService:
    @staticmethod
    def scrape_stores_at_address(address: str) -> Dict[str, Any]:
        """
        Scrape Bringo website for stores at address
        
        Args:
            address: Full address (e.g. "Strada Fetești 52, București")
        
        Returns:
            Dict with stores found
        """
        logger.info(f"🔍 Scraping stores for: {address}")
        
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        driver = None
        stores = []
        
        try:
            driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=options
            )
            
            driver.get(f"{settings.BRINGO_BASE_URL}/ro/stores-list")
            wait = WebDriverWait(driver, 15)
            
            # Reject cookies
            try:
                cookie_btn = wait.until(EC.element_to_be_clickable((By.ID, "onetrust-reject-all-handler")))
                cookie_btn.click()
                time.sleep(1)
            except Exception:
                pass
            
            # Type address
            try:
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
                    except Exception:
                        continue
            except Exception as e:
                logger.error(f"Address input failed: {e}")
                raise
            
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
                    url = f"{settings.BRINGO_BASE_URL}{link}" if link.startswith('/') else link
                    
                    store_div = elem.find(lambda tag: 'store-div' in tag.get('class', []))
                    status = 'Closed' if store_div and 'close-store' in store_div.get('class', []) else 'Open'
                    
                    schedule = {}
                    for day in elem.find_all('div', class_='store-program-day'):
                        day_name = day.find('div', class_='store-program-week-day').text.strip()
                        hours = day.text.replace(day_name, '').strip()
                        schedule[day_name] = hours
                    
                    if schedule:  # Only add stores with schedules
                        # Extract store_id from URL
                        store_id = url.split('/')[-1] if url else None
                        
                        if store_id:
                            # Save to SQLite
                            db.save_store(
                                store_id=store_id,
                                store_name=name,
                                category=category,
                                url=url,
                                status=status,
                                schedule=schedule,
                                address=address
                            )
                        
                        stores.append({
                            'store_id': store_id,
                            'name': name,
                            'category': category,
                            'url': url,
                            'status': status,
                            'schedule': schedule
                        })
                except Exception:
                    continue
                    
        except Exception as e:
            logger.error(f"❌ Scraping failed: {e}")
            return {"status": "error", "message": str(e)}
        finally:
            if driver:
                driver.quit()
        
        logger.info(f"✅ Found {len(stores)} stores, saved to SQLite")
        
        return {
            "status": "success",
            "address": address,
            "stores_count": len(stores),
            "stores": stores
        }

    @staticmethod
    def get_configured_store() -> Dict[str, Any]:
        """Get the configured store info"""
        store_id = settings.BRINGO_STORE
        
        # Try to get details from DB
        store = db.get_store_by_id(store_id)
        if store:
            return {
                "status": "success",
                "store_id": store['store_id'],
                "name": store['store_name'],
                "category": store['category'],
                "url": store['url'],
                "status": store['status'],
                "schedule": json.loads(store['schedule']) if isinstance(store['schedule'], str) else store['schedule']
            }
        else:
             return {
                "status": "success",
                "store_id": store_id,
                "message": "Store configured but details not in database"
            }
