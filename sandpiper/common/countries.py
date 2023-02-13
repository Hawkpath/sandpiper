__all__ = [
    "DEFAULT_FLAG",
    "country_code_to_country_name",
    "timezone_to_country_code",
    "to_regional_indicator",
    "get_country_flag_emoji",
    "get_country_flag_emoji_from_timezone",
]

from typing import Union

import pytz

from sandpiper.common.time import TimezoneType

DEFAULT_FLAG = ":flag_white:"


country_code_to_country_name = pytz.country_names
timezone_to_country_code = {
    tz: country_code
    for country_code, timezones in pytz.country_timezones.items()
    for tz in timezones
}


def to_regional_indicator(char: str) -> str:
    code = ord(char)
    if code < 65 or code > 90:
        raise ValueError("char must be a single char from A-Z")
    return chr(code + 127397)


def get_country_flag_emoji(country_id: str) -> str:
    if len(country_id) != 2:
        raise ValueError("country_id must be a 2-character string")
    return "".join(to_regional_indicator(i) for i in country_id)


def get_country_flag_emoji_from_timezone(tz: Union[str, TimezoneType]):
    if isinstance(tz, TimezoneType.__args__):
        tz: str = tz.zone
    elif not isinstance(tz, str):
        raise TypeError(f"tz must be a str or pytz timezone, got {type(tz)}")

    code = timezone_to_country_code.get(tz)
    return get_country_flag_emoji(code) if code is not None else DEFAULT_FLAG
