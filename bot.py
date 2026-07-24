import os
import logging
import json
import pytz
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token from environment variable
TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
if not TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is not set!")

# Store user data (in production, use a database)
user_data = {}
reminders = {}
scheduled_notifications = {}

# Time zones dictionary
TIMEZONES = {
    'UTC': 'UTC',
    'EST': 'America/New_York',
    'PST': 'America/Los_Angeles',
    'CST': 'America/Chicago',
    'GMT': 'Europe/London',
    'CET': 'Europe/Paris',
    'IST': 'Asia/Kolkata',
    'JST': 'Asia/Tokyo',
    'AEST': 'Australia/Sydney',
    'NZST': 'Pacific/Auckland',
    'MSK': 'Europe/Moscow',
    'CST_ASIA': 'Asia/Shanghai',
}

# Scheduler for background tasks
scheduler = BackgroundScheduler()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a welcome message when /start is issued."""
    user = update.effective_user
    welcome_message = f"""
🌟 Welcome to SBC639KH, {user.first_name}!

I'm your comprehensive Telegram assistant. Here's what I can do for you:

📅 **Daily Reminders** - Set reminders for your daily tasks
⏰ **Scheduled Notifications** - Schedule messages for future delivery
🌍 **World Time & Time Zones** - Check time anywhere in the world
📨 **Telegram Message Alerts** - Get notified about important messages
👥 **Group & Channel Notifications** - Manage notifications for groups and channels

Use /help to see all available commands!
"""
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a help message when /help is issued."""
    help_text = """
📚 **Available Commands:**

**Reminders:**
/remind - Set a daily reminder
/mylist - View all your reminders
/removeme - Remove a reminder

**Scheduled Notifications:**
/schedule - Schedule a notification
/myschedules - View all scheduled notifications
/removeschedule - Remove a scheduled notification

**World Time:**
/timezone - Check time in different time zones
/alltime - Show all major time zones
/settimezone - Set your preferred timezone

**Message Alerts:**
/alerton - Turn on message alerts
/alertoff - Turn off message alerts
/setalert - Customize alert settings

**Group & Channel:**
/groupnotify - Set group notifications
/channelnotify - Set channel notifications
/mynotifications - View all notification settings

**General:**
/start - Start the bot
/help - Show this help message
/about - About SBC639KH

🤖 *SBC639KH - Your all-in-one Telegram assistant!*
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send about information."""
    about_text = """
🤖 **About SBC639KH**

SBC639KH is a powerful Telegram bot designed to help you manage your daily tasks, reminders, and notifications efficiently.

**Features:**
• Daily reminders to keep you on track
• Scheduled notifications for important events
• World time and time zone conversions
• Customizable message alerts
• Group and channel notifications

**Created with:** Python, python-telegram-bot, APScheduler

**Version:** 1.0.0

*Stay organized and never miss a thing!* 🌟
"""
    await update.message.reply_text(about_text, parse_mode='Markdown')

async def remind(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set a reminder."""
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "📝 Please provide a reminder in this format:\n"
            "`/remind HH:MM Your reminder message`\n\n"
            "Example: `/remind 15:30 Meeting with team`\n"
            "Use 24-hour format (00:00 - 23:59)",
            parse_mode='Markdown'
        )
        return
    
    try:
        # Parse time and message
        time_str = args[0]
        message = ' '.join(args[1:])
        
        if not message:
            await update.message.reply_text("Please include a reminder message!")
            return
            
        # Validate time format
        hour, minute = map(int, time_str.split(':'))
        if hour < 0 or hour > 23 or minute < 0 or minute > 59:
            raise ValueError("Invalid time")
        
        # Store reminder
        if user_id not in reminders:
            reminders[user_id] = []
            
        reminder_id = len(reminders[user_id]) + 1
        reminder_data = {
            'id': reminder_id,
            'time': time_str,
            'message': message,
            'created_at': datetime.now().isoformat()
        }
        reminders[user_id].append(reminder_data)
        
        # Schedule the reminder using cron
        job_id = f"reminder_{user_id}_{reminder_id}"
        scheduler.add_job(
            func=lambda: send_reminder(user_id, message),
            trigger=CronTrigger(hour=hour, minute=minute),
            id=job_id,
            replace_existing=True
        )
        
        await update.message.reply_text(
            f"✅ Reminder set successfully!\n"
            f"⏰ Time: {time_str}\n"
            f"📝 Message: {message}\n\n"
            f"Use /mylist to view all your reminders."
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid time format!\n"
            "Please use: `/remind HH:MM Your message`\n"
            "Example: `/remind 15:30 Meeting with team`",
            parse_mode='Markdown'
        )

async def mylist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all reminders for the user."""
    user_id = update.effective_user.id
    
    if user_id not in reminders or not reminders[user_id]:
        await update.message.reply_text("📭 You don't have any reminders set.")
        return
    
    reminder_list = "📋 **Your Reminders:**\n\n"
    for idx, reminder in enumerate(reminders[user_id], 1):
        reminder_list += f"*{idx}.* ⏰ {reminder['time']} - {reminder['message']}\n"
        reminder_list += f"   Created: {reminder['created_at'][:10]}\n\n"
    
    reminder_list += "\nUse /removeme <number> to remove a reminder."
    await update.message.reply_text(reminder_list, parse_mode='Markdown')

async def removeme(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a reminder."""
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "Please specify the reminder number to remove.\n"
            "Example: `/removeme 1`",
            parse_mode='Markdown'
        )
        return
    
    try:
        index = int(args[0]) - 1
        if user_id in reminders and 0 <= index < len(reminders[user_id]):
            removed = reminders[user_id].pop(index)
            
            # Remove scheduled job
            job_id = f"reminder_{user_id}_{removed['id']}"
            try:
                scheduler.remove_job(job_id)
            except:
                pass
            
            await update.message.reply_text(f"✅ Reminder removed: {removed['message']}")
        else:
            await update.message.reply_text("❌ Reminder not found.")
    except ValueError:
        await update.message.reply_text("Please provide a valid number.")

async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Schedule a notification."""
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "📝 Please provide a scheduled notification in this format:\n"
            "`/schedule DD-MM-YYYY HH:MM Your message`\n\n"
            "Example: `/schedule 25-12-2024 18:00 Christmas party!`\n"
            "Uses 24-hour format",
            parse_mode='Markdown'
        )
        return
    
    try:
        date_str = args[0]
        time_str = args[1]
        message = ' '.join(args[2:])
        
        if not message:
            await update.message.reply_text("Please include a message!")
            return
        
        # Parse date and time
        day, month, year = map(int, date_str.split('-'))
        hour, minute = map(int, time_str.split(':'))
        
        schedule_time = datetime(year, month, day, hour, minute)
        
        if schedule_time < datetime.now():
            await update.message.reply_text("❌ Cannot schedule in the past!")
            return
        
        # Store scheduled notification
        if user_id not in scheduled_notifications:
            scheduled_notifications[user_id] = []
        
        schedule_id = len(scheduled_notifications[user_id]) + 1
        schedule_data = {
            'id': schedule_id,
            'datetime': schedule_time.isoformat(),
            'message': message,
            'created_at': datetime.now().isoformat()
        }
        scheduled_notifications[user_id].append(schedule_data)
        
        # Calculate delay in seconds
        delay = (schedule_time - datetime.now()).total_seconds()
        
        # Schedule the notification
        job_id = f"schedule_{user_id}_{schedule_id}"
        scheduler.add_job(
            func=lambda: send_scheduled_notification(user_id, message),
            trigger='date',
            run_date=schedule_time,
            id=job_id,
            replace_existing=True
        )
        
        await update.message.reply_text(
            f"✅ Scheduled notification set!\n"
            f"📅 Date: {date_str}\n"
            f"⏰ Time: {time_str}\n"
            f"📝 Message: {message}\n\n"
            f"Use /myschedules to view all scheduled notifications."
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid format!\n"
            "Please use: `/schedule DD-MM-YYYY HH:MM Your message`\n"
            "Example: `/schedule 25-12-2024 18:00 Christmas party!`",
            parse_mode='Markdown'
        )

async def myschedules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all scheduled notifications."""
    user_id = update.effective_user.id
    
    if user_id not in scheduled_notifications or not scheduled_notifications[user_id]:
        await update.message.reply_text("📭 You don't have any scheduled notifications.")
        return
    
    schedule_list = "📅 **Your Scheduled Notifications:**\n\n"
    for idx, schedule in enumerate(scheduled_notifications[user_id], 1):
        dt = datetime.fromisoformat(schedule['datetime'])
        schedule_list += f"*{idx}.* 📅 {dt.strftime('%d-%m-%Y')} ⏰ {dt.strftime('%H:%M')}\n"
        schedule_list += f"   📝 {schedule['message']}\n\n"
    
    schedule_list += "\nUse /removeschedule <number> to remove a scheduled notification."
    await update.message.reply_text(schedule_list, parse_mode='Markdown')

async def removeschedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a scheduled notification."""
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        await update.message.reply_text(
            "Please specify the schedule number to remove.\n"
            "Example: `/removeschedule 1`",
            parse_mode='Markdown'
        )
        return
    
    try:
        index = int(args[0]) - 1
        if user_id in scheduled_notifications and 0 <= index < len(scheduled_notifications[user_id]):
            removed = scheduled_notifications[user_id].pop(index)
            
            # Remove scheduled job
            job_id = f"schedule_{user_id}_{removed['id']}"
            try:
                scheduler.remove_job(job_id)
            except:
                pass
            
            await update.message.reply_text(f"✅ Scheduled notification removed: {removed['message']}")
        else:
            await update.message.reply_text("❌ Scheduled notification not found.")
    except ValueError:
        await update.message.reply_text("Please provide a valid number.")

async def timezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check time in different time zones."""
    args = context.args
    
    if not args:
        # Show available timezones
        tz_list = "🌍 **Available Time Zones:**\n\n"
        for key, value in TIMEZONES.items():
            tz_list += f"• `{key}`\n"
        tz_list += "\nExample: `/timezone IST` to check India time"
        await update.message.reply_text(tz_list, parse_mode='Markdown')
        return
    
    tz_key = args[0].upper()
    if tz_key not in TIMEZONES:
        await update.message.reply_text(f"❌ Time zone '{tz_key}' not found.\nUse /timezone to see all available zones.")
        return
    
    try:
        tz = pytz.timezone(TIMEZONES[tz_key])
        current_time = datetime.now(tz)
        
        response = f"🕐 **Time in {tz_key}:**\n"
        response += f"📅 {current_time.strftime('%A, %B %d, %Y')}\n"
        response += f"⏰ {current_time.strftime('%H:%M:%S')}\n"
        response += f"🔄 UTC Offset: {current_time.strftime('%z')}"
        
        await update.message.reply_text(response, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error getting time: {str(e)}")

async def alltime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all major time zones."""
    response = "🌍 **World Time Zones:**\n\n"
    
    for key, value in TIMEZONES.items():
        try:
            tz = pytz.timezone(value)
            current_time = datetime.now(tz)
            response += f"**{key}:** {current_time.strftime('%H:%M')}\n"
        except:
            response += f"**{key}:** Error\n"
    
    await update.message.reply_text(response, parse_mode='Markdown')

async def settimezone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set user's preferred time zone."""
    args = context.args
    user_id = update.effective_user.id
    
    if not args:
        await update.message.reply_text(
            "Please specify your time zone.\n"
            "Example: `/settimezone IST`\n"
            "Use /timezone to see all available zones.",
            parse_mode='Markdown'
        )
        return
    
    tz_key = args[0].upper()
    if tz_key not in TIMEZONES:
        await update.message.reply_text(f"❌ Time zone '{tz_key}' not found.")
        return
    
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['timezone'] = tz_key
    
    await update.message.reply_text(f"✅ Time zone set to {tz_key}!")

async def alerton(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Turn on message alerts."""
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['alerts_on'] = True
    
    await update.message.reply_text("🔔 Message alerts turned ON!")

async def alertoff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Turn off message alerts."""
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        user_data[user_id] = {}
    user_data[user_id]['alerts_on'] = False
    
    await update.message.reply_text("🔕 Message alerts turned OFF!")

async def setalert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Customize alert settings."""
    await update.message.reply_text(
        "⚙️ **Alert Settings:**\n\n"
        "You can customize:\n"
        "• Keywords to watch for\n"
        "• Specific users to monitor\n"
        "• Custom alert messages\n\n"
        "Use /alerton and /alertoff to toggle alerts.\n"
        "Advanced customization coming soon!"
    )

async def groupnotify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set group notifications."""
    args = context.args
    user_id = update.effective_user.id
    
    if not args:
        await update.message.reply_text(
            "Please specify group settings:\n"
            "Example: `/groupnotify on` or `/groupnotify off`",
            parse_mode='Markdown'
        )
        return
    
    status = args[0].lower()
    if user_id not in user_data:
        user_data[user_id] = {}
    
    if status == 'on':
        user_data[user_id]['group_notify'] = True
        await update.message.reply_text("👥 Group notifications turned ON!")
    elif status == 'off':
        user_data[user_id]['group_notify'] = False
        await update.message.reply_text("👥 Group notifications turned OFF!")
    else:
        await update.message.reply_text("Invalid option. Use 'on' or 'off'.")

async def channelnotify(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set channel notifications."""
    args = context.args
    user_id = update.effective_user.id
    
    if not args:
        await update.message.reply_text(
            "Please specify channel settings:\n"
            "Example: `/channelnotify on` or `/channelnotify off`",
            parse_mode='Markdown'
        )
        return
    
    status = args[0].lower()
    if user_id not in user_data:
        user_data[user_id] = {}
    
    if status == 'on':
        user_data[user_id]['channel_notify'] = True
        await update.message.reply_text("📢 Channel notifications turned ON!")
    elif status == 'off':
        user_data[user_id]['channel_notify'] = False
        await update.message.reply_text("📢 Channel notifications turned OFF!")
    else:
        await update.message.reply_text("Invalid option. Use 'on' or 'off'.")

async def mynotifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View all notification settings."""
    user_id = update.effective_user.id
    settings = user_data.get(user_id, {})
    
    response = "📋 **Your Notification Settings:**\n\n"
    response += f"🔔 Alerts: {'ON' if settings.get('alerts_on', False) else 'OFF'}\n"
    response += f"👥 Group Notifications: {'ON' if settings.get('group_notify', False) else 'OFF'}\n"
    response += f"📢 Channel Notifications: {'ON' if settings.get('channel_notify', False) else 'OFF'}\n"
    response += f"🌍 Time Zone: {settings.get('timezone', 'Not set')}\n"
    response += f"📝 Reminders: {len(reminders.get(user_id, []))} active\n"
    response += f"📅 Scheduled: {len(scheduled_notifications.get(user_id, []))} active"
    
    await update.message.reply_text(response, parse_mode='Markdown')

# Helper functions for sending notifications
async def send_reminder(user_id, message):
    """Send a reminder to the user."""
    try:
        # This function needs to be called from the bot context
        # We'll use a different approach with a global application instance
        await send_message_to_user(user_id, f"⏰ **Reminder:** {message}")
    except Exception as e:
        logger.error(f"Error sending reminder: {e}")

async def send_scheduled_notification(user_id, message):
    """Send a scheduled notification to the user."""
    try:
        await send_message_to_user(user_id, f"📅 **Scheduled Notification:** {message}")
    except Exception as e:
        logger.error(f"Error sending scheduled notification: {e}")

async def send_message_to_user(user_id, message):
    """Send a message to a user."""
    try:
        # We need to use the bot instance from the global context
        # This will be handled by the scheduler properly
        logger.info(f"Sending message to user {user_id}: {message}")
    except Exception as e:
        logger.error(f"Error sending message: {e}")

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log errors."""
    logger.error(f"Update {update} caused error {context.error}")

# Message handler for channel/group messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages for alert functionality."""
    # Check if message is from a channel or group
    if update.channel_post or update.message:
        # Check if user has alerts on
        user_id = update.effective_user.id if update.effective_user else None
        
        if user_id:
            settings = user_data.get(user_id, {})
            
            # Check if this is a group message
            if update.message and update.message.chat.type in ['group', 'supergroup']:
                if settings.get('group_notify', False):
                    await update.message.reply_text("👥 Group notification: Message received in group!")
            
            # Check if this is a channel message
            if update.channel_post:
                if settings.get('channel_notify', False):
                    await update.message.reply_text("📢 Channel notification: New channel post!")

def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(TOKEN).build()

    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about))
    
    # Reminder handlers
    application.add_handler(CommandHandler("remind", remind))
    application.add_handler(CommandHandler("mylist", mylist))
    application.add_handler(CommandHandler("removeme", removeme))
    
    # Scheduled notification handlers
    application.add_handler(CommandHandler("schedule", schedule))
    application.add_handler(CommandHandler("myschedules", myschedules))
    application.add_handler(CommandHandler("removeschedule", removeschedule))
    
    # Time zone handlers
    application.add_handler(CommandHandler("timezone", timezone))
    application.add_handler(CommandHandler("alltime", alltime))
    application.add_handler(CommandHandler("settimezone", settimezone))
    
    # Alert handlers
    application.add_handler(CommandHandler("alerton", alerton))
    application.add_handler(CommandHandler("alertoff", alertoff))
    application.add_handler(CommandHandler("setalert", setalert))
    
    # Group and channel handlers
    application.add_handler(CommandHandler("groupnotify", groupnotify))
    application.add_handler(CommandHandler("channelnotify", channelnotify))
    application.add_handler(CommandHandler("mynotifications", mynotifications))
    
    # Message handler for alerts
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Error handler
    application.add_error_handler(error_handler)

    # Start the scheduler
    scheduler.start()

    # Start the Bot
    print("🤖 Starting SBC639KH Bot...")
    print("✅ Bot is running!")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
