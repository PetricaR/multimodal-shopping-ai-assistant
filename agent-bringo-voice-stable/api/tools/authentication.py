"""
Authentication tools - Real Bringo login via Selenium
Uses credentials from database (SQLite) with .env fallback
"""

import logging
import json
import time
from typing import Dict
from selenium import webdriver
# from selenium.webdriver.chrome.service import Service as ChromeService
# from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from datetime import datetime, timedelta
import requests

# Import unified database module
from api.tools.shared import db
from config.settings import settings

logger = logging.getLogger("authentication_tools")

def authenticate_with_credentials(username: str, password: str, store: str = "carrefour_park_lake") -> str:
    """
    REAL ACTION: Authenticate with Bringo using Selenium
    """
    logger.info(f"🔐 Starting automated authentication for: {username}")
    
    driver = None
    
    try:
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36")
        
        # Initialize driver
        # Use Selenium Manager (built-in) instead of webdriver_manager to avoid architecture mismatches
        # and handle the binary location automatically.
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        logger.info("Browser initialized successfully")
        
        # Navigate to login page
        login_url = "https://www.bringo.ro/ro/login"
        logger.info(f"Navigating to login page: {login_url}")
        driver.get(login_url)
        
        # Wait for page load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        logger.info("Filling login credentials...")
        
        # Find username field
        # Find username field - try multiple selectors
        username_selectors = [
            "input[name='_username']",
            "input[type='email']",
            "#username",
            "#email",
            "input[placeholder*='email' i]"
        ]
        username_field = None
        for selector in username_selectors:
            try:
                username_field = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except:
                continue
        
        if not username_field:
            raise Exception("Username field not found")
        
        # Find password field - try multiple selectors
        password_selectors = [
            "input[name='_password']",
            "input[type='password']",
            "#password"
        ]
        password_field = None
        for selector in password_selectors:
            try:
                password_field = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except:
                continue
        
        if not password_field:
            raise Exception("Password field not found")
        
        # Fill credentials
        username_field.clear()
        username_field.send_keys(username)
        password_field.clear()
        password_field.send_keys(password)
        
        # Find and click submit button
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:contains('Login')",
            "button:contains('Sign in')",
            ".btn-login",
            "form button"
        ]
        submit_button = None
        for selector in submit_selectors:
            try:
                submit_button = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except:
                continue
        
        if not submit_button:
            raise Exception("Submit button not found")
        
        logger.info("Submitting login form...")
        submit_button.click()
        
        # Monitor for login success
        logger.info("Monitoring for login success...")
        timeout = 60
        start_time = time.time()
        login_successful = False

        success_indicators = [
            lambda d: store in d.current_url,
            lambda d: d.find_elements(By.CSS_SELECTOR, ".account-dropdown, .user-menu, [data-testid='user-menu']"),
            lambda d: not d.find_elements(By.CSS_SELECTOR, "form[action*='login'], #login-form"),
            lambda d: d.find_elements(By.CSS_SELECTOR, "a[href*='logout'], button[data-action='logout']")
        ]
        
        while time.time() - start_time < timeout:
            current_url = driver.current_url
            for i, indicator in enumerate(success_indicators):
                try:
                    if indicator(driver):
                        logger.info(f"Login success detected by indicator {i+1}! URL: {current_url}")
                        login_successful = True
                        break
                except:
                    continue

            if login_successful:
                break

            # Check for error messages
            try:
                error_elements = driver.find_elements(By.CSS_SELECTOR, ".alert-danger, .error-message, .login-error, [class*='error']")
                if error_elements:
                    error_text = error_elements[0].text
                    if any(keyword in error_text.lower() for keyword in ['invalid', 'incorrect', 'failed', 'error']):
                        driver.save_screenshot("login_failed_error.png")
                        raise Exception(f"Login failed: {error_text}")
            except Exception as e:
                # ignore error check failures
                pass

            time.sleep(1)
        
        if not login_successful:
            try:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                screenshot_path = f"login_timeout_{timestamp}.png"
                driver.save_screenshot(screenshot_path)
                logger.error(f"Login timed out. Screenshot saved to {screenshot_path}. URL: {driver.current_url}")
            except Exception as e:
                logger.error(f"Failed to save screenshot: {e}")
            raise Exception("Login success detection timed out")
        
        # Extract cookies
        logger.info("Extracting session cookies...")
        cookies = driver.get_cookies()

        extracted_cookies = {}
        phpsessid_cookie = None
        for cookie in cookies:
            if cookie['name'] in ['PHPSESSID', 'OptanonConsent', '_ga', '_gid', '_gat']:
                extracted_cookies[cookie['name']] = cookie['value']
                if cookie['name'] == 'PHPSESSID':
                    phpsessid_cookie = cookie

        if 'PHPSESSID' not in extracted_cookies:
            raise Exception("PHPSESSID cookie not found")

        logger.info(f"✅ Extracted {len(extracted_cookies)} cookies including PHPSESSID")

        # Save credentials and session to database
        # Use actual cookie expiration if available, otherwise use conservative 2-hour default
        if phpsessid_cookie and 'expiry' in phpsessid_cookie:
            # Cookie expiry is in Unix timestamp
            expires_at = datetime.fromtimestamp(phpsessid_cookie['expiry']).isoformat()
            logger.info(f"🕐 Using actual cookie expiration: {expires_at}")
        else:
            # Conservative 2-hour expiration instead of 24 hours
            expires_at = (datetime.now() + timedelta(hours=2)).isoformat()
            logger.warning(f"⚠️ Cookie expiry not found, using conservative 2-hour expiration: {expires_at}")

        db.save_credentials(username, password, extracted_cookies['PHPSESSID'])
        db.update_session(username, extracted_cookies['PHPSESSID'], expires_at)
        logger.info(f"💾 Saved credentials and session to database for: {username}")
        
        return json.dumps({
            "status": "success",
            "cookies": extracted_cookies,
            "phpsessid": extracted_cookies['PHPSESSID'],
            "store": store,
            "expires_at": expires_at,
            "authenticated_at": datetime.now().isoformat(),
            "saved_to_database": True
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return json.dumps({
            "status": "error",
            "message": str(e)
        })
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass

def validate_session(phpsessid: str) -> str:
    """
    REAL ACTION: Validate if session is still active
    """
    import requests
    logger.info(f"🔍 Validating session: {phpsessid[:8]}...")
    
    try:
        session = requests.Session()
        session.cookies.set('PHPSESSID', phpsessid, domain='www.bringo.ro')
        
        # Test endpoint
        response = session.get("https://www.bringo.ro/ro/_partial/cart/summary")
        
        if response.status_code == 200 and "login" not in response.url.lower():
            logger.info("✅ Session is valid")
            return json.dumps({"status": "valid", "message": "Session is active"})
        else:
            logger.warning("⚠️ Session expired")
            return json.dumps({"status": "expired", "message": "Session has expired"})
    except Exception as e:
        logger.error(f"Validation error: {e}")
        return json.dumps({"status": "error", "message": str(e)})

def get_authentication_from_state() -> str:
    """
    REAL ACTION: Retrieve authentication from database
    """
    try:
        logger.info("🔍 Checking authentication state in database...")
        creds = db.get_credentials()
        
        if not creds:
            return json.dumps({"status": "not_authenticated", "message": "No credentials found in database."})
        
        if not creds.get('session_cookie'):
            return json.dumps({"status": "authenticated_no_session", "username": creds.get('username')})
        
        return json.dumps({
            "status": "authenticated",
            "username": creds.get('username'),
            "session_cookie": creds.get('session_cookie'),
            "last_login": creds.get('last_login'),
            "expires_at": creds.get('cookie_expires')
        }, ensure_ascii=False, indent=2)
        
    except Exception as e:
        logger.error(f"❌ Error checking authentication state: {e}")
        return json.dumps({"status": "error", "message": f"Failed: {str(e)}"})
