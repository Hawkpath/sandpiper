__all__ = [
    "UserTimezoneUnset",
    "TimezoneNotFound",
    "LocalizedTimes",
    "TimeConversion",
    "TimeConversionOutput",
    "convert_time_to_user_timezones",
]

from collections import defaultdict
from collections.abc import Iterable
import datetime as dt
import logging
from typing import Optional, Union, cast

from attr import Factory, define
import discord

from sandpiper.common.misc import RuntimeMessages
from sandpiper.common.time import *
from sandpiper.components.conversion.raw_quantity import RawQuantity
from sandpiper.components.user_data import Database

logger = logging.getLogger(__name__)


class UserTimezoneUnset(Exception):
    def __str__(self):
        return (
            "Your timezone is not set. Use the `help timezone set` command "
            "for more info."
        )


class TimezoneNotFound(Exception):
    def __init__(self, timezone: str):
        self.timezone = timezone

    def __str__(self):
        return f'Timezone "{self.timezone}" not found'


@define
class LocalizedTimes:
    timezone_name: str
    datetimes: list[dt.datetime] = Factory(list)


@define
class TimeConversion:
    input_timezone_name: str | None
    localized_times: list[LocalizedTimes] = Factory(list)


@define
class TimeConversionOutput:
    conversions: list[TimeConversion] = Factory(list)
    # Strings that should pass on to unit conversion
    failed: list[RawQuantity] = Factory(list)


def _get_timezone(name: str) -> Optional[TimezoneType]:
    """
    Get the timezone that best matches this name. May return None if the fuzzy
    search score is less than 50.
    """
    matches = fuzzy_match_timezone(name, best_match_threshold=50, limit=1)
    return matches.best_match or None


async def _get_guild_timezones(db: Database, guild: discord.Guild) -> set[TimezoneType]:
    """
    Get all user timezones from the given guild.

    :param db: the Database to get user data from
    :param guild: the guild to limit the search to
    :return: a set of user timezones in this guild
    """
    all_timezones = await db.get_all_timezones()
    return {
        # Filter out timezones of users outside this guild
        tz
        for user_id, tz in all_timezones
        if guild.get_member(user_id)
    }


async def _convert_times(
    times: list[dt.datetime], out_timezones: Union[TimezoneType, Iterable[TimezoneType]]
) -> list[LocalizedTimes]:
    """
    Convert a list of datetimes to the given timezones.

    :param times: a list of timezone-aware datetimes to convert
    :param out_timezones: one or more timezones to convert each datetime to
    :return: a list of tuples of (timezone_name, converted_times), where
        ``converted_times`` is a list of datetimes converted to that timezone
    """
    if isinstance(out_timezones, TimezoneType.__args__):
        out_timezones = (out_timezones,)

    localized_times: list[LocalizedTimes] = []
    for tz in out_timezones:
        times = [time.astimezone(tz) for time in times]
        localized_times.append(LocalizedTimes(tz.zone, times))
    localized_times.sort(key=lambda c: cast(LocalizedTimes, c).datetimes[0].utcoffset())
    return localized_times


T_TimeConversions = dict[TimezoneType | None, list[dt.datetime]]


async def _parse_input(
    db: Database,
    user_id: int,
    raw_quantities: list[RawQuantity],
    runtime_msgs: RuntimeMessages,
    conversion_output: TimeConversionOutput,
) -> T_TimeConversions:
    """
    Attempt to parse the strings as times and populate success and failure
    lists accordingly

    :param db: the Database adapter for getting user timezones
    :param user_id: the id of the user asking for a time conversion
    :param raw_quantities: a list of `RawQuantity`s that may be valid times
    :param runtime_msgs: a collection of messages that were generated during
        runtime. These may be reported back to the user.
    :param conversion_output: the container for conversion output
    :return: a dict mapping timezone keys to datetimes
    """
    time_conversions: T_TimeConversions = defaultdict(list)
    user_tz = None
    for raw_quantity in raw_quantities:
        time_raw = raw_quantity.quantity
        timezone_out_str = raw_quantity.suffix

        try:
            parsed_time, timezone_in_str, definitely_time = parse_time(time_raw)
        except ValueError as e:
            logger.info(
                f"Failed to parse time string (string={time_raw!r}, reason={e})"
            )
            # Failed to parse as a time, so pass it on to unit conversion
            conversion_output.failed.append(RawQuantity(time_raw, timezone_out_str))
            continue
        except Exception:
            logger.warning(
                f"Unhandled exception while parsing time string "
                f"(string={time_raw!r})",
                exc_info=True,
            )
            continue

        # Input timezone stuff

        if timezone_in_str is None:
            # Use the user's timezone; only get it once in the loop
            if user_tz is None and (user_tz := await db.get_timezone(user_id)) is None:
                runtime_msgs.add_type_once(UserTimezoneUnset())
            timezone_in = user_tz
        # Try to parse input timezone
        elif (timezone_in := _get_timezone(timezone_in_str)) is None:
            # User supplied a source timezone and we matched timezone_in, so
            # we already know time_raw is definitely a time
            runtime_msgs += TimezoneNotFound(timezone_in_str)
            continue

        # Output timezone stuff

        if not timezone_out_str:
            timezone_out = None
        # Try to parse output timezone
        elif (timezone_out := _get_timezone(timezone_out_str)) is None:
            if definitely_time:
                # We know this is a time, so this unfound timezone should
                # be reported and not passed on to unit conversion
                runtime_msgs += TimezoneNotFound(timezone_out_str)
            else:
                # This might be a unit
                conversion_output.failed.append(RawQuantity(time_raw, timezone_out_str))

        # Do stuff with our parsed data
        local_dt = localize_time_to_datetime(parsed_time, timezone_in)
        time_conversions[timezone_out].append(local_dt)

    return time_conversions


async def _do_conversions(
    db: Database,
    guild: discord.Guild,
    time_conversions: T_TimeConversions,
    conversion_output: TimeConversionOutput,
) -> None:
    """
    Mutate `conversion_output` with converted times

    :param db: the Database adapter for getting user timezones
    :param guild: the guild the conversion is occurring in
    :param time_conversions: a dict mapping timezone keys to datetimes. Each
        datetime under a given timezone will be converted to that timezone
        only. The None key is a special case, where each datetime it maps to
        will be converted to all user timezones in the database.
    :param conversion_output: the container for conversion output
    """
    for timezone_out, times in time_conversions.items():
        if not times:
            continue

        if timezone_out is None:
            # No specific output timezone, so use all the timezones in the guild
            converted = await _convert_times(
                times, await _get_guild_timezones(db, guild)
            )
            assert len(time_conversions) != 0
            if len(time_conversions) > 1:
                input_timezone_name = "All timezones"
            else:
                # If there aren't any other out timezones, don't print the timezone
                # name header
                input_timezone_name = None
        else:
            converted = await _convert_times(times, timezone_out)
            input_timezone_name = cast(TimezoneType, times[0].tzinfo).zone

        conversion_output.conversions.append(
            TimeConversion(input_timezone_name, converted)
        )


async def convert_time_to_user_timezones(
    db: Database,
    user_id: int,
    guild: discord.Guild,
    raw_quantities: list[RawQuantity],
    *,
    runtime_msgs: RuntimeMessages,
) -> TimeConversionOutput:
    """
    Convert times.

    :param db: the Database adapter for getting user timezones
    :param user_id: the id of the user asking for a time conversion
    :param guild: the guild the conversion is occurring in
    :param raw_quantities: a list of `RawQuantity`s that may be valid times
    :param runtime_msgs: A collection of messages that were generated during
        runtime. These may be reported back to the user.
    :returns: a `TimeConversionOutput` object with details about this conversion
    """
    out = TimeConversionOutput()

    time_conversions = await _parse_input(
        db, user_id, raw_quantities, runtime_msgs, out
    )
    if not time_conversions:
        return out

    await _do_conversions(db, guild, time_conversions, out)

    return out
