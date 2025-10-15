import os
import re
from typing import Optional, List
from dotenv import load_dotenv
from html import unescape

from msgraph import GraphServiceClient
from azure.identity import DeviceCodeCredential, TokenCachePersistenceOptions
from azure.core.credentials import AccessToken
from msgraph.generated.models.message import Message
from msgraph.generated.models.mail_folder import MailFolder
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder

# Configuration constants
DEFAULT_MESSAGE_LIMIT: int = 10

class EmailReaderSDK:
    def __init__(self) -> None:
        load_dotenv()
        self.client_id: Optional[str] = os.getenv('CLIENT_ID')
        self.tenant_id: Optional[str] = os.getenv('TENANT_ID')
        
        if not all([self.client_id, self.tenant_id]):
            raise ValueError("Missing required environment variables. Check your .env file.")
        
        # Microsoft Graph scopes (offline_access is automatically included with these)
        self.scopes: List[str] = [
            "https://graph.microsoft.com/Mail.Read",
            "https://graph.microsoft.com/Mail.ReadWrite", 
            "https://graph.microsoft.com/User.Read"
        ]
        
        # Configure persistent token caching for server-like behavior
        cache_options = TokenCachePersistenceOptions(
            allow_unencrypted_storage=True  # For development - use default cache name
        )
        
        # Initialize credential with persistent token caching
        # offline_access is automatically requested by DeviceCodeCredential for refresh tokens
        self.credential = DeviceCodeCredential(
            client_id=self.client_id,
            tenant_id=self.tenant_id,
            cache_persistence_options=cache_options,
            disable_automatic_authentication=False
        )
        
        # Initialize Graph Service Client
        self.client: GraphServiceClient = GraphServiceClient(
            credentials=self.credential,
            scopes=self.scopes
        )
        self._authenticated: bool = False

    async def authenticate(self) -> bool:
        """Ensure user is authenticated by making a simple API call"""
        if self._authenticated:
            return True
        
        try:
            print("🔐 Authenticating with Microsoft Graph...")
            
            user = await self.client.me.get()
            
            if user:
                print(f"✅ Successfully authenticated as: {user.display_name or 'Unknown User'}")
                self._authenticated = True
                return True
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            return False
        
        return False
    
    def debug_token_status(self) -> None:
        """Debug method to check if refresh tokens are properly stored"""
        print("\n🔍 TOKEN DEBUG INFORMATION")
        print("=" * 50)
        
        try:
            # Try to get a token (this will use cache if available)
            token = self.credential.get_token("https://graph.microsoft.com/.default")
            
            if token:
                from datetime import datetime
                import time
                
                expires_at = datetime.fromtimestamp(token.expires_on)
                time_left = token.expires_on - time.time()
                
                print("✅ Access Token Found:")
                print(f"   Expires at: {expires_at}")
                print(f"   Time left: {time_left/60:.1f} minutes")
                print(f"   Token preview: {token.token[:30]}...{token.token[-10:]}")
                
                # Check if we can get token silently (indicates refresh token exists)
                try:
                    # This should work silently if refresh token exists
                    silent_token = self.credential.get_token("https://graph.microsoft.com/.default")
                    if silent_token:
                        print("✅ Refresh Token: Available (can refresh silently)")
                        print("✅ Server Mode: Ready for long-term operation")
                    else:
                        print("❌ Refresh Token: Not available")
                        print("⚠️  Server Mode: Will require re-auth when token expires")
                except Exception as e:
                    print(f"❌ Refresh Token: Error checking - {e}")
                    
            else:
                print("❌ No access token found")
                
        except Exception as e:
            print(f"❌ Token check failed: {e}")
            print("💡 Try running authentication first")
        
        # Check cache file existence
        import os
        import glob
        
        # Check common cache locations
        cache_locations = [
            os.path.expanduser("~/.azure/msal_token_cache.bin"),
            os.path.expanduser("~/.cache/msal_token_cache.bin"),
            os.path.expanduser("~/.IdentityService/msal_token_cache.*"),
            os.path.expanduser("~/.IdentityService/*.cae"),
            os.path.expanduser("~/.IdentityService/*.nocae")
        ]
        
        print("\n📁 Cache File Status:")
        cache_found = False
        for location in cache_locations:
            if '*' in location:
                # Handle glob patterns
                matches = glob.glob(location)
                if matches:
                    for match in matches:
                        size = os.path.getsize(match)
                        print(f"✅ Found: {match} ({size} bytes)")
                        cache_found = True
                else:
                    print(f"❌ Not found: {location}")
            else:
                # Handle exact paths
                if os.path.exists(location):
                    size = os.path.getsize(location)
                    print(f"✅ Found: {location} ({size} bytes)")
                    cache_found = True
                else:
                    print(f"❌ Not found: {location}")
        
        if cache_found:
            print("✅ Token persistence: Working correctly")
        else:
            print("⚠️  No cache files found - tokens may not be persisting")
        
        print("=" * 50)
    
    async def get_inbox_messages(self, filter_unread: bool = False, top: int = DEFAULT_MESSAGE_LIMIT) -> Optional[List[Message]]:
        """
        Get inbox messages using Graph SDK
        
        Args:
            filter_unread: If True, only get unread messages
            top: Number of messages to retrieve (default: DEFAULT_MESSAGE_LIMIT)
        """
        if not await self.authenticate():
            return None
            
        try:
            print(f"📬 Fetching {'unread' if filter_unread else 'all'} inbox messages...")
            
            request_config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
                query_parameters=MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
                    top=top,
                    select=['id', 'subject', 'from', 'toRecipients', 'receivedDateTime', 'isRead', 'bodyPreview', 'body', 'hasAttachments'],
                    orderby=['receivedDateTime desc']
                )
            )

            if filter_unread:
                request_config.query_parameters.filter = "isRead eq false"

            messages = await self.client.me.messages.get(request_configuration=request_config)
            
            if messages and messages.value:
                print(f"✅ Retrieved {len(messages.value)} messages")
                return messages.value
            else:
                print("📭 No messages found")
                return []
                
        except Exception as e:
            print(f"❌ Error fetching messages: {e}")
            return None
    
    async def get_message_details(self, message_id: str) -> Optional[Message]:
        """Get detailed information about a specific message"""
        try:
            message = await self.client.me.messages.by_message_id(message_id).get()
            return message
        except Exception as e:
            print(f"❌ Error getting message details: {e}")
            return None
    
    async def mark_as_read(self, message_id: str) -> bool:
        """Mark a message as read"""
        try:
            message_update = Message()
            message_update.is_read = True
            
            await self.client.me.messages.by_message_id(message_id).patch(message_update)
            return True
        except Exception as e:
            print(f"❌ Error marking message as read: {e}")
            return False
    
    async def get_mail_folders(self) -> Optional[List[MailFolder]]:
        """Get all mail folders"""
        try:
            folders = await self.client.me.mail_folders.get()
            return folders.value if folders else []
        except Exception as e:
            print(f"❌ Error getting mail folders: {e}")
            return None
    
    async def find_folder_by_name(self, folder_name: str) -> Optional[MailFolder]:
        """Find a folder by name"""
        folders = await self.get_mail_folders()
        if not folders:
            return None
        
        for folder in folders:
            if folder.display_name and folder.display_name.lower() == folder_name.lower():
                return folder
        return None
    
    async def create_folder(self, folder_name: str) -> Optional[MailFolder]:
        """Create a new mail folder"""
        try:
            new_folder = MailFolder()
            new_folder.display_name = folder_name
            
            folder = await self.client.me.mail_folders.post(new_folder)
            return folder
        except Exception as e:
            print(f"❌ Error creating folder: {e}")
            return None
    
    async def ensure_folder_exists(self, folder_name: str) -> Optional[MailFolder]:
        """Ensure a folder exists, create it if it doesn't"""
        folder = await self.find_folder_by_name(folder_name)
        
        if folder:
            print(f"✅ Folder '{folder_name}' already exists")
            return folder

        print(f"📁 Creating folder '{folder_name}'...")
        folder = await self.create_folder(folder_name)
        
        if folder:
            print(f"✅ Folder '{folder_name}' created successfully")
            return folder
        else:
            print(f"❌ Failed to create folder '{folder_name}'")
            return None    

    async def move_message(self, message_id: str, destination_folder_id: str) -> bool:
        """Move a message to a specific folder"""
        try:
            from msgraph.generated.users.item.messages.item.move.move_post_request_body import MovePostRequestBody
            
            move_request = MovePostRequestBody()
            move_request.destination_id = destination_folder_id
            
            await self.client.me.messages.by_message_id(message_id).move.post(move_request)
            return True
        except Exception as e:
            print(f"❌ Error moving message: {e}")
            return False
    
    async def process_emails_by_subject(self, search_term: str, target_folder: str = "daily meetings") -> bool:
        """Find emails with specific term in subject and move them to target folder"""
        print(f"🔍 Looking for emails with '{search_term}' in subject...")

        folder = await self.ensure_folder_exists(target_folder)
        if not folder or not folder.id:
            return False
        
        messages = await self.get_inbox_messages(top=DEFAULT_MESSAGE_LIMIT)
        if not messages:
            print("No messages found to process")
            return False
        
        moved_count = 0
        search_term_lower = search_term.lower()
        
        for message in messages:
            if message.subject and message.id and search_term_lower in message.subject.lower():
                print(f"📧 Found matching email: '{message.subject}'")
                
                if await self.move_message(message.id, folder.id):
                    print(f"✅ Moved to '{target_folder}' folder")
                    moved_count += 1
                else:
                    print(f"❌ Failed to move email")
        
        print(f"\n📊 Summary: Moved {moved_count} emails containing '{search_term}' to '{target_folder}' folder")
        return moved_count > 0
    
    def html_to_text(self, html_content: str) -> str:
        """Convert HTML content to readable plain text"""
        if not html_content:
            return ""

        # Remove script and style elements
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)

        # Replace common HTML elements with text equivalents
        replacements = [
            (r'<br\s*/?>', '\n'),
            (r'</?p[^>]*>', '\n'),
            (r'</?div[^>]*>', '\n'),
            (r'<hr[^>]*>', '\n' + '-' * 50 + '\n'),
            (r'</?b[^>]*>', '**'),
            (r'</?strong[^>]*>', '**'),
            (r'</?i[^>]*>', '*'),
            (r'</?em[^>]*>', '*'),
            (r'<a[^>]*href=["\']([^"\']*)["\'][^>]*>(.*?)</a>', r'\2 (\1)'),
        ]

        for pattern, replacement in replacements:
            html_content = re.sub(pattern, replacement, html_content, flags=re.IGNORECASE | re.DOTALL)

        # Remove all remaining HTML tags
        html_content = re.sub(r'<[^>]+>', '', html_content)

        # Decode HTML entities
        html_content = unescape(html_content)

        # Clean up whitespace
        lines = html_content.split('\n')
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if line:
                cleaned_lines.append(line)

        # Join lines and limit consecutive newlines
        result = '\n'.join(cleaned_lines)
        result = re.sub(r'\n{3,}', '\n\n', result)  # Max 2 consecutive newlines

        return result.strip()

    def display_email_beautifully(self, message: Message) -> None:
        """Display a single email in a beautiful, readable format"""
        if not message:
            print("❌ No message to display")
            return

        print("\n" + "=" * 80)
        print("📧 EMAIL DETAILS")
        print("=" * 80)

        status = "📧 UNREAD" if not message.is_read else "✅ READ"
        print(f"Status: {status}")

        if message.from_ and message.from_.email_address:
            sender_name = message.from_.email_address.name or "Unknown"
            sender_email = message.from_.email_address.address or "Unknown"
            print(f"From: {sender_name} <{sender_email}>")

        print(f"Subject: {message.subject or 'No Subject'}")
        print(f"Received: {message.received_date_time or 'Unknown'}")

        print("-" * 80)

        if message.body and message.body.content:
            body_type = str(message.body.content_type) if message.body.content_type else "Unknown"
            print(f"Body Type: {body_type}")
            print("-" * 80)

            if body_type.lower() == "bodytype.html":
                # Convert HTML to readable text
                readable_content = self.html_to_text(message.body.content)
                print("📄 EMAIL CONTENT:")
                print(readable_content)
            else:
                print("📄 EMAIL CONTENT:")
                print(message.body.content)
        else:
            print("📄 EMAIL CONTENT: No content available")

        print("=" * 80)

        # Attachments info
        if hasattr(message, 'has_attachments') and message.has_attachments:
            print("📎 This email has attachments")

        print(f"Message ID: {message.id or 'Unknown'}")
        print("=" * 80)
    
    def display_email_list_beautifully(self, messages: Optional[List[Message]]) -> None:
        """Display a list of emails in a beautiful, compact format"""
        if not messages:
            print("📭 No messages found")
            return
        
        print(f"\n📬 INBOX SUMMARY ({len(messages)} messages)")
        print("=" * 100)
        
        for i, message in enumerate(messages, 1):
            status_icon = "📧" if not message.is_read else "✅"

            sender = "Unknown Sender"
            if message.from_ and message.from_.email_address:
                sender_name = message.from_.email_address.name
                sender_email = message.from_.email_address.address
                if sender_name and sender_email:
                    sender = f"{sender_name} <{sender_email}>"
                elif sender_email:
                    sender = sender_email
                elif sender_name:
                    sender = sender_name
            
            subject = message.subject or "No Subject"
            date = str(message.received_date_time)[:19] if message.received_date_time else "Unknown Date"
            preview = (message.body_preview[:80] + "...") if message.body_preview and len(message.body_preview) > 80 else (message.body_preview or "")
            
            print(f"{i:2d}. {status_icon} {subject}")
            print(f"    👤 {sender}")
            print(f"    📅 {date}")
            if preview:
                print(f"    💬 {preview}")
            print(f"    🆔 {message.id}")
            print("-" * 100)
        
        print("=" * 100)