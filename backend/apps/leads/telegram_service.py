import io
import os
import logging
from typing import Optional, Union
from telegram import Bot, InputFile, InputMediaPhoto
from telegram.error import TelegramError
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class TelegramService:
    """Service for interacting with Telegram Bot API."""

    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN', '')
        self.bot = None
        if self.bot_token:
            try:
                self.bot = Bot(token=self.bot_token)
            except Exception as e:
                logger.error(f"Failed to initialize Telegram bot: {e}")

    async def _get_bot(self) -> Optional[Bot]:
        """Get bot instance, checking database config first."""
        # Check database for token
        try:
            from .models import TelegramConfig
            # Use sync_to_async to call database from async context
            config = await sync_to_async(TelegramConfig.get_config)()
            if config and config.bot_token:
                return Bot(token=config.bot_token)
        except Exception as e:
            logger.error(f"Could not get bot from database: {e}", exc_info=True)

        # Fall back to environment variable
        if self.bot:
            return self.bot
        return None

    async def is_configured(self) -> bool:
        """Check if Telegram bot is properly configured (async)."""
        bot = await self._get_bot()
        return bot is not None

    def is_configured_sync(self) -> bool:
        """Check if Telegram bot is configured (sync version for agent)."""
        # Check database for token
        try:
            from .models import TelegramConfig
            config = TelegramConfig.get_config()
            if config and config.bot_token:
                return True
        except Exception:
            pass
        # Fall back to environment variable
        return self.bot is not None

    async def send_message(self, chat_id: str, text: str) -> Optional[dict]:
        """
        Send a message to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            text: Message text (max 4096 characters)

        Returns:
            Message data if successful, None otherwise
        """
        bot = await self._get_bot()
        if not bot:
            logger.error("Telegram bot not configured")
            return None

        try:
            # Trim message if too long
            if len(text) > 4096:
                text = text[:4093] + "..."

            message = await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=None  # Plain text for now
            )

            return {
                'message_id': message.message_id,
                'chat_id': message.chat_id,
                'text': message.text,
                'date': message.date.isoformat() if message.date else None,
            }
        except TelegramError as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
            raise

    async def send_photo(self, chat_id: str, file_source: Union[str, io.BytesIO], caption: str = None) -> Optional[dict]:
        """
        Send a photo file to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            file_source: Absolute path to the image file OR a BytesIO object
            caption: Optional caption text

        Returns:
            Message data if successful, None otherwise
        """
        bot = await self._get_bot()
        if not bot:
            logger.error("Telegram bot not configured")
            return None

        try:
            if isinstance(file_source, (bytes, io.BytesIO)):
                buf = io.BytesIO(file_source) if isinstance(file_source, bytes) else file_source
                buf.seek(0)
                message = await bot.send_photo(
                    chat_id=chat_id,
                    photo=buf,  # pass IO directly — PTB wraps with attach=True
                    caption=caption,
                )
            else:
                with open(file_source, 'rb') as photo_file:
                    message = await bot.send_photo(
                        chat_id=chat_id,
                        photo=photo_file,  # pass IO directly
                        caption=caption,
                    )
            return {
                'message_id': message.message_id,
                'chat_id': message.chat_id,
            }
        except TelegramError as e:
            logger.error(f"Failed to send photo to {chat_id}: {e}")
            raise
        except OSError as e:
            logger.error(f"Failed to read photo file {file_source}: {e}")
            return None

    async def send_document(self, chat_id: str, file_path: str, caption: str = None) -> Optional[dict]:
        """
        Send a document file to a Telegram chat.

        Args:
            chat_id: Telegram chat ID
            file_path: Absolute path to the document file
            caption: Optional caption text

        Returns:
            Message data if successful, None otherwise
        """
        bot = await self._get_bot()
        if not bot:
            logger.error("Telegram bot not configured")
            return None

        try:
            with open(file_path, 'rb') as doc_file:
                message = await bot.send_document(
                    chat_id=chat_id,
                    document=InputFile(doc_file),
                    caption=caption,
                )
            return {
                'message_id': message.message_id,
                'chat_id': message.chat_id,
            }
        except TelegramError as e:
            logger.error(f"Failed to send document to {chat_id}: {e}")
            raise
        except OSError as e:
            logger.error(f"Failed to read document file {file_path}: {e}")
            return None

    async def send_media_group(self, chat_id: str, file_sources: list, caption: str = None) -> Optional[list]:
        """
        Send multiple photos as a Telegram media group (album).

        Args:
            chat_id: Telegram chat ID
            file_sources: List of absolute file paths OR BytesIO objects (2–10 photos)
            caption: Optional caption on the first photo

        Returns:
            List of message dicts if successful, None otherwise
        """
        bot = await self._get_bot()
        if not bot:
            logger.error("Telegram bot not configured")
            return None

        if not file_sources:
            return None

        try:
            # In PTB 22, InputMediaPhoto internally calls parse_file_input(attach=True).
            # Passing a raw IO/bytes object lets PTB create InputFile(attach=True) correctly,
            # setting attach_name so the multipart attachment is properly referenced.
            # Wrapping in InputFile() ourselves (attach=False by default) leaves attach_name=None
            # and causes Telegram to return 400 "Can't parse inputmedia: media not found".
            media = []
            file_handles = []
            for idx, source in enumerate(file_sources):
                if isinstance(source, (bytes, io.BytesIO)):
                    buf = io.BytesIO(source) if isinstance(source, bytes) else source
                    buf.seek(0)
                    file_handles.append(buf)
                    media.append(InputMediaPhoto(
                        media=buf,  # pass IO directly — PTB wraps with attach=True
                        filename=f"photo_{idx}.jpg",
                        caption=caption if idx == 0 else None,
                    ))
                else:
                    fh = open(source, 'rb')
                    file_handles.append(fh)
                    media.append(InputMediaPhoto(
                        media=fh,  # pass IO directly — PTB wraps with attach=True
                        caption=caption if idx == 0 else None,
                    ))

            messages = await bot.send_media_group(chat_id=chat_id, media=media)

            for fh in file_handles:
                fh.close()

            return [{'message_id': m.message_id, 'chat_id': m.chat_id} for m in messages]
        except TelegramError as e:
            logger.error(f"Failed to send media group to {chat_id}: {e}")
            raise
        except OSError as e:
            logger.error(f"Failed to read file for media group: {e}")
            return None

    async def send_chat_action(self, chat_id: str, action: str = 'typing') -> None:
        """
        Send a chat action (e.g. 'typing') to show an activity indicator.

        The indicator is visible for ~5 seconds. Call every 4 seconds to keep
        it showing continuously.
        """
        bot = await self._get_bot()
        if not bot:
            return
        try:
            await bot.send_chat_action(chat_id=chat_id, action=action)
        except TelegramError as e:
            logger.warning(f"Failed to send chat action to {chat_id}: {e}")

    async def get_bot_info(self) -> Optional[dict]:
        """Get information about the bot."""
        bot = await self._get_bot()
        if not bot:
            return None

        try:
            bot_info = await bot.get_me()
            return {
                'id': bot_info.id,
                'username': bot_info.username,
                'first_name': bot_info.first_name,
                'can_read_messages': bot_info.can_read_all_group_messages,
            }
        except TelegramError as e:
            logger.error(f"Failed to get bot info: {e}")
            return None


# Singleton instance
telegram_service = TelegramService()
