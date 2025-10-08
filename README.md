# Microsoft Graph SDK Email Reader

A Python application that uses the **Microsoft Graph SDK** to read emails from your inbox. This is the SDK version that provides high-level functions instead of raw HTTP requests.

## Key Differences from Raw HTTP Version

### **This Version (Graph SDK):**
- ✅ **Pre-built Functions**: Uses SDK methods like `client.me.messages.get()`
- ✅ **Type Safety**: Built-in models and validation
- ✅ **Less Code**: No manual URL construction or HTTP headers
- ✅ **Auto Error Handling**: Built-in retry logic and error handling
- ❌ **Async/Await**: Requires asynchronous programming
- ❌ **Heavier**: Larger dependency footprint

### **Raw HTTP Version (using MSAL):**
- ✅ **Full Control**: Complete control over requests
- ✅ **Synchronous**: No async/await complexity
- ✅ **Lightweight**: Minimal dependencies
- ❌ **More Code**: Manual URL construction and error handling

## Prerequisites

- Python 3.7 or higher
- An Azure AD account (work/school account)
- Azure app registration (same as raw HTTP version)

## Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Azure App Configuration
Use the **same Azure app registration** as the raw HTTP version. No changes needed:

- **Authentication**: "Allow public client flows" = Yes
- **API Permissions**: Mail.Read, Mail.ReadWrite, User.Read (Delegated)
- **No admin consent required**

### 3. Configure Environment
Update the `.env` file with your Azure app details:
```env
CLIENT_ID=your_application_client_id_here
TENANT_ID=your_directory_tenant_id_here
```

## Usage

### Run the SDK Version
```bash
python main_sdk.py
```

### Authentication Flow
Same device code flow as the raw HTTP version:
1. App displays device code and URL
2. Open browser and enter code
3. Sign in with your work account
4. Tokens are cached for future runs

## Code Comparison

### **Raw HTTP Version:**
```python
# Manual HTTP request
def get_inbox_messages(self):
    token = self.get_access_token()
    url = f"{self.graph_url}/me/mailFolders/inbox/messages"
    headers = {'Authorization': f'Bearer {token}'}
    params = {'$top': 10, '$select': 'id,subject,from'}
    response = requests.get(url, headers=headers, params=params)
    return response.json()
```

### **SDK Version:**
```python
# SDK method
async def get_inbox_messages(self):
    request_config = MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
        query_parameters=MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            top=10,
            select=['id', 'subject', 'from']
        )
    )
    messages = await self.client.me.mail_folders.inbox.messages.get(request_configuration=request_config)
    return messages.value
```

## Features

### **Email Operations**
- ✅ **Read Messages**: Get all or unread messages only
- ✅ **Message Details**: Get full message content
- ✅ **Mark as Read**: Update message read status
- ✅ **Filter by Subject**: Find emails containing specific terms

### **Folder Operations**
- ✅ **List Folders**: Get all mail folders
- ✅ **Create Folders**: Create new mail folders
- ✅ **Move Messages**: Move emails between folders
- ✅ **Auto-Create**: Automatically create folders if they don't exist

### **SDK Advantages**
- ✅ **Built-in Models**: Strongly typed Message and MailFolder objects
- ✅ **Automatic Serialization**: No manual JSON parsing
- ✅ **Error Handling**: Built-in retry and error handling
- ✅ **IntelliSense**: Better IDE support with autocomplete

## Dependencies

```
msgraph>=1.0.0          # Microsoft Graph SDK
azure-identity>=1.15.0  # Azure authentication
python-dotenv>=1.0.0    # Environment variables
```

## Async/Await Pattern

The SDK uses async/await for all operations:

```python
# All SDK methods are async
messages = await reader.get_inbox_messages()
folder = await reader.create_folder("test")
success = await reader.move_message(message_id, folder_id)

# Main function must be async
async def main():
    reader = EmailReaderSDK()
    messages = await reader.get_inbox_messages()

# Run with asyncio
asyncio.run(main())
```

## When to Use Each Version

### **Use SDK Version When:**
- Building production applications
- Want built-in error handling and retry logic
- Prefer strongly typed objects
- Don't mind async/await complexity
- Want automatic updates for API changes

### **Use Raw HTTP Version When:**
- Learning how Graph API works
- Need synchronous operations
- Want minimal dependencies
- Need maximum flexibility and control
- Building simple scripts or prototypes

## Performance

Both versions have similar performance for basic operations. The SDK adds some overhead for object creation and serialization, but provides better error handling and retry logic.

## Security

Both versions use the same authentication flow and security model. The SDK doesn't add or remove any security features - it's just a different way to make the same API calls.