import sys
import asyncio
import logging
from typing import Optional
from discord import Role, TextChannel, Message
from discord.ext.commands import command, check, Cog, \
    Context, MissingRequiredArgument, BadArgument, CheckFailure
from asyncrcon import AsyncRCON
from database import SQLite


def is_guild_owner() -> bool:
    async def predicate(ctx: Context) -> bool:
        return ctx.author.id == ctx.guild.owner.id
    return check(predicate)


class Admin(Cog, name='Admin'):

    _rcon: AsyncRCON
    _db: SQLite
    _sudo_enabled: bool

    def __init__(self, bot, rcon: AsyncRCON, db: SQLite, sudo_enabled=False):
        self.bot = bot
        self._rcon = rcon
        self._db = db
        self._sudo_enabled = sudo_enabled

    async def _check_admin(self, ctx: Context) -> bool:
        role_id = self._db.get_admin_role(ctx.guild.id)
        admin = (role_id and role_id in [str(r.id) for r in ctx.author.roles])
        admin = admin or ctx.author.id == ctx.guild.owner.id
        if not admin:
            await ctx.send(':warning:  Insufficient permission.')
        return admin

    # adminrole

    @command(
        brief='Set admin role',
        description='Sets a role as admin role.')
    @is_guild_owner()
    async def adminrole(self, ctx: Context, role: Role):
        async with ctx.typing():
            self._db.set_admin_role(ctx.guild.id, role.id)
            await ctx.send(
                ':white_check_mark:  Role ' +
                '`{}` is now set as admin role.'.format(role.name))

    @adminrole.error
    async def adminrole_error(self, ctx: Context, err):
        if isinstance(err, MissingRequiredArgument):
            await ctx.send_help()
        if isinstance(err, BadArgument):
            await ctx.send(':warning:  Bad argument: {}'.format(err))
        if isinstance(err, CheckFailure):
            await ctx.send(':warning:  Insufficient permission.')

    # sudo

    @command(
        brief='Execute RCON command',
        description='Execute RCON command directly on server')
    async def sudo(self, ctx: Context, *cmd):
        async with ctx.typing():
            if not await self._check_admin(ctx):
                return

            if not self._sudo_enabled:
                await ctx.send(':warning:  Sudo is disbaled by configuration.')
                return

            res = await self._rcon.command(' '.join(cmd))
            await ctx.send(
                'Result:\n```{}```'.format(res or '[empty]'))

    # restart

    @command(
        brief='Restart the bot',
        description='Restart the bot instance - this only works if the script auto-restarts!')
    async def restart(self, ctx: Context):
        if not await self._check_admin(ctx):
            return

        await ctx.send(':repeat:  Restarting...')
        await ctx.bot.close()
        sys.exit(1)

    # statuschan

    @command(
        brief='Setup status channel',
        description='Set up the channel where the server status message will be spawned')
    async def statuschan(self, ctx: Context, channel: Optional[TextChannel] = None):
        if not await self._check_admin(ctx):
            return

        if channel is None:
            channel = ctx.message.channel

        self._db.set_status_channel(ctx.guild.id, channel.id)

        await ctx.send(':white_check_mark:  Set <#{}> as status channel.'.format(channel.id))

    # disable

    @command(
        brief='Disable whitelist binding',
        description='Disable whitelist binding for this guild')
    async def disable(self, ctx: Context):
        if not await self._check_admin(ctx):
            return

        self._db.set_disabled(ctx.guild.id, True)

        await ctx.send(':white_check_mark:  Whitelist binding is now **disabled**.')

    # enable

    @command(
        brief='Enable whitelist binding',
        description='Enable whitelist binding for this guild')
    async def enable(self, ctx: Context):
        if not await self._check_admin(ctx):
            return

        self._db.set_disabled(ctx.guild.id, False)

        await ctx.send(':white_check_mark:  Whitelist binding is now **enabled**.')

    # sync

    @command(
        brief='Sync server whitelist',
        description='Sync the database mapped whitelist to the servers whitelist')
    async def sync(self, ctx: Context):
        if not await self._check_admin(ctx):
            return

        whitelist_map = self._db.get_whitelist()
        synced = 0
        to_sync = len(whitelist_map)

        msg: Message = await ctx.send(':clock1:  Synced {} of {} users...'.format(synced, to_sync))

        map_tpls = list(whitelist_map.items())

        while synced < to_sync:
            await asyncio.sleep(0.5)
            try:
                await self._rcon.command('whitelist add {}'.format(map_tpls[synced][1]))
                synced += 1
            except Exception as e:
                logging.error('Failed syncing: {}'.format(e))
                continue
            await msg.edit(content=':clock1:  Synced {} of {} users...'.format(synced, to_sync))

        await self._rcon.command('whitelist reload')

        await msg.edit(content=':white_check_mark:  Synced {} of {} users sccessfully.'.format(synced, to_sync))

    # purge

    @command(
        brief='Purge server whitelist',
        description='Sync the database mapped whitelist to the servers whitelist')
    async def purge(self, ctx: Context):
        if not await self._check_admin(ctx):
            return

        whitelist_map = self._db.get_whitelist()
        synced = 0
        to_sync = len(whitelist_map)

        msg: Message = await ctx.send(':clock1:  Purged {} of {} users...'.format(synced, to_sync))

        map_tpls = list(whitelist_map.items())

        while synced < to_sync:
            await asyncio.sleep(0.5)
            try:
                await self._rcon.command('whitelist remove {}'.format(map_tpls[synced][1]))
                synced += 1
            except Exception as e:
                logging.error('Failed syncing: {}'.format(e))
                continue
            await msg.edit(content=':clock1:  Purged {} of {} users...'.format(synced, to_sync))

        await self._rcon.command('whitelist reload')

        await msg.edit(content=':white_check_mark:  Purged {} of {} users sccessfully.'.format(synced, to_sync))
