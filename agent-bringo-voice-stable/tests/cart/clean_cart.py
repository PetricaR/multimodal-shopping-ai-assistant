
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("clean_cart")

load_dotenv()

def setup_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)

def clean_cart_selenium():
    email = os.getenv("BRINGO_EMAIL") or "radan.petrica@yahoo.com"
    password = os.getenv("BRINGO_PASSWORD")
    
    logger.info(f"Checking credentials... Email: {'FOUND' if email else 'MISSING'}, Password: {'FOUND' if password else 'MISSING'}")
    
    if not email or not password:
        logger.error("❌ BRINGO_EMAIL or BRINGO_PASSWORD not set in env.")
        # Attempt to read from config.env manually if needed or exit
        return

    driver = setup_driver()
    try:
        logger.info("🌍 Navigating to Login Page...")
        driver.get("https://www.bringo.ro/ro/login")
        
        # Login
        logger.info("🔑 Logging in...")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "_username")))
        driver.find_element(By.ID, "_username").send_keys(email)
        driver.find_element(By.ID, "_password").send_keys(password)
        
        # Click login button (usually class btn-login)
        login_btn = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_btn.click()
        
        # Wait for redirect or cart icon
        time.sleep(5)
        
        # Go to Cart
        logger.info("🛒 Navigating to Cart Page...")
        driver.get("https://www.bringo.ro/ro/cart/")
        
        time.sleep(3)
        
        if "Nu ai niciun produs" in driver.page_source or "Cosul tau este gol" in driver.page_source:
            logger.info("✅ Cart is already empty.")
            return

        # Try to find remove buttons
        remove_btns = driver.find_elements(By.CSS_SELECTOR, "a.remove-from-cart, button.remove-item, i.fa-trash")
        
        if not remove_btns:
            # Fallback text search
            buttons = driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if "sterge" in btn.text.lower():
                    remove_btns.append(btn)
        
        if remove_btns:
            logger.info(f"Found {len(remove_btns)} items/buttons to remove. Attempting to clear...")
            for btn in remove_btns:
                try:
                    btn.click()
                    time.sleep(1)
                except:
                    pass
            logger.info("✅ Attempted removal.")
            
            # Refresh to check
            driver.refresh()
            time.sleep(2)
            if "Nu ai niciun produs" in driver.page_source:
                logger.info("✅ Cart cleared confirmed.")
            else:
                logger.warning("⚠️ Cart might still have items.")

    except Exception as e:
        logger.error(f"❌ Selenium Error: {e}")
        driver.save_screenshot("clean_cart_error.png")
    finally:
        driver.quit()

if __name__ == "__main__":
    clean_cart_selenium()
