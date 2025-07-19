import logging
import re
import datetime

try:
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False

# --- Global objects to solve the pickling issue ---
# The scheduler and bot reference are kept at the module level.
# This prevents the scheduler from trying to pickle the live bot instance,
# which contains un-pickleable thread locks.
_scheduler = None
_bot_ref = None

def _send_reminder_job(user_id, message):
    """
    This is the actual function the scheduler calls.
    It's a top-level function, so it doesn't have a 'self' and is easily pickled.
    It uses the global _bot_ref to access the live bot instance when it runs.
    """
    global _bot_ref
    try:
        if _bot_ref and _bot_ref._logged_in:
            _bot_ref._send_pm(user_id, f"[Reminder] {message}")
            logging.info(f"Sent reminder to user_id {user_id}.")
        elif _bot_ref:
            logging.warning(f"Could not send reminder to user_id {user_id}: Bot is not logged in.")
        else:
            logging.error(f"Could not send reminder to user_id {user_id}: Bot reference is not set.")
    except Exception as e:
        logging.error(f"Failed to send reminder to user_id {user_id}: {e}")

# ----------------------------------------------------

class ReminderService:
    def __init__(self, bot_instance):
        global _scheduler, _bot_ref
        _bot_ref = bot_instance  # Set the global reference to the live bot
        self._enabled = SCHEDULER_AVAILABLE
        
        if not self.is_enabled():
            logging.warning("ReminderService disabled: 'apscheduler' or 'sqlalchemy' not found.")
            return

        # Initialize the scheduler only once
        if _scheduler is None:
            jobstores = {
                'default': SQLAlchemyJobStore(url='sqlite:///reminders.sqlite')
            }
            _scheduler = BackgroundScheduler(jobstores=jobstores)
            logging.info("ReminderService initialized with persistent job store.")

    def is_enabled(self):
        return self._enabled

    def start(self):
        if self.is_enabled() and _scheduler and not _scheduler.running:
            _scheduler.start()
            logging.info("Reminder scheduler started.")

    def shutdown(self):
        if self.is_enabled() and _scheduler and _scheduler.running:
            _scheduler.shutdown()
            logging.info("Reminder scheduler shut down.")

    def parse_and_add_reminder(self, user_id: int, reminder_str: str) -> str:
        """
        Parses the user's reminder string and adds a job to the scheduler.
        Expected format: "message" in <number> <unit>
        """
        if not self.is_enabled():
            return "[Bot] Reminder feature is disabled (required libraries not installed)."

        # Regex to capture the message and the time components
        match = re.match(r'^\s*"(.+?)"\s+in\s+(\d+)\s+(minutes?|hours?|days?)\s*$', reminder_str, re.IGNORECASE)

        if not match:
            return 'Usage: remindme "Your message here" in <number> <unit> (e.g., 5 minutes, 1 hour, 2 days).'

        message, number_str, unit = match.groups()
        number = int(number_str)

        # Calculate the timedelta
        if 'minute' in unit:
            delta = datetime.timedelta(minutes=number)
        elif 'hour' in unit:
            delta = datetime.timedelta(hours=number)
        elif 'day' in unit:
            delta = datetime.timedelta(days=number)
        else:
            return "Invalid time unit. Please use 'minutes', 'hours', or 'days'."

        run_time = datetime.datetime.now() + delta

        try:
            _scheduler.add_job(
                _send_reminder_job,  # Schedule the pickle-safe, top-level function
                'date',
                run_date=run_time,
                args=[user_id, message],
                id=f"reminder_{user_id}_{run_time.timestamp()}",
                misfire_grace_time=3600
            )
            logging.info(f"Scheduled reminder for user_id {user_id} at {run_time.strftime('%Y-%m-%d %H:%M:%S')}")
            return f"OK, I will remind you to '{message}' in {number} {unit}."
        except Exception as e:
            logging.error(f"Failed to schedule reminder: {e}", exc_info=True)
            return "[Bot Error] Could not schedule the reminder."