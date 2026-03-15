"""
Background Worker for Bringo Session Keep-Alive
Continuously monitors and refreshes sessions before they expire.

Based on Cloud Run Worker Pool pattern for non-HTTP background processing.
References:
- https://cloud.google.com/run/docs/deploy-worker-pools
- https://cloud.google.com/blog/products/serverless/exploring-cloud-run-worker-pools-and-kafka-autoscaler
"""

import logging
import time
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional

from services.auth_service import AuthService
from database import db_adapter as db
from config.settings import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("session_keepalive_worker")

class SessionKeepAliveWorker:
    """
    Worker that keeps Bringo sessions alive by proactively refreshing them.

    Pattern: Pull-based background processing
    - Continuously polls database for sessions needing refresh
    - Refreshes sessions before they expire (with configurable buffer)
    - Validates sessions periodically
    """

    def __init__(
        self,
        refresh_buffer_minutes: int = 60,
        poll_interval_seconds: int = 3600,
        validate_interval_minutes: int = 15
    ):
        """
        Initialize the session keep-alive worker.

        Args:
            refresh_buffer_minutes: Refresh session this many minutes before expiration
            poll_interval_seconds: How often to check for sessions needing refresh
            validate_interval_minutes: How often to validate session with server
        """
        self.refresh_buffer_minutes = refresh_buffer_minutes
        self.poll_interval_seconds = poll_interval_seconds
        self.validate_interval_minutes = validate_interval_minutes
        self.running = True
        self.last_validation = {}  # Track last validation time per session

        # Setup graceful shutdown
        signal.signal(signal.SIGTERM, self._shutdown_handler)
        signal.signal(signal.SIGINT, self._shutdown_handler)

        logger.info(f"🔧 Worker initialized:")
        logger.info(f"   - Refresh buffer: {refresh_buffer_minutes} minutes")
        logger.info(f"   - Poll interval: {poll_interval_seconds} seconds")
        logger.info(f"   - Validate interval: {validate_interval_minutes} minutes")

    def _shutdown_handler(self, signum, frame):
        """Handle graceful shutdown"""
        logger.info(f"🛑 Received signal {signum}, shutting down gracefully...")
        self.running = False
        sys.exit(0)

    def should_refresh_session(self, expires_at_str: Optional[str]) -> bool:
        """
        Check if session should be refreshed based on expiration time.

        Args:
            expires_at_str: ISO format expiration timestamp

        Returns:
            True if session should be refreshed
        """
        if not expires_at_str:
            logger.warning("No expiration time found - should refresh")
            return True

        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            now = datetime.now(expires_at.tzinfo)
            buffer = timedelta(minutes=self.refresh_buffer_minutes)

            # Refresh if we're within buffer time of expiration
            should_refresh = now >= (expires_at - buffer)

            if should_refresh:
                time_until_expiry = (expires_at - now).total_seconds() / 60
                logger.info(f"⏰ Session expires in {time_until_expiry:.1f} minutes - triggering refresh")

            return should_refresh

        except Exception as e:
            logger.error(f"Error parsing expiration time: {e}")
            return True

    def should_validate_session(self, phpsessid: str) -> bool:
        """
        Check if session should be validated with Bringo server.

        Args:
            phpsessid: Session cookie value

        Returns:
            True if validation is needed
        """
        last_check = self.last_validation.get(phpsessid)

        if not last_check:
            return True

        time_since_check = datetime.now() - last_check
        should_validate = time_since_check >= timedelta(minutes=self.validate_interval_minutes)

        if should_validate:
            logger.info(f"🔍 Last validation was {time_since_check.total_seconds()/60:.1f} minutes ago - validating")

        return should_validate

    def refresh_session(self, username: str, password: str, store: str) -> bool:
        """
        Refresh a session by re-authenticating.

        Args:
            username: User's email
            password: User's password
            store: Store ID

        Returns:
            True if refresh successful
        """
        try:
            logger.info(f"🔄 Refreshing session for {username}...")
            db.log_session_action(username, "refresh_trigger")

            result = AuthService.authenticate_with_credentials(username, password, store)

            if result.get("status") == "success":
                new_expires = result.get("expires_at")
                logger.info(f"✅ Session refreshed successfully! New expiration: {new_expires}")
                db.log_session_action(username, "refresh_success", result.get("phpsessid"), datetime.fromisoformat(new_expires))
                return True
            else:
                error_msg = result.get("message", "Unknown error")
                logger.error(f"❌ Failed to refresh session: {error_msg}")
                db.log_session_action(username, "refresh_failed")
                return False

        except Exception as e:
            logger.error(f"❌ Error refreshing session: {e}")
            return False

    def validate_and_refresh_if_needed(self, phpsessid: str, username: str) -> bool:
        """
        Validate session with server and refresh if expired.

        Args:
            phpsessid: Session cookie
            username: Username for refresh

        Returns:
            True if session is valid or was refreshed
        """
        try:
            validation = AuthService.validate_session(phpsessid)
            self.last_validation[phpsessid] = datetime.now()

            if validation.get("status") == "expired":
                logger.warning(f"⚠️ Session for {username} expired on server")
                db.log_session_action(username, "server_expired")

                # Get credentials and refresh
                creds = db.get_credentials(username)
                if creds:
                    return self.refresh_session(
                        creds['username'],
                        creds['password'],
                        settings.BRINGO_STORE
                    )
                else:
                    logger.error(f"❌ No credentials found for {username}")
                    return False
            
            db.log_session_action(username, "validation_ok")
            return True

        except Exception as e:
            logger.error(f"Error validating session: {e}")
            return False

    def process_sessions(self):
        """
        Main processing loop - check and refresh sessions for ALL users.
        """
        try:
            # Get all users (multi-tenant support)
            all_users = db.get_all_users()

            if not all_users:
                logger.debug("No users found in database")
                return

            logger.info(f"📋 Processing sessions for {len(all_users)} users")

            for user_data in all_users:
                username = user_data.get('username') or user_data.get('email')
                phpsessid = user_data.get('session_cookie')
                expires_at_str = user_data.get('cookie_expires')

                if not username:
                    continue

                logger.info(f"🔍 Checking session for {username}")
                db.log_session_action(username, "check_start")

                if not phpsessid:
                    logger.warning(f"⚠️ No session cookie for {username}")
                    db.log_session_action(username, "no_session")
                    continue

                # Check if we should validate with server
                if self.should_validate_session(phpsessid):
                    self.validate_and_refresh_if_needed(phpsessid, username)

                # Check if we should refresh based on expiration time
                elif self.should_refresh_session(expires_at_str):
                    creds = db.get_credentials(username)
                    if creds and creds.get('password'):
                        self.refresh_session(username, creds['password'], settings.BRINGO_STORE)
                    else:
                        logger.error(f"❌ No credentials/password found for {username}")
                        db.log_session_action(username, "missing_creds")
                else:
                    logger.info(f"✓ Session for {username} is healthy")
                    db.log_session_action(username, "check_ok")

        except Exception as e:
            logger.error(f"Error processing sessions: {e}", exc_info=True)

    def run(self):
        """
        Main worker loop - continuously process sessions.
        """
        logger.info("🚀 Session Keep-Alive Worker started")
        logger.info(f"📊 Polling every {self.poll_interval_seconds} seconds")

        iteration = 0

        while self.running:
            iteration += 1

            try:
                logger.info(f"--- Iteration {iteration} ---")
                self.process_sessions()

                # Sleep until next poll
                logger.debug(f"💤 Sleeping for {self.poll_interval_seconds} seconds...")
                time.sleep(self.poll_interval_seconds)

            except Exception as e:
                logger.error(f"Unexpected error in main loop: {e}", exc_info=True)
                # Sleep before retrying
                time.sleep(self.poll_interval_seconds)

        logger.info("👋 Worker stopped")


def main():
    """
    Entry point for the worker.
    Can be deployed to Cloud Run Worker Pool or run locally.
    """
    # Configuration from environment or defaults
    refresh_buffer = int(settings.SESSION_REFRESH_BUFFER_MINUTES or 30)
    poll_interval = int(settings.SESSION_POLL_INTERVAL_SECONDS or 60)
    validate_interval = int(settings.SESSION_VALIDATE_INTERVAL_MINUTES or 15)

    worker = SessionKeepAliveWorker(
        refresh_buffer_minutes=refresh_buffer,
        poll_interval_seconds=poll_interval,
        validate_interval_minutes=validate_interval
    )

    worker.run()


if __name__ == "__main__":
    main()
