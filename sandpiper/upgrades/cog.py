import logging
from typing import Optional

import discord.ext.commands as commands

from .versions import all_upgrade_handlers
from .upgrades import do_upgrades
from sandpiper import __version__ as current_version
from sandpiper.user_data import UserData

__all__ = ['Upgrades']


logger = logging.getLogger(__name__)


class Upgrades(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def do_upgrades(self):
        user_data: Optional[UserData] = self.bot.get_cog('UserData')
        if user_data is None:
            logger.warning(
                f"Failed to get the UserData cog. Skipping upgrade handlers."
            )
        db = await user_data.get_database()
        await db.ready()
        previous_version = await db.get_sandpiper_version()
        await do_upgrades(
            self.bot, previous_version, current_version, all_upgrade_handlers
        )
