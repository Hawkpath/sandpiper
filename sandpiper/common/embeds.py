from collections import Iterable
from typing import Union

import discord

from .misc import join

__all__ = ['Embeds']

FieldType = tuple[str, str, bool]


class Embeds:

    INFO_COLOR = 0x5E5FFF
    SUCCESS_COLOR = 0x57FCA5
    WARNING_COLOR = 0xE7D900
    ERROR_COLOR = 0xFF0000
    SPECIAL_COLOR = 0xF656F1

    @classmethod
    async def info(
            cls, messageable: discord.abc.Messageable,
            message: Union[str, Iterable[str]] = None,
            fields: Iterable[FieldType] = None
    ):
        """
        Sends an info embed. At least one of ``message`` or ``fields`` must be
        supplied.

        :param messageable: A messageable interface to send the embed to
        :param message: An info message. Can be either a single string or an
            iterable of strings to join with newlines. Optional if ``fields``
            is supplied.
        :param fields: An iterable of fields to add to the embed where each
            field is a tuple of shape (name, value, inline). Optional if
            ``message`` is supplied.
        """
        if not (message or fields):
            raise ValueError(
                "You must specify at least one of message or fields"
            )

        if isinstance(message, str):
            pass
        elif isinstance(message, Iterable):
            message = join(*message, sep='\n')
        elif message is None:
            message = discord.Embed.Empty
        else:
            raise ValueError(
                "Message must either be None, a single string, or an iterable "
                "of strings"
            )

        embed = discord.Embed(
            title='Info', description=message, color=cls.INFO_COLOR
        )

        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)
        await messageable.send(embed=embed)

    @classmethod
    async def success(
            cls, messageable: discord.abc.Messageable,
            message: Union[str, Iterable[str]]
    ):
        """
        Sends a success embed.

        :param messageable: A messageable interface to send the embed to
        :param message: The success message. Can be either a single string or
            an iterable of strings to join with newlines.
        """
        if not isinstance(message, str) and isinstance(message, Iterable):
            message = join(*message, sep='\n')
        embed = discord.Embed(
            title='Success', description=message, color=cls.SUCCESS_COLOR
        )
        await messageable.send(embed=embed)

    @classmethod
    async def warning(
            cls, messageable: discord.abc.Messageable,
            message: Union[str, Iterable[str]]
    ):
        """
        Sends a success embed.

        :param messageable: A messageable interface to send the embed to
        :param message: The success message. Can be either a single string or
            an iterable of strings to join with newlines.
        """
        if not isinstance(message, str) and isinstance(message, Iterable):
            message = join(*message, sep='\n')
        embed = discord.Embed(
            title='Warning', description=message, color=cls.WARNING_COLOR
        )
        await messageable.send(embed=embed)

    @classmethod
    async def error(
            cls, messageable: discord.abc.Messageable,
            message: Union[str, Iterable[str]]
    ):
        """
        Sends an error embed.

        :param messageable: A messageable interface to send the embed to
        :param message: The error message. Can be either a single string or an
            iterable of strings to join with newlines.
        """
        if not isinstance(message, str) and isinstance(message, Iterable):
            message = join(*message, sep='\n')
        embed = discord.Embed(
            title='Error', description=message, color=cls.ERROR_COLOR
        )
        await messageable.send(embed=embed)

    @classmethod
    async def special(
            cls, messageable: discord.abc.Messageable, title: str,
            message: Union[str, Iterable[str]]
    ):
        """
        Sends a special embed (such as for announcements).

        :param messageable: A messageable interface to send the embed to
        :param title: The embed's title
        :param message: The special message. Can be either a single string or an
            iterable of strings to join with newlines.
        """
        if not isinstance(message, str) and isinstance(message, Iterable):
            message = join(*message, sep='\n')
        embed = discord.Embed(
            title=title, description=message, color=cls.SPECIAL_COLOR
        )
        await messageable.send(embed=embed)
