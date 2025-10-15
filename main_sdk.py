#!/usr/bin/env python3
"""
Simple script to read emails using Microsoft Graph SDK
"""

import asyncio
from typing import Optional, List
from email_reader_sdk import EmailReaderSDK
from msgraph.generated.models.message import Message

async def main() -> None:
    try:
        # Initialize the email reader
        reader: EmailReaderSDK = EmailReaderSDK()
        
        # Get all messages (read and unread)
        print("\n📬 Fetching all inbox messages...")
        all_messages: Optional[List[Message]] = await reader.get_inbox_messages(top=5)  # Keep small for demo

        # # Display one message in detail
        # if all_messages and len(all_messages) > 0:
        #     print(f"\n🔍 DETAILED VIEW OF FIRST EMAIL:")
        #     message_details = await reader.get_message_details(all_messages[0].id)
        #     reader.display_email_beautifully(message_details)
        #     return
        
        reader.display_email_list_beautifully(all_messages)
        
        # Get only unread messages
        print("\n📩 Fetching unread messages...")
        unread_messages: Optional[List[Message]] = await reader.get_inbox_messages(filter_unread=True, top=10)  # Keep small for demo
        reader.display_email_list_beautifully(unread_messages)
        
        # Process emails with specific subject terms - move them to specific folder
        print("\n" + "="*60)
        print("🏢 PROCESSING EMAILS BY SUBJECT (SDK VERSION)")
        print("="*60)
        await reader.process_emails_by_subject("daily stand up", "daily meetings")
        
    except ValueError as e:
        print(f"❌ Configuration Error: {e}")
        print("Please check your .env file and ensure all required values are set.")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())