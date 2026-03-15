"""
Authentication Service - Real Bringo login via Selenium
Uses credentials from database (SQLite) with .env fallback via settings
"""

import logging
import json
import time
from typing import Dict, Optional, Tuple, Any
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from datetime import datetime, timedelta

from database import db_adapter as db
from config.settings import settings

logger = logging.getLogger(__name__)

class AuthService:
    """Service for handling Bringo authentication"""
    
    @staticmethod
    def get_credentials_from_config() -> Dict[str, Any]:
        """
        Get authentication credentials from database or settings
        
        Priority:
        1. Try to get from SQLite database (previously saved)
        2. Fallback to settings (env vars)
        3. Save to database if loaded from settings
        
        Returns:
            Dict with credentials
        """
        try:
            # Try database first
            creds_from_db = db.get_credentials()
            
            if creds_from_db:
                logger.info(f"✅ Retrieved credentials from DATABASE for: {creds_from_db['username']}")
                return {
                    "status": "success",
                    "username": creds_from_db['username'],
                    "password": creds_from_db['password'],
                    "store": settings.BRINGO_STORE,
                    "source": "database",
                    "message": "Credentials loaded from database"
                }
            
            # Fallback to settings
            username = settings.BRINGO_USERNAME
            password = settings.BRINGO_PASSWORD
            store = settings.BRINGO_STORE
            
            if not username or not password:
                logger.warning("⚠️ Credentials not found in database or settings")
                return {
                    "status": "missing",
                    "message": "BRINGO_USERNAME and BRINGO_PASSWORD not set in config/settings and not in database"
                }
            
            # Save to database for future use
            db.save_credentials(username, password)
            logger.info(f"✅ Retrieved credentials from settings and saved to database for: {username}")
            
            return {
                "status": "success",
                "username": username,
                "password": password,
                "store": store,
                "source": "settings",
                "message": "Credentials loaded from settings and saved to database"
            }
            
        except Exception as e:
            logger.error(f"❌ Failed to get credentials: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def authenticate_with_credentials(username: str, password: str, store: str = "carrefour_park_lake") -> Dict[str, Any]:
        """
        Authenticate with Bringo using Selenium
        
        Args:
            username: Bringo email/username
            password: Bringo password
            store: Store ID to authenticate against
        
        Returns:
            Dict with authentication result and cookies
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
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            # Initialize driver
            driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=chrome_options
            )
            driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("Browser initialized successfully")
            
            # Navigate to login page
            login_url = f"{settings.BRINGO_BASE_URL}/ro/login"
            logger.info(f"Navigating to login page: {login_url}")
            driver.get(login_url)
            
            # Wait for page load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            logger.info("Filling login credentials...")
            
            # Try to find username field
            username_field = None
            try:
                username_field = driver.find_element(By.CSS_SELECTOR, "input[name='_username']")
            except Exception:
                try:
                    username_field = driver.find_element(By.CSS_SELECTOR, "input[type='email']")
                except Exception:
                    pass
            
            if not username_field:
                # Try generic selectors if specific ones fail
                username_selectors = ["#username", "#email", "input[placeholder*='email' i]"]
                for selector in username_selectors:
                    try:
                        username_field = driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except Exception:
                        continue
            
            if not username_field:
                raise Exception("Username field not found")
            
            # Try to find password field
            password_field = None
            try:
                password_field = driver.find_element(By.CSS_SELECTOR, "input[name='_password']")
            except Exception:
                try:
                    password_field = driver.find_element(By.CSS_SELECTOR, "input[type='password']")
                except Exception:
                    pass
            
            if not password_field:
                raise Exception("Password field not found")
            
            # Fill credentials
            username_field.clear()
            username_field.send_keys(username)
            password_field.clear()
            password_field.send_keys(password)
            
            # Find and click submit button
            submit_button = None
            try:
                submit_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            except Exception:
                # Try alternatives
                selectors = [".btn-login", "form button", "input[type='submit']"]
                for selector in selectors:
                    try:
                        submit_button = driver.find_element(By.CSS_SELECTOR, selector)
                        break
                    except Exception:
                        continue

            if not submit_button:
                raise Exception("Submit button not found")
            
            logger.info("Submitting login form...")
            submit_button.click()
            
            # Monitor for login success
            logger.info("Monitoring for login success...")
            timeout = 30
            start_time = time.time()
            login_successful = False

            while time.time() - start_time < timeout:
                current_url = driver.current_url
                logger.debug(f"Current URL: {current_url}")

                # Check for success indicators
                if store in current_url:
                    logger.info("Login success detected (URL contains store)!")
                    login_successful = True
                    break

                # URL navigated away from login page
                if '/login' not in current_url and 'bringo.ro' in current_url:
                    logger.info(f"Login success detected (redirected away from login to: {current_url})")
                    login_successful = True
                    break

                # Check for user menu / account elements
                try:
                    account_selectors = [
                        ".account-dropdown", ".user-menu", ".my-account",
                        "[data-user]", ".logged-in", ".user-name",
                        "a[href*='/account']", "a[href*='/profile']"
                    ]
                    for selector in account_selectors:
                        if driver.find_elements(By.CSS_SELECTOR, selector):
                            logger.info(f"Login success detected (found: {selector})!")
                            login_successful = True
                            break
                    if login_successful:
                        break
                except Exception:
                    pass

                # Check for error
                try:
                    error_selectors = [".alert-danger", ".error-message", ".login-error"]
                    for selector in error_selectors:
                        error_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if error_elements:
                            error_text = error_elements[0].text
                            if error_text.strip():
                                raise Exception(f"Login failed: {error_text}")
                except Exception as e:
                    if "Login failed" in str(e):
                        raise e

                time.sleep(1)

            if not login_successful:
                # Last resort: check if PHPSESSID changed (indicates server processed login)
                current_cookies = {c['name']: c['value'] for c in driver.get_cookies()}
                if 'PHPSESSID' in current_cookies:
                    logger.info("Login assumed successful (PHPSESSID cookie present, timeout reached)")
                    login_successful = True
                else:
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
                expires_at_dt = datetime.fromtimestamp(phpsessid_cookie['expiry'])
                expires_at = expires_at_dt.isoformat()

                # Calculate duration from now
                now = datetime.now()
                duration = expires_at_dt - now
                duration_hours = duration.total_seconds() / 3600

                logger.info(f"🕐 Cookie expiration from Bringo:")
                logger.info(f"   • Expires at: {expires_at}")
                logger.info(f"   • Current time: {now.isoformat()}")
                logger.info(f"   • Duration: {duration_hours:.2f} hours ({duration.total_seconds():.0f} seconds)")
                logger.info(f"   • Raw expiry timestamp: {phpsessid_cookie['expiry']}")
            else:
                # Conservative 2-hour expiration instead of 24 hours
                expires_at = (datetime.now() + timedelta(hours=2)).isoformat()
                logger.warning(f"⚠️ Cookie expiry not found, using conservative 2-hour expiration: {expires_at}")

            # Save to database with proper error checking
            saved_creds = db.save_credentials(username, password, extracted_cookies['PHPSESSID'])
            saved_session = db.update_session(username, extracted_cookies['PHPSESSID'], expires_at)

            if not saved_creds or not saved_session:
                logger.error(f"❌ Failed to save session to database for: {username}")
                logger.error(f"   save_credentials: {saved_creds}, update_session: {saved_session}")
                return {
                    "status": "error",
                    "message": "Authentication successful but failed to save session to database",
                    "phpsessid": extracted_cookies['PHPSESSID'],
                    "expires_at": expires_at,
                    "saved_to_database": False
                }

            logger.info(f"💾 Successfully saved credentials and session to database for: {username}")

            return {
                "status": "success",
                "cookies": extracted_cookies,
                "phpsessid": extracted_cookies['PHPSESSID'],
                "store": store,
                "expires_at": expires_at,
                "authenticated_at": datetime.now().isoformat(),
                "saved_to_database": True
            }
            
        except TimeoutException:
            logger.error("Login process timed out")
            return {
                "status": "error",
                "message": "Login process timed out"
            }
        except WebDriverException as e:
            logger.error(f"Browser error: {str(e)}")
            return {
                "status": "error",
                "message": f"Browser error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return {
                "status": "error",
                "message": str(e)
            }
        finally:
            if driver:
                try:
                    logger.info("Closing browser...")
                    driver.quit()
                except Exception as e:
                    logger.warning(f"Error closing browser: {str(e)}")

    @staticmethod
    def validate_session(phpsessid: str) -> Dict[str, Any]:
        """
        Validate if session is still active
        
        Args:
            phpsessid: PHP session ID to validate
        
        Returns:
            Dict with validation result
        """
        import requests
        
        logger.info(f"🔍 Validating session: {phpsessid[:8]}...")
        
        try:
            session = requests.Session()
            session.cookies.set('PHPSESSID', phpsessid, domain='www.bringo.ro')
            
            # Test endpoint - cart summary is usually light and requires auth for full details
            response = session.get(f"{settings.BRINGO_BASE_URL}/ro/_partial/cart/summary", timeout=10)
            
            # Bringo redirects to login or returns different content if session invalid
            if response.status_code == 200 and "login" not in response.url.lower():
                logger.info("✅ Session is valid")
                return {
                    "status": "valid",
                    "message": "Session is active"
                }
            else:
                logger.warning("⚠️ Session expired")
                return {
                    "status": "expired",
                    "message": "Session has expired"
                }
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

    @staticmethod
    def get_authentication_from_state() -> Dict[str, Any]:
        """
        Retrieve authentication from database (persistent storage)
        
        Returns:
            Dict with authentication status from database
        """
        try:
            logger.info("🔍 Checking authentication state in database...")
            
            creds = db.get_credentials()
            
            if not creds:
                logger.warning("❌ No credentials found in database")
                return {
                    "status": "not_authenticated",
                    "message": "No credentials found. Please login."
                }
            
            # Check if we have a valid session cookie
            if not creds.get('session_cookie'):
                logger.warning(f"⚠️ Credentials exist for {creds.get('username')} but no session cookie")
                return {
                    "status": "authenticated_no_session",
                    "message": "Credentials exist but no session cookie. Please re-authenticate.",
                    "username": creds.get('username')
                }
            
            # Check if session expired
            expires_at_str = creds.get('cookie_expires')
            if expires_at_str:
                expires_at = datetime.fromisoformat(expires_at_str)
                # Ensure 'now' matches the awareness of 'expires_at' to avoid comparison error
                now = datetime.now(expires_at.tzinfo)
                if now > expires_at:
                    logger.warning(f"⚠️ Session expired at {expires_at_str}")
                    return {
                        "status": "expired",
                        "message": "Authentication has expired. Please re-authenticate.",
                        "username": creds.get('username')
                    }
            
            # Valid authentication found
            logger.info(f"✅ Valid authentication found for {creds.get('username')}")
            return {
                "status": "authenticated",
                "username": creds.get('username'),
                "session_cookie": creds.get('session_cookie'),
                "last_login": creds.get('last_login'),
                "expires_at": expires_at_str
            }
            
        except Exception as e:
            logger.error(f"❌ Error checking authentication state: {e}")
            return {
                "status": "error",
                "message": f"Failed to check authentication: {str(e)}"
            }
