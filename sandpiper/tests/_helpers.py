import re
from typing import NoReturn, Optional
import unittest.mock as mock

import discord


# region Misc helper functions


# noinspection PyPep8Naming
class MagicMock_(mock.MagicMock):
    """
    Identical to MagicMock, but the ``name`` kwarg will be parsed as a regular
    kwarg (assigned to the mock as an attribute).
    """

    def __init__(self, *args, _name_: Optional[str] = None, **kwargs):
        if _name_ is None:
            _name_ = ''
        name_attr = kwargs.pop('name', None)
        super().__init__(*args, name=_name_, **kwargs)
        self.name = name_attr


def get_embeds(mock_: MagicMock_) -> list[discord.Embed]:
    """
    :param mock_: a mock ``send`` method
    :return: a list of embeds sent in each message
    """
    return [
        embed for call in mock_.call_args_list
        if (embed := call.kwargs.get('embed'))
    ]


def get_contents(mock_: MagicMock_) -> list[str]:
    """
    :param mock_: a mock ``send`` method
    :return: a list of each message's contents
    """
    # noinspection PyUnboundLocalVariable
    return [
        content for call in mock_.call_args_list
        if len(call.args) > 0 and (content := call.args[0]) is not None
    ]


# endregion

# region Embed assertions


def assert_success(self, embed: discord.Embed, *substrings: str):
    """
    Assert ``embed`` is a success embed and that its description contains
    each substring in ``substrings``.
    """
    __tracebackhide__ = True
    assert 'Success' in embed.title
    assert_in(embed.description, *substrings)


def assert_warning(self, embed: discord.Embed, *substrings: str):
    """
    Assert ``embed`` is a warning embed and that its description contains
    each substring in ``substrings``.
    """
    __tracebackhide__ = True
    assert 'Warning' in embed.title
    assert_in(embed.description, *substrings)


def assert_error(self, embed: discord.Embed, *substrings: str):
    """
    Assert ``embed`` is an error embed and that its description contains
    each substring in ``substrings``.
    """
    __tracebackhide__ = True
    assert 'Error' in embed.title
    assert_in(embed.description, *substrings)


def assert_info(self, embed: discord.Embed, *substrings: str):
    """
    Assert ``embed`` is an info embed and that its description contains
    each substring in ``substrings``.
    """
    __tracebackhide__ = True
    assert 'Info' in embed.title
    assert_in(embed.description, *substrings)


# endregion

# region Misc assertions


def assert_no_reply(self, send: mock.Mock) -> NoReturn:
    """Assert that the bot didn't reply with the `send` mock."""
    __tracebackhide__ = True
    assert not send.called, "Bot replied when it shouldn't have"


def assert_in(self, str_: str, *substrings: str) -> NoReturn:
    """
    Dispatch ``msg`` to the bot and assert that it replies with one
    message and contains each substring in ``substrings``.
    """
    __tracebackhide__ = True
    for substr in substrings:
        assert substr in str_


def assert_regex(self, str_: str, *patterns: str) -> NoReturn:
    """
    Dispatch ``msg`` to the bot and assert that it replies with one
    message and matches each regex pattern in ``patterns``.
    """
    __tracebackhide__ = True
    str_ = await self.dispatch_msg_get_contents(str_, only_one=True)
    for pattern in patterns:
        assert re.match(pattern, str_), (
            f'Pattern "{pattern}" did not match "{str_}"'
        )


# endregion
