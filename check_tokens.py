#!/usr/bin/env python3
"""
Simple script to check if refresh tokens are properly stored
"""

import asyncio
from email_reader_sdk import EmailReaderSDK

async def main():
    print("🔍 Checking Token Status...")
    print("=" * 60)
    
    # Initialize the SDK
    reader = EmailReaderSDK()
    
    # Check current token status
    reader.debug_token_status()
    
    # Try to authenticate (this will use cached tokens if available)
    print("\n🔐 Testing Authentication...")
    success = await reader.authenticate()
    
    if success:
        print("✅ Authentication successful!")
        
        # Check token status again after authentication
        print("\n🔍 Post-Authentication Token Status:")
        reader.debug_token_status()
        
        # Test if we can make API calls
        print("\n📧 Testing API Call...")
        try:
            messages = await reader.get_inbox_messages(top=1)
            if messages is not None:
                print("✅ API call successful - tokens are working!")
            else:
                print("❌ API call failed")
        except Exception as e:
            print(f"❌ API call error: {e}")
    else:
        print("❌ Authentication failed")
    
    print("\n" + "=" * 60)
    print("💡 WHAT TO LOOK FOR:")
    print("✅ 'Refresh Token: Available' = Server can run long-term")
    print("❌ 'Refresh Token: Not available' = Will need re-auth every hour")
    print("✅ Cache file with size > 0 = Tokens are being stored")
    print("❌ No cache files = Tokens not persisting between runs")

if __name__ == "__main__":
    asyncio.run(main())