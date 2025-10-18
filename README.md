# Try-again-plan
GreenXTrades Copy Trading Telegram Bot

This repository contains a simple Telegram bot that automates the user
onboarding flow for GreenXTrades copy‑trading clients. It follows the
step‑by‑step script outlined in the GreenXTrades Copy Trading Bot
Integration Guide (v2) and provides interactive buttons for
registration, deposit guidance, proof submission, private channel access,
results and support.

Features

Welcome and registration – Greets the user and provides a button to
create an account with the official broker. After registering,
users can tap “Continue” to proceed.

Deposit guide – Explains the minimum deposit (₦100,000) and links to
the deposit guide channel on Telegram. Users can send proof of deposit to
support or indicate they’ve deposited.

Deposit verification – Thanks users for submitting proof and instructs
them to contact support. An optional admin command (/verify) lets
authorized personnel mark a user as verified and send them the private
channel invite.

Exclusive access and results – Once verified, users receive a
placeholder link to the private signal provider channel and can view
public performance via the results channel.

Support – Displays the support handle and customer care number
with operating hours.

24‑hour follow‑up – Schedules a reminder 24 hours after registration if
the user hasn’t deposited yet, encouraging them to fund their account and
providing quick links to the deposit guide and support.

Disclaimer – The bot sends a disclaimer message reminding users that
copy trading involves risk and profits are not guaranteed.

Getting Started

Install the required library (Python 3.9+):

pip install python-telegram-bot


Export your bot token and (optionally) an admin user ID as environment
variables. The admin ID enables the /verify command to grant private
channel access.

export TELEGRAM_BOT_TOKEN=123456:ABCDEF      # replace with your bot token
export ADMIN_ID=123456789                   # Telegram user ID of the admin


Replace the placeholder private_link_placeholder inside
greenxtrades_bot.py with the real invite link to your private signal
provider channel.

Run the bot:

python greenxtrades_bot.py


Open a chat with your bot in Telegram and send /start to begin.

Note on Persistence

This implementation stores user status in memory. In production you
should add persistence (e.g. using PicklePersistence from
python-telegram-bot) so that user progress is retained across restarts.

Disclaimer

Forex and copy trading involve significant risk. GreenXTrades provides
access to professional traders, but profits are not guaranteed. Users
should deposit funds responsibly and understand the risks involved.
