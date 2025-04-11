import logging
from pathlib import Path
from typing import Optional, Dict, List, Any, Union

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.types import Message, User, Chat, Channel
from telethon.tl import types


from telethon.tl.functions.messages import SendReactionRequest


# Import from our refactored config module
# Import specific config values directly
from .config import (
    TG_API_ID,
    TG_API_HASH,
    TG_PHONE_NUMBER,
    HOME_DATA_DIR,
    SESSION_FILENAME,
)

# Setup logger for this module
logger = logging.getLogger(__name__)

# --- Global Instance Holder ---
# Define the global instance here, to be managed by server lifespan
telegram_wrapper_instance: Optional["TelegramClientWrapper"] = None


class TelegramClientWrapper:
    """Wraps the Telethon client for easier use within the MCP server."""

    def __init__(self):
        self.api_id: int = TG_API_ID
        self.api_hash: str = TG_API_HASH
        self.phone_number: Optional[str] = TG_PHONE_NUMBER
        self.session_path: Path = HOME_DATA_DIR / SESSION_FILENAME
        self.client: Optional[TelegramClient] = None
        logger.info(
            f"TelegramClientWrapper initialized. Session path: {self.session_path}"
        )

    async def connect(self, perform_login_if_needed: bool = False) -> bool:
        """
        Initializes and connects the Telethon client.
        If perform_login_if_needed is True, attempts phone login if not authorized.
        Returns True if connected and authorized, False otherwise (or raises error on login failure).
        """
        if self.client and self.client.is_connected():
            logger.info("Client already connected.")
            try:
                if self.client.is_user_authorized():
                    logger.info("User already authorized.")
                    return True
                else:
                    logger.warning("Client connected but user not authorized.")
                    if perform_login_if_needed:
                        return await self._perform_phone_login()
                    else:
                        return False
            except Exception as e:
                logger.error(f"Error checking authorization status: {e}")
                await self.disconnect()
                return False

        logger.info(f"Initializing TelegramClient with session: {self.session_path}")
        self.client = TelegramClient(
            str(self.session_path),
            self.api_id,
            self.api_hash,
            system_version="4.16.30-vxCUSTOM",
        )

        try:
            logger.info("Connecting to Telegram...")
            await self.client.connect()
            logger.info("Initial connection successful.")

            if await self.client.is_user_authorized():
                user = await self.client.get_me()
                if user:
                    logger.info(f"User {user.username or user.id} is authorized.")
                    return True
                else:
                    logger.warning("Client authorized but get_me() returned None.")
                    if perform_login_if_needed:
                        logger.warning(
                            "Attempting login again due to inconsistent state."
                        )
                        return await self._perform_phone_login()
                    else:
                        await self.disconnect()
                        return False
            else:
                logger.warning("User is not authorized.")
                if perform_login_if_needed:
                    return await self._perform_phone_login()
                else:
                    await self.disconnect()
                    return False

        except Exception as e:
            logger.error(f"Failed to connect: {e}")
            await self.disconnect()
            if perform_login_if_needed:
                raise
            else:
                return False

    async def _perform_phone_login(self) -> bool:
        """Handles the interactive phone number and code login flow."""
        if not self.client or not self.client.is_connected():
            logger.error("Cannot perform phone login, client not connected.")
            return False

        phone_to_use = self.phone_number
        if not phone_to_use:
            try:
                phone_to_use = input(
                    "Please enter your phone number (e.g., +1234567890): "
                )
            except EOFError:
                logger.error(
                    "Cannot prompt for phone number in non-interactive mode. Set TG_PHONE_NUMBER environment variable."
                )
                return False

        logger.info(f"Attempting login for phone number: {phone_to_use}")
        print(f"Attempting login for phone number: {phone_to_use}")

        try:
            print("Requesting login code from Telegram...")
            code_info = await self.client.send_code_request(phone_to_use)
            logger.info("Login code sent via Telegram.")
            print("Login code sent via Telegram.")

            code = ""
            while not code:
                try:
                    code = input("Please enter the code you received: ")
                except EOFError:
                    logger.error(
                        "Cannot prompt for login code in non-interactive mode."
                    )
                    return False

            logger.info("Attempting sign-in with received code...")
            signed_in_user = await self.client.sign_in(
                phone_to_use, code=code, phone_code_hash=code_info.phone_code_hash
            )
            logger.info(
                f"Successfully signed in as: {signed_in_user.username or signed_in_user.id}"
            )
            print(
                f"Successfully signed in as: {signed_in_user.username or signed_in_user.id}"
            )
            return True

        except SessionPasswordNeededError:
            logger.warning("Two-factor authentication enabled.")
            print("Two-factor authentication enabled.")
            try:
                password = ""
                while not password:
                    try:
                        password = input("Enter your Telegram password (2FA): ")
                    except EOFError:
                        logger.error(
                            "Cannot prompt for 2FA password in non-interactive mode."
                        )
                        return False

                logger.info("Attempting sign-in with 2FA password...")
                signed_in_user = await self.client.sign_in(password=password)
                logger.info(
                    f"Successfully signed in with 2FA as: {signed_in_user.username or signed_in_user.id}"
                )
                print(
                    f"Successfully signed in with 2FA as: {signed_in_user.username or signed_in_user.id}"
                )
                return True
            except Exception as pwd_err:
                logger.error(f"Password sign in failed: {pwd_err}")
                print(f"[ERROR] Password sign in failed: {pwd_err}")
                return False
        except Exception as e:
            logger.error(f"Phone login process failed: {e}", exc_info=True)
            print(f"[ERROR] Phone login process failed: {e}")
            return False

    async def disconnect(self):
        """Disconnects the Telethon client if connected."""
        if self.client and self.client.is_connected():
            logger.info("Disconnecting Telegram client...")
            await self.client.disconnect()
            logger.info("Client disconnected.")
        self.client = None

    async def _ensure_connected(self):
        """Checks if the client is connected and authorized, raises error if not."""
        if not self.client or not self.client.is_connected():
            raise ConnectionError(
                "Telegram client is not connected. Please restart the server or check logs."
            )
        if not self.client.is_user_authorized():
            raise ConnectionError(
                "Telegram client connected but not authorized. Please run --login."
            )

    async def get_login_status(self) -> Dict[str, Any]:
        """Checks the connection and authorization status."""
        session_exists = self.session_path.exists()
        if not self.client:
            return {
                "connected": False,
                "authorized": False,
                "message": f"Client not initialized. Session file {'exists' if session_exists else 'does not exist'}.",
            }

        connected = False
        authorized = False
        user_info = None
        message = "Status check failed."

        try:
            connected = self.client.is_connected()
            if connected:
                authorized = await self.client.is_user_authorized()  # Restore await
                if authorized:
                    me = await self.client.get_me()
                    if me:
                        user_info = {
                            "id": me.id,
                            "username": me.username,
                            "first_name": me.first_name,
                            "last_name": me.last_name,
                        }
                        message = "Client connected and authorized."
                    else:
                        authorized = False
                        message = "Client authorized but failed to get user info. Session may be invalid."
                else:
                    message = "Client connected but not authorized. Login required (run with --login)."
            else:
                message = f"Client not connected. Session file {'exists' if session_exists else 'does not exist'}."
        except Exception as e:
            logger.warning(f"Error checking status: {e}")
            message = f"Error checking status: {str(e)}"
            try:
                connected = (
                    self.client.is_connected() if self.client else False
                )  # Await here
            except:
                connected = False
            authorized = False
            user_info = None

        status = {"connected": connected, "authorized": authorized, "message": message}
        if user_info:
            status["user"] = user_info  # Match schema field name 'user'
        return status

    # --- Wrapper Methods for Tools ---

    async def list_chats(self, limit: int = 100) -> List[Dict]:
        await self._ensure_connected()
        logger.info(f"Listing up to {limit} dialogs...")
        dialogs_data = []
        try:
            async for dialog in self.client.iter_dialogs(limit=limit):
                entity = dialog.entity
                entity_type = "Unknown"
                if isinstance(entity, User):
                    entity_type = "User"
                elif isinstance(entity, Chat):
                    entity_type = "Group"
                elif isinstance(entity, Channel):
                    entity_type = "Channel" if entity.broadcast else "Supergroup"
                dialogs_data.append(
                    {
                        "id": dialog.id,
                        "name": dialog.name,
                        "type": entity_type,
                        "unread_count": dialog.unread_count,
                    }
                )
            logger.info(f"Retrieved {len(dialogs_data)} dialogs.")
            return dialogs_data
        except Exception as e:
            logger.error(f"Failed to list chats: {e}", exc_info=True)
            raise ConnectionError(f"Failed to list chats: {str(e)}")

    async def search_chats(self, query: str) -> List[Dict]:
        await self._ensure_connected()
        logger.info(f"Searching for chats/users matching query: '{query}'")
        results = []
        query_lower = query.lower()
        try:
            async for dialog in self.client.iter_dialogs():
                if dialog.name and query_lower in dialog.name.lower():
                    entity = dialog.entity
                    entity_type = "Unknown"
                    if isinstance(entity, User):
                        entity_type = "User"
                    elif isinstance(entity, Chat):
                        entity_type = "Group"
                    elif isinstance(entity, Channel):
                        entity_type = "Channel" if entity.broadcast else "Supergroup"
                    results.append(
                        {"id": dialog.id, "name": dialog.name, "type": entity_type}
                    )
            logger.info(f"Found {len(results)} chats/users matching query.")
            return results
        except Exception as e:
            logger.error(f"Failed during chat search: {e}", exc_info=True)
            raise ConnectionError(f"Failed during chat search: {str(e)}")

    async def post_message(self, chat_id: Union[int, str], text: str) -> Dict:
        await self._ensure_connected()
        logger.info(f"Sending message to chat_id {chat_id}")
        try:
            message: Message = await self.client.send_message(chat_id, text)
            logger.info(f"Message sent successfully. ID: {message.id}")
            return {
                "message_id": message.id,
                "status": "success",
                "timestamp": message.date.isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}", exc_info=True)
            return {"error": str(e), "status": "failed"}

    async def reply_to_message(
        self, chat_id: Union[int, str], message_id: int, text: str
    ) -> Dict:
        await self._ensure_connected()
        logger.info(f"Replying to message ID {message_id} in chat_id {chat_id}")
        try:
            message: Message = await self.client.send_message(
                chat_id, text, reply_to=message_id
            )
            logger.info(f"Reply sent successfully. ID: {message.id}")
            return {
                "message_id": message.id,
                "status": "success",
                "timestamp": message.date.isoformat(),
            }
        except Exception as e:
            logger.error(
                f"Failed to reply to message {message_id} in {chat_id}: {e}",
                exc_info=True,
            )
            return {"error": str(e), "status": "failed"}

    async def add_reaction(
        self, chat_id: Union[int, str], message_id: int, reaction: str
    ) -> Dict:
        """Adds an emoji reaction to a specific message using raw API."""
        await self._ensure_connected()
        logger.info(
            f"Adding reaction '{reaction}' to message ID {message_id} in chat_id {chat_id}"
        )
        try:
            # Get the input peer entity for the request
            peer = await self.client.get_input_entity(chat_id)

            # Create the raw API request
            # Note: Telethon might require reactions to be wrapped in ReactionEmoji or similar
            # For now, assuming a simple string works, but might need adjustment.
            # Also, the API might expect a list of reactions.
            request = SendReactionRequest(
                peer=peer,
                msg_id=message_id,
                reaction=[
                    types.ReactionEmoji(emoticon=reaction)
                ],  # Wrap in ReactionEmoji
            )
            # Execute the raw API request
            await self.client(request)
            logger.info(f"Reaction '{reaction}' added successfully.")
            return {"status": "success"}
        except Exception as e:
            logger.error(
                f"Failed to add reaction to message {message_id} in {chat_id}: {e}",
                exc_info=True,
            )
            return {"error": str(e), "status": "failed"}

    async def get_chat_history(
        self, chat_id: Union[int, str], limit: int, max_id: Optional[int]
    ) -> List[Dict]:
        await self._ensure_connected()
        logger.info(
            f"Getting {limit} messages from chat_id {chat_id}, ending before ID {max_id or 'latest'}"
        )
        messages_data = []
        try:
            async for message in self.client.iter_messages(
                entity=chat_id, limit=limit, max_id=max_id or 0
            ):
                if isinstance(message, Message):
                    sender_info = {"id": message.sender_id}
                    sender_name = f"User {message.sender_id}"
                    try:
                        sender = await message.get_sender()
                        if sender:
                            sender_name = (
                                getattr(sender, "username", None)
                                or getattr(sender, "title", None)
                                or getattr(sender, "first_name", f"User {sender.id}")
                            )
                    except Exception:
                        logger.warning(
                            f"Could not resolve sender entity for ID {message.sender_id}",
                            exc_info=False,
                        )
                    messages_data.append(
                        {
                            "id": message.id,
                            "text": message.text
                            or f"[Non-text content: {type(message.media).__name__ if message.media else 'None'}]",
                            "sender_id": message.sender_id,
                            "sender_name": sender_name,
                            "timestamp": message.date.isoformat(),
                            "is_reply": message.is_reply,
                            "reply_to_msg_id": message.reply_to_msg_id
                            if message.is_reply
                            else None,
                            "is_outgoing": message.out,
                        }
                    )
            logger.info(f"Retrieved {len(messages_data)} messages.")
            return messages_data
        except Exception as e:
            logger.error(f"Failed to get messages from {chat_id}: {e}", exc_info=True)
            raise ConnectionError(f"Failed to get messages: {str(e)}")

    async def get_user_profile(self, user_id: Union[int, str]) -> Dict:
        await self._ensure_connected()
        logger.info(f"Getting profile for user_id: {user_id}")
        try:
            entity = await self.client.get_entity(user_id)
            if isinstance(entity, User):
                profile_data = {
                    "id": entity.id,
                    "username": entity.username,
                    "first_name": entity.first_name,
                    "last_name": entity.last_name,
                    "phone": entity.phone,
                    "is_bot": entity.bot,
                    "is_contact": entity.contact,
                    "is_mutual_contact": entity.mutual_contact,
                    "status": str(entity.status) if entity.status else None,
                }
                logger.info(
                    f"Retrieved profile for user {entity.username or entity.id}"
                )
                return profile_data
            else:
                logger.warning(
                    f"Entity found for {user_id} is not a User (type: {type(entity).__name__})"
                )
                return {"error": f"ID {user_id} does not correspond to a user."}
        except ValueError:
            logger.error(f"Could not find entity for user_id: {user_id}")
            return {
                "error": f"User with ID/username '{user_id}' not found or inaccessible."
            }
        except Exception as e:
            logger.error(
                f"Failed to get user profile for {user_id}: {e}", exc_info=True
            )
            return {"error": f"An error occurred while fetching profile: {str(e)}"}

    async def search_messages(
        self, query: str, chat_id: Optional[Union[int, str]] = None, limit: int = 20
    ) -> List[Dict]:
        """Searches for messages containing the query text, globally or in a specific chat."""
        await self._ensure_connected()
        search_scope = f"chat_id {chat_id}" if chat_id else "globally"
        logger.info(
            f"Searching up to {limit} messages {search_scope} for query: '{query}'"
        )
        messages_data = []
        try:
            entity = None
            if chat_id:
                try:
                    entity = await self.client.get_entity(chat_id)
                except ValueError:
                    raise ValueError(
                        f"Chat/User with ID/username '{chat_id}' not found or inaccessible."
                    )
                except Exception as e:
                    raise ConnectionError(f"Error resolving entity {chat_id}: {str(e)}")

            async for message in self.client.iter_messages(
                entity=entity, limit=limit, search=query
            ):
                if isinstance(message, Message):
                    sender_info = {"id": message.sender_id}
                    sender_name = f"User {message.sender_id}"
                    try:
                        sender = await message.get_sender()
                        if sender:
                            sender_name = (
                                getattr(sender, "username", None)
                                or getattr(sender, "title", None)
                                or getattr(sender, "first_name", f"User {sender.id}")
                            )
                    except Exception:
                        logger.warning(
                            f"Could not resolve sender entity for ID {message.sender_id}",
                            exc_info=False,
                        )
                    messages_data.append(
                        {
                            "id": message.id,
                            "chat_id": message.chat_id,
                            "text": message.text
                            or f"[Non-text content: {type(message.media).__name__ if message.media else 'None'}]",
                            "sender_id": message.sender_id,
                            "sender_name": sender_name,
                            "timestamp": message.date.isoformat(),
                            "is_reply": message.is_reply,
                            "reply_to_msg_id": message.reply_to_msg_id
                            if message.is_reply
                            else None,
                            "is_outgoing": message.out,
                        }
                    )
            logger.info(f"Retrieved {len(messages_data)} messages matching query.")
            return messages_data
        except Exception as e:
            logger.error(
                f"Failed to search messages ({search_scope}): {e}", exc_info=True
            )
            raise ConnectionError(f"Failed to search messages: {str(e)}")


# --- Login Function (Moved from cli.py) ---
async def run_initial_login() -> bool:
    """Performs the initial blocking login to create the session file. Returns True on success, False on failure."""
    # This function now creates its own wrapper instance for the login process
    print("-" * 60)
    print(" Telegram MCP Server Initial Login ".center(60, "-"))
    print("-" * 60)
    print("\nAttempting Telegram login...")
    # Create a temporary wrapper instance specifically for login
    login_wrapper = TelegramClientWrapper()
    login_successful = False
    try:
        # Call connect on the temporary instance, forcing login if needed
        login_successful = await login_wrapper.connect(perform_login_if_needed=True)
        # Disconnect the temporary client after login attempt
        await login_wrapper.disconnect()
    except Exception as e:
        logger.error(
            f"An unexpected error occurred during initial login: {e}", exc_info=True
        )
        login_successful = False
        # Ensure disconnect even on error
        await login_wrapper.disconnect()

    print("-" * 60)
    if login_successful:
        print("[SUCCESS] Initial login complete!")
        print(f"Telegram session saved to {login_wrapper.session_path}")
    else:
        print("[FAILURE] Initial login failed.")
        print("Please check the logs above for errors.")
        # Access config directly for the path
        print(f"Ensure the data directory exists and is writable: {HOME_DATA_DIR}")
    print("-" * 60)
    return login_successful
