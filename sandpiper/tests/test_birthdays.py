import asyncio
import datetime as dt
from typing import Optional
from unittest import mock

import discord
from discord.ext import commands
import pytest
import pytz

from .helpers.misc import *
from .helpers.mocking import *
from sandpiper.birthdays import Birthdays
from sandpiper.common.time import TimezoneType
from sandpiper.user_data import PrivacyType, UserData

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def asyncio_sleep():
    return asyncio.sleep


@pytest.fixture()
def birthdays_cog(
        bot, message_templates_with_age, message_templates_no_age
) -> Birthdays:
    cog = Birthdays(
        bot, message_templates_no_age=message_templates_no_age,
        message_templates_with_age=message_templates_with_age
    )
    bot.add_cog(cog)
    cog.daily_loop.count = 1
    cog.daily_loop.cancel()
    return cog


@pytest.fixture()
def bot(bot, database) -> commands.Bot:
    """Add a Bios cog to a bot and return the bot"""
    bot.add_cog(UserData(bot))
    bot.loop.set_debug(True)
    return bot


@pytest.fixture()
async def main_channel(database, main_guild, make_channel):
    channel = make_channel(main_guild, name='the-birthday-channel')
    await database.set_guild_birthday_channel(main_guild.id, channel.id)
    yield channel


@pytest.fixture()
def main_guild(make_guild):
    return make_guild(name='Main Guild')


@pytest.fixture()
def message_templates_no_age() -> list[str]:
    return ["name={name} they={they} ping={ping}"]


@pytest.fixture()
def message_templates_with_age() -> list[str]:
    return ["name={name} they={they} age={age} ping={ping}"]


@pytest.fixture(autouse=True)
def patch_asyncio_sleep(asyncio_sleep):
    async def sleep(time: int, *args, **kwargs):
        if time == 0:
            # This is used to skip the current loop
            await asyncio_sleep(0)

    with mock.patch('asyncio.sleep') as mock_sleep:
        mock_sleep.side_effect = sleep
        yield mock_sleep


@pytest.fixture(autouse=True)
def patch_database_isinstance():
    with mock.patch(
        'sandpiper.user_data.database_sqlite.isinstance',
        wraps=isinstance_mock_supported
    ):
        yield


@pytest.fixture()
def patch_send_birthday_message_hook(
        birthdays_cog, patch_asyncio_sleep, patch_datetime_now
):
    """
    Adds a hook to Birthdays.send_birthday_message. When it is called, the mock
    datetime.now will be changed to a different datetime to simulate sleeping.
    """
    patchers = []

    def f(new_datetime: dt.datetime):
        # Save a reference to the original method
        orig_fn = birthdays_cog.send_birthday_message

        async def side_effect(*args, **kwargs):
            """
            Change the datetime.now, reset the asyncio.sleep mock (to make
            testing args more reliable), and call the original method
            """
            patch_datetime_now(new_datetime)
            patch_asyncio_sleep.reset_mock()
            await orig_fn(*args, **kwargs)

        p = mock.patch.object(
            birthdays_cog, 'send_birthday_message', side_effect=side_effect
        )
        patchers.append(p)
        p.start()

    yield f

    for p in patchers:
        p.stop()


@pytest.fixture(autouse=True)
def patch_time(
        patch_datetime, patch_localzone_utc, patch_database_isinstance
) -> dt.datetime:
    pass


@pytest.fixture()
def run_birthdays_cog(
        add_user_to_guild, bot, main_channel, main_guild,
        patch_asyncio_sleep, patch_datetime_now,
        patch_send_birthday_message_hook, run_daily_loop_once
):
    async def f(
            user: discord.User, birthday: dt.date,
            now_when_scheduling: dt.datetime, now_when_sending: dt.datetime
    ) -> str:
        # Add bot to main_guild
        add_user_to_guild(main_guild.id, bot.user.id, 'Bot')
        # Set datetime.now before scheduling
        patch_datetime_now(now_when_scheduling)
        # Add hook to change datetime.now when the message is about to be
        # sent
        patch_send_birthday_message_hook(now_when_sending)

        await run_daily_loop_once()

        # Assert send_birthday_message slept until the birthday midnight
        time_delta = (now_when_sending - now_when_scheduling).total_seconds()
        patch_asyncio_sleep.assert_called_with(time_delta)

        # Ensure a message was sent to main_channel and return the message
        # for further assertions
        main_channel.send.assert_called_once()
        return main_channel.send.call_args.args[0]

    return f


@pytest.fixture()
def run_daily_loop_once(birthdays_cog):
    async def f():
        birthdays_cog.daily_loop.start()
        # Wait for the birthday scheduling task to finish
        await birthdays_cog.daily_loop.get_task()
        # Wait for the birthday sending task to finish
        await asyncio.gather(*birthdays_cog.tasks.values())
    return f


@pytest.fixture()
def user_factory(add_user_to_guild, database, make_user, new_id):
    async def f(
            *,
            guild: Optional[discord.Guild] = None,
            display_name: Optional[str] = None,
            name: Optional[str] = None,
            pronouns: Optional[str] = None,
            birthday: Optional[dt.date] = None,
            timezone: Optional[TimezoneType] = None,
            p_name: PrivacyType = PrivacyType.PUBLIC,
            p_pronouns: PrivacyType = PrivacyType.PUBLIC,
            p_birthday: PrivacyType = PrivacyType.PUBLIC,
            p_age: PrivacyType = PrivacyType.PUBLIC,
            p_timezone: PrivacyType = PrivacyType.PUBLIC,
    ) -> discord.User:
        uid = new_id()

        user = make_user(uid)
        if guild is not None:
            if display_name is None:
                display_name = "Some member"
            add_user_to_guild(guild.id, uid, display_name)

        await database.create_user(uid)
        await database.set_preferred_name(uid, name)
        await database.set_pronouns(uid, pronouns)
        await database.set_birthday(uid, birthday)
        await database.set_timezone(uid, timezone)
        await database.set_privacy_preferred_name(uid, p_name)
        await database.set_privacy_pronouns(uid, p_pronouns)
        await database.set_privacy_birthday(uid, p_birthday)
        await database.set_privacy_age(uid, p_age)
        await database.set_privacy_timezone(uid, p_timezone)

        return user

    return f


class TestBirthdays:

    async def test_basic(self, main_guild, run_birthdays_cog, user_factory):
        bday = dt.date(2000, 2, 14)
        user = await user_factory(
            guild=main_guild,
            birthday=bday,
            timezone=pytz.timezone('UTC')
        )
        msg = await run_birthdays_cog(
            user, bday,
            now_when_scheduling=dt.datetime(2020, 2, 13, 23, 45),
            now_when_sending=dt.datetime(2020, 2, 14, 0, 0)
        )
        assert_in(msg, "name=Some member", "they=they", "age=20", f"ping=<@{user.id}>")
