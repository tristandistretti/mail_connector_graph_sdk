#!/usr/bin/env python3
"""
Email processing server that runs continuously
"""

import asyncio
import signal
import sys
from datetime import datetime
from email_reader_sdk import EmailReaderSDK

# ============================================================================
# GLOBAL CONFIGURATION - Edit these values to control all timing intervals
# ============================================================================

# Set to True for quick testing (30 second intervals)
DEVELOPMENT_MODE = True

if DEVELOPMENT_MODE:
    CHECK_INTERVAL_MINUTES = 0.5  # 30 seconds for testing
    ERROR_RETRY_MINUTES = 0.1     # 6 seconds for testing
else:
    CHECK_INTERVAL_MINUTES = 60   # 1 hour for production
    ERROR_RETRY_MINUTES = 1       # 1 minute for production

# Derived constants (don't change these directly)
CHECK_INTERVAL_SECONDS = int(CHECK_INTERVAL_MINUTES * 60)
ERROR_RETRY_SECONDS = int(ERROR_RETRY_MINUTES * 60)

class EmailServer:
    def __init__(self):
        self.reader = EmailReaderSDK()
        self.check_interval = CHECK_INTERVAL_SECONDS
        self.error_retry_interval = ERROR_RETRY_SECONDS
        self.running = False
        self.shutdown_event = asyncio.Event()
        
    async def start(self):
        """Start the email processing server"""
        mode = "DEVELOPMENT" if DEVELOPMENT_MODE else "PRODUCTION"
        print(f"� Starting Email Processing Server ({mode} MODE)...")
        
        if DEVELOPMENT_MODE:
            print(f"📅 Check interval: {CHECK_INTERVAL_SECONDS} seconds (for testing)")
            print(f"⚠️ Error retry interval: {ERROR_RETRY_SECONDS} seconds")
        else:
            print(f"📅 Check interval: {CHECK_INTERVAL_MINUTES} minutes")
            print(f"⚠️ Error retry interval: {ERROR_RETRY_MINUTES} minutes")
        
        if not await self.reader.authenticate():
            print("❌ Initial authentication failed. Server cannot start.")
            return
        
        self.running = True
        print("✅ Server started successfully!")
        
        loop = asyncio.get_event_loop()
        for sig in [signal.SIGINT, signal.SIGTERM]:
            loop.add_signal_handler(sig, self._signal_handler, sig)
        
        while self.running:
            try:
                await self._process_emails()
                
                if self.running:
                    if DEVELOPMENT_MODE:
                        print(f"😴 Sleeping for {CHECK_INTERVAL_SECONDS} seconds... (Press Ctrl+C to stop)")
                    else:
                        print(f"😴 Sleeping for {CHECK_INTERVAL_MINUTES} minutes... (Press Ctrl+C to stop)")
                    
                    # Use asyncio.wait_for with shutdown_event to allow interruption
                    try:
                        await asyncio.wait_for(
                            self.shutdown_event.wait(), 
                            timeout=self.check_interval
                        )
                        break
                    except asyncio.TimeoutError:
                        pass
                    
            except Exception as e:
                print(f"❌ Error in server loop: {e}")
                if DEVELOPMENT_MODE:
                    print(f"🔄 Continuing in {ERROR_RETRY_SECONDS} seconds...")
                else:
                    print(f"🔄 Continuing in {ERROR_RETRY_MINUTES} minutes...")
                
                try:
                    await asyncio.wait_for(
                        self.shutdown_event.wait(), 
                        timeout=self.error_retry_interval
                    )
                    break
                except asyncio.TimeoutError:
                    pass
        
        print("🛑 Email Processing Server stopped")
    
    async def _process_emails(self):
        """Process emails - this is where your email logic goes"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n📧 Processing emails at {current_time}")
        
        try:
            if self.shutdown_event.is_set():
                return
            
            await self.reader.process_emails_by_subject("daily stand up", "daily meetings")
            
            if self.shutdown_event.is_set():
                return
            
            unread_messages = await self.reader.get_inbox_messages(filter_unread=True, top=50)
            if unread_messages:
                print(f"�N Found {len(unread_messages)} unread messages")
            else:
                print("📭 No unread messages")
                
        except Exception as e:
            print(f"❌ Error processing emails: {e}")
    
    def _signal_handler(self, signum):
        """Handle shutdown signals gracefully"""
        print(f"\n🛑 Received signal {signum} - Shutting down gracefully...")
        self.running = False
        self.shutdown_event.set()
    
    def stop(self):
        """Stop the server"""
        self.running = False
        self.shutdown_event.set()

async def main():
    """Main server entry point"""
    server = EmailServer()
    
    try:
        await server.start()
    except KeyboardInterrupt:
        print("\n🛑 Server interrupted")
    except Exception as e:
        print(f"❌ Server error: {e}")
    finally:
        server.stop()

if __name__ == "__main__":
    print("📧 Email Processing Server")
    print("=" * 70)
    print("This server will:")
    print("• Authenticate once, then run continuously")
    if DEVELOPMENT_MODE:
        print(f"• Process emails every {CHECK_INTERVAL_SECONDS} seconds (DEV MODE)")
    else:
        print(f"• Process emails every {CHECK_INTERVAL_MINUTES} minutes")
    print("• Handle token refresh automatically")
    print("• Run until stopped with Ctrl+C")
    print("=" * 70)
    print("💡 CONFIGURATION:")
    print(f"   DEVELOPMENT_MODE = {DEVELOPMENT_MODE}")
    print(f"   CHECK_INTERVAL_MINUTES = {CHECK_INTERVAL_MINUTES}")
    print(f"   ERROR_RETRY_MINUTES = {ERROR_RETRY_MINUTES}")
    print("=" * 70)
    
    asyncio.run(main())