import os
import asyncio
import re
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from html import unescape

from msgraph import GraphServiceClient
from azure.identity import DeviceCodeCredential
from azure.core.credentials import AccessToken
from msgraph.generated.models.message import Message
from msgraph.generated.models.mail_folder import MailFolder
from msgraph.generated.users.item.messages.messages_request_builder import MessagesRequestBuilder
from msgraph.generated.users.item.mail_folders.mail_folders_request_builder import MailFoldersRequestBuilder
import json, time

# Configuration constants
DEFAULT_MESSAGE_LIMIT: int = 10

class CachedTokenCredential:
    """Custom credential that uses cached tokens when available"""
    
    def __init__(self, device_credential: DeviceCodeCredential, token_file: str = "token.json"):
        self.device_credential = device_credential
        self.token_file = token_file
    
    def get_token(self, *scopes, **kwargs):
        """Get token - use cached if valid, otherwise get new one"""
        # Try cached token first
        cached_token = self._get_cached_token()
        if cached_token:
            return cached_token

        return self.device_credential.get_token(*scopes, **kwargs)
    
    def _get_cached_token(self) -> Optional[AccessToken]:
        """Get cached token if it's still valid"""
        try:
            if os.path.exists(self.token_file):
                with open(self.token_file, "r") as f:
                    token_data = json.load(f)
                
                access_token = token_data.get("access_token")
                expires_on = token_data.get("expires_on")
                
                if access_token and expires_on:
                    current_time = time.time()
                    
                    if current_time < expires_on:
                        return AccessToken(access_token, expires_on)
        except Exception:
            pass
        
        return None
    
    def save_token(self, token: AccessToken):
        """Save token to cache file"""
        try:
            data = {
                "access_token": token.token,
                "expires_on": token.expires_on
            }
            with open(self.token_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            print(f"⚠️ Failed to save token: {e}")

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
        
        # Initialize device code credential
        device_credential = DeviceCodeCredential(
            client_id=self.client_id,
            tenant_id=self.tenant_id
        )
        
        # Use custom token caching that saves to token.json
        self.credential = CachedTokenCredential(device_credential)
        
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
            # Check if we have a cached token
            if self.credential._get_cached_token():
                print("🔐 Using cached token - no authentication needed!")
            else:
                print("🔐 Authenticating with Microsoft Graph...")
            
            user = await self.client.me.get()
            
            if user:
                # Save the token that was just used
                token = self.credential.get_token("https://graph.microsoft.com/.default")
                self.credential.save_token(token)
                
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
                import json
                
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
        
        # Check token.json file
        print("\n📁 Token File Status:")
        token_file = "token.json"
        if os.path.exists(token_file):
            size = os.path.getsize(token_file)
            print(f"✅ Found: {token_file} ({size} bytes)")
            
            # Try to read and display token info
            try:
                with open(token_file, "r") as f:
                    token_data = json.load(f)
                
                expires_on = token_data.get("expires_on")
                if expires_on:
                    from datetime import datetime
                    expires_at = datetime.fromtimestamp(expires_on)
                    time_left = expires_on - time.time()
                    print(f"   Token expires: {expires_at}")
                    print(f"   Time left: {time_left/60:.1f} minutes")
                    
                    if time_left > 0:
                        print("✅ Token persistence: Working correctly")
                    else:
                        print("⚠️  Token has expired")
                else:
                    print("⚠️  Invalid token format")
                    
            except Exception as e:
                print(f"⚠️  Error reading token file: {e}")
        else:
            print(f"❌ Not found: {token_file}")
            print("💡 Token will be created after first authentication")
        
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
        
        folder_id: str = folder.id
        
        # Get inbox messages
        messages = await self.get_inbox_messages(top=DEFAULT_MESSAGE_LIMIT)
        if not messages:
            print("No messages found to process")
            return False
        
        moved_count: int = 0
        search_term_lower: str = search_term.lower()
        
        for message in messages:
            if message.subject and message.id:
                subject: str = message.subject.lower()
                
                if search_term_lower in subject:
                    print(f"📧 Found matching email: '{message.subject}'")
                    
                    if await self.move_message(message.id, folder_id):
                        print(f"✅ Moved to '{target_folder}' folder")
                        moved_count += 1
                    else:
                        print(f"❌ Failed to move email")
        
        print(f"\n📊 Summary: Moved {moved_count} emails containing '{search_term}' to '{target_folder}' folder")
        return moved_count > 0
    
    def display_messages(self, messages: Optional[List[Message]]) -> None:
        """Display messages in a readable format"""
        if not messages:
            print("No messages found or error occurred.")
            return
        
        print(f"\nFound {len(messages)} messages:")
        print("-" * 80)
        
        for i, message in enumerate(messages, 1):

            status: str = "📧 UNREAD" if not message.is_read else "✅ READ"
            sender: str = "Unknown"
            if message.from_ and message.from_.email_address:
                sender = message.from_.email_address.address or "Unknown"
            
            subject: str = message.subject or "No Subject"
            received: str = str(message.received_date_time) if message.received_date_time else "Unknown"
            body_preview: str = message.body_preview or ""
            preview: str = body_preview[:100] + "..." if len(body_preview) > 100 else body_preview
            
            print(f"{i}. {status}")
            print(f"   From: {sender}")
            print(f"   Subject: {subject}")
            print(f"   Received: {received}")
            print(f"   Preview: {preview}")
            print(f"   Message ID: {message.id or 'Unknown'}")
            print("-" * 80)

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
