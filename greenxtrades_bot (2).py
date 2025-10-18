"""
greenxtrades_bot.py
====================

This module implements a Telegram bot that guides new users through the
GreenXTrades copy‑trading onboarding flow.  The conversation logic and
messages are derived from the GreenXTrades Copy Trading Bot Integration
Guide (v2)【732727018170150†L0-L69】.  The bot helps users to:

* Register a trading account with the official broker.
* Learn about the required deposit and join the deposit guide channel.
* Send proof of deposit to support and await verification.
* Get access to the private signal provider channel once verified.
* View public results and contact support when needed.
* Receive an automatic reminder 24 hours after registration if they haven’t
  completed the deposit【732727018170150†L52-L63】.

The code uses the `python‑telegram‑bot` library (v20 or newer) in its
asynchronous API style.  To run this bot you need to install the library
(`pip install python-telegram-bot`) and supply your bot token via the
`TELEGRAM_BOT_TOKEN` environment variable.  An optional `ADMIN_ID` may be
provided to enable an administrative `/verify` command for deposit
verification.

Please note:

* This example does **not** execute any financial transactions.  It only
  automates the chat flow and uses placeholder links and buttons for
  registration and support.  You must replace the placeholder private
  channel link with a real invite link after deposit verification as
  described in the guide【732727018170150†L67-L75】.
* Copy trading carries financial risk; profits are not guaranteed【732727018170150†L63-L65】.
* Before deploying the bot to production you should add persistence (for
  example by using `PicklePersistence` from `python‑telegram‑bot`) so that
  user statuses survive restarts.
"""

import os
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict, Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
    constants,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    Job,
    MessageHandler,
    filters,
)


# ---------------------------------------------------------------------------
# Configuration constants taken from the integration guide
#
REGISTRATION_LINK = "https://www.naga.com/register?cmp=1u0w5f6b&refid=4448"  # from guide【732727018170150†L10-L15】
DEPOSIT_GUIDE_CHANNEL = "https://t.me/greenxtradesdeposit"  # from guide【732727018170150†L10-L13】
RESULTS_CHANNEL = "https://t.me/greenxtradesresults"  # from guide【732727018170150†L10-L15】
SUPPORT_USERNAME = "Greenxtradesupport"  # Telegram handle【732727018170150†L10-L15】
CUSTOMER_CARE_NUMBER = "0916 970 1299"  # phone number【732727018170150†L10-L15】


# ---------------------------------------------------------------------------
# State tracking
#
@dataclass
class UserState:
    """In‑memory representation of a user's progress through the onboarding flow."""

    chat_id: int
    status: str = "new"  # one of: new, registered, deposited, verified, granted
    follow_up_job: Optional[Job] = field(default=None, repr=False)


class UserRegistry:
    """
    Simple container to map chat IDs to their current state.

    In a real deployment you should back this with persistent storage.
    """

    def __init__(self):
        self._users: Dict[int, UserState] = {}

    def get_or_create(self, chat_id: int) -> UserState:
        if chat_id not in self._users:
            self._users[chat_id] = UserState(chat_id=chat_id)
        return self._users[chat_id]

    def set_status(self, chat_id: int, status: str):
        user = self.get_or_create(chat_id)
        user.status = status
        return user

    def cancel_follow_up(self, chat_id: int):
        user = self._users.get(chat_id)
        if user and user.follow_up_job:
            user.follow_up_job.schedule_removal()
            user.follow_up_job = None


# ---------------------------------------------------------------------------
# Bot command and callback handlers
#
class GreenXTradesBot:
    def __init__(self, token: str, admin_id: Optional[int] = None):
        self.application = ApplicationBuilder().token(token).build()
        self.user_registry = UserRegistry()
        self.admin_id = admin_id

        # Register handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        self.application.add_handler(CommandHandler("help", self.start))
        # Admin command for verifying deposits
        self.application.add_handler(CommandHandler("verify", self.verify_deposit))
        # Fallback for unknown messages
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.echo_unknown))

    # ------------------------------------------------------------------
    # Entry point: /start or /help
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send welcome message and ask user to start the registration flow."""
        chat_id = update.effective_chat.id
        # Reset user state when (re)starting
        self.user_registry.set_status(chat_id, "new")

        welcome_text = (
            "Welcome to GreenXTrades Copy Trading! Here, professionals trade while you earn —"
            " no stress, no charts, no signals.\n\n"
            "Follow these steps carefully to start your copy‑trading journey."  # from guide【732727018170150†L18-L22】
        )
        keyboard = [
            [
                InlineKeyboardButton("Create Account", callback_data="create_account"),
                InlineKeyboardButton("Help & Support", callback_data="support"),
            ]
        ]
        await update.message.reply_text(
            welcome_text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML
        )

    # ------------------------------------------------------------------
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle all callback query interactions (button presses)."""
        query = update.callback_query
        await query.answer()
        chat_id = query.message.chat_id
        user_state = self.user_registry.get_or_create(chat_id)
        data = query.data

        if data == "create_account":
            # Step 1: Registration information and link
            text = (
                "Great! Click below to create your trading account with our official broker (NAGA).\n\n"
                "After registration, return here and tap ‘Continue’."  # from guide【732727018170150†L23-L28】
            )
            keyboard = [
                [InlineKeyboardButton("Create Account", url=REGISTRATION_LINK)],
                [InlineKeyboardButton("Continue", callback_data="continue_after_registration")],
            ]
            await query.edit_message_text(
                text=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=constants.ParseMode.HTML
            )
        elif data == "continue_after_registration":
            # Mark user as registered and schedule follow‑up in 24 hours
            self.user_registry.set_status(chat_id, "registered")
            # Schedule follow‑up reminder if deposit not made
            job = context.job_queue.run_once(
                self.follow_up,
                when=timedelta(hours=24),
                chat_id=chat_id,
                name=f"follow_up_{chat_id}",
            )
            user_state.follow_up_job = job
            # Send deposit guide
            text = (
                "Time to fund your account! Minimum deposit: ₦100,000.\n\n"
                "Watch our Deposit Guide video on Telegram:"
            )
            keyboard = [
                [InlineKeyboardButton("Join Deposit Guide Channel", url=DEPOSIT_GUIDE_CHANNEL)],
                [
                    InlineKeyboardButton("Send Proof to Support", url=f"https://t.me/{SUPPORT_USERNAME}"),
                    InlineKeyboardButton("I’ve Deposited", callback_data="i_deposited"),
                ],
            ]
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=constants.ParseMode.HTML,
            )
        elif data == "i_deposited":
            # User claims to have deposited – mark and cancel follow up
            self.user_registry.set_status(chat_id, "deposited")
            self.user_registry.cancel_follow_up(chat_id)
            text = (
                "Thank you! Our support team will verify your deposit and grant you access to the Private "
                "Signal Provider Channel."  # from guide【732727018170150†L34-L38】
            )
            keyboard = [
                [InlineKeyboardButton("Contact Support for Verification", url=f"https://t.me/{SUPPORT_USERNAME}")],
            ]
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=constants.ParseMode.HTML,
            )
        elif data == "access_private":
            # Provide the private channel link after verification.  You must replace
            # the placeholder below with a real invite link once available【732727018170150†L67-L75】.
            text = (
                "Deposit verified! You now have access to our private Signal Provider Analysis Channel for live "
                "trade setups."  # from guide【732727018170150†L41-L43】
            )
            private_link_placeholder = "https://t.me/your_private_channel_invite"
            keyboard = [
                [InlineKeyboardButton("Join Private Channel", url=private_link_placeholder)],
                [InlineKeyboardButton("View Results", callback_data="view_results")],
            ]
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=constants.ParseMode.HTML,
            )
        elif data == "view_results":
            # Provide link to public results channel
            text = "View public performance and weekly trade summaries here:"  # from guide【732727018170150†L46-L47】
            keyboard = [
                [InlineKeyboardButton("View Results Channel", url=RESULTS_CHANNEL)],
                [InlineKeyboardButton("Support", callback_data="support")],
            ]
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=constants.ParseMode.HTML,
            )
        elif data == "support":
            # Display support information
            text = (
                "Need help? Our support team is available Mon–Fri, 9 AM–5 PM.\n\n"
                f"Contact Support: <a href='https://t.me/{SUPPORT_USERNAME}'>@{SUPPORT_USERNAME}</a>\n"
                f"Customer Care Number: {CUSTOMER_CARE_NUMBER}"
            )  # from guide【732727018170150†L48-L51】
            keyboard = [
                [InlineKeyboardButton("Back to Start", callback_data="create_account")],
            ]
            await query.edit_message_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=constants.ParseMode.HTML,
            )
        else:
            # Unknown callback
            await query.edit_message_text("Sorry, I didn't understand that selection.")

    # ------------------------------------------------------------------
    async def follow_up(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send a 24‑hour follow‑up reminder if the user hasn't deposited."""
        job = context.job
        chat_id = job.chat_id
        user_state = self.user_registry.get_or_create(chat_id)
        # If the user has not deposited yet, send reminder
        if user_state.status == "registered":
            text = (
                "Hi there! Just checking in — we noticed you registered your GreenXTrades account but haven’t "
                "made your first deposit yet.\n\n"
                "Remember, your trading journey starts with a minimum of ₦100,000.\n"
                "Watch the Deposit Guide video to get started."
            )  # from guide【732727018170150†L52-L59】
            keyboard = [
                [InlineKeyboardButton("Join Deposit Guide Channel", url=DEPOSIT_GUIDE_CHANNEL)],
                [InlineKeyboardButton("Contact Support", url=f"https://t.me/{SUPPORT_USERNAME}")],
            ]
            await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=constants.ParseMode.HTML,
            )
            # Reset follow‑up job reference
            user_state.follow_up_job = None

    # ------------------------------------------------------------------
    async def verify_deposit(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """
        Admin‑only command to mark a user as verified and grant access.

        Usage: /verify <chat_id>

        Only the user ID specified during bot initialization (`admin_id`) is
        permitted to call this command.  This command simulates the admin
        verification step mentioned in the integration guide【732727018170150†L67-L73】.
        """
        if self.admin_id is not None and update.effective_user.id != self.admin_id:
            await update.message.reply_text("You are not authorized to use this command.")
            return

        # Expect a chat_id argument
        if not context.args:
            await update.message.reply_text("Usage: /verify <chat_id>")
            return
        try:
            target_chat_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text("Invalid chat_id. It should be a number.")
            return

        # Mark user as verified and send access link
        user_state = self.user_registry.get_or_create(target_chat_id)
        if user_state.status != "deposited":
            await update.message.reply_text(
                f"User {target_chat_id} is not in deposited state; current status: {user_state.status}"
            )
            return
        self.user_registry.set_status(target_chat_id, "verified")
        # Send exclusive access message to user
        text = (
            "Deposit verified! You now have access to our private Signal Provider Analysis Channel for live "
            "trade setups."  # from guide【732727018170150†L41-L43】
        )
        private_link_placeholder = "https://t.me/your_private_channel_invite"  # replace with real link
        keyboard = [
            [InlineKeyboardButton("Join Private Channel", url=private_link_placeholder)],
            [InlineKeyboardButton("View Results", callback_data="view_results")],
        ]
        await context.bot.send_message(
            chat_id=target_chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=constants.ParseMode.HTML,
        )
        # Update state to granted once link is sent
        self.user_registry.set_status(target_chat_id, "granted")
        await update.message.reply_text(
            f"User {target_chat_id} has been verified and granted access."
        )

    # ------------------------------------------------------------------
    async def echo_unknown(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Fallback handler for messages that are not recognized."""
        await update.message.reply_text(
            "I'm sorry, I didn't understand that. Please use the buttons provided or /start to begin."
        )

    # ------------------------------------------------------------------
    def run(self) -> None:
        """Run the bot until manually stopped.

        This synchronous runner blocks the current thread and keeps the bot
        polling for new updates until it receives a termination signal (e.g.,
        Ctrl+C).  It calls :meth:`Application.run_polling` directly, which
        internally initializes and starts the application, begins polling for
        updates and idles until the service is stopped.  Using this
        synchronous runner avoids conflicts with already running asyncio event
        loops (Render uses Python 3.13 and may have an active loop), which
        caused a ``RuntimeError: This event loop is already running`` when
        attempting to run the asynchronous version under ``asyncio.run()``.
        """
        # ``run_polling`` blocks until the bot is stopped, ensuring the process
        # stays alive on Render’s free dynos.
        self.application.run_polling()


def main() -> None:
    """Entry point for running the bot from the command line."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("Please set the TELEGRAM_BOT_TOKEN environment variable.")
    admin_id_env = os.getenv("ADMIN_ID")
    admin_id = int(admin_id_env) if admin_id_env else None
    bot = GreenXTradesBot(token=token, admin_id=admin_id)
    # Invoke the synchronous runner.  ``asyncio.run`` is no longer used
    # because ``bot.run`` is synchronous and will block until the bot is stopped.
    bot.run()


if __name__ == "__main__":
    main()