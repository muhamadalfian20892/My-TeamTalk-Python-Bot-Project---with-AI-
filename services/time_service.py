from datetime import datetime
import logging

try:
    import pytz
    TIME_LIBS_AVAILABLE = True
except ImportError:
    TIME_LIBS_AVAILABLE = False

class TimeService:
    def __init__(self):
        self._enabled = TIME_LIBS_AVAILABLE
        if not self._enabled:
            logging.warning("Time library (pytz) not found. Time command will be disabled.")

    def is_enabled(self):
        return self._enabled

    def get_time_for_location(self, location_name: str) -> str:
        if not self.is_enabled():
            return "[Bot] Time feature is disabled (required 'pytz' library not installed)."
        
        # A simple approach to find a timezone without heavy dependencies.
        # It works for major cities and timezone identifiers.
        search_str = location_name.replace(" ", "_").lower()
        
        # Prioritize exact matches like "UTC", "GMT"
        if search_str.upper() in pytz.all_timezones_set:
            found_tzs = [search_str.upper()]
        else:
            found_tzs = [tz for tz in pytz.all_timezones if search_str in tz.lower()]
        
        if not found_tzs:
            return f"[Time] Could not find a timezone for '{location_name}'."
        
        # Try to find a more specific match (e.g., 'london' -> 'Europe/London')
        exact_match = next((tz for tz in found_tzs if tz.lower().endswith(f'/{search_str}')), None)
        
        target_tz_str = exact_match or found_tzs[0]
        
        try:
            target_tz = pytz.timezone(target_tz_str)
            local_time = datetime.now(target_tz)
            time_str = local_time.strftime('%Y-%m-%d %H:%M:%S %Z (%z)')
            
            # Clean up the display name
            display_name = target_tz_str.replace('_', ' ').split('/')[-1]
            return f"The current time in {display_name} is: {time_str}"
        except pytz.UnknownTimeZoneError:
            # This case should be rare due to the pre-check, but for safety
            return f"[Time] Could not resolve timezone for '{location_name}'."
        except Exception as e:
            logging.error(f"Error getting time for {location_name} ({target_tz_str}): {e}")
            return "[Time] An unexpected error occurred."