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
        reader.display_messages(all_messages)
        
        # Get only unread messages
        print("\n📩 Fetching unread messages...")
        unread_messages: Optional[List[Message]] = await reader.get_inbox_messages(filter_unread=True, top=10)  # Keep small for demo
        reader.display_messages(unread_messages)
        
        # Example: Get details of the first message if available
        if all_messages and len(all_messages) > 0:
            first_message = all_messages[0]
            if first_message.id:
                print(f"\n📄 Getting details for first message...")
                message_details: Optional[Message] = await reader.get_message_details(first_message.id)
                
                if message_details:
                    print(f"Subject: {message_details.subject or 'No Subject'}")
                    body_type = "Unknown"
                    if message_details.body and message_details.body.content_type:
                        body_type = str(message_details.body.content_type)
                    print(f"Body Type: {body_type}")
                    print("✅ Full message body available in message_details.body.content")
        
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