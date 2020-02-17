import logging
import asyncio
import argparse
import discord
import asyncrcon
from asyncrcon import AsyncRCON
from database import SQLite
from discord import Member, Embed, Message
from discord.ext import commands
from shared import EMBED_COLOR
from cogs import WhitelistMgmt, Admin


def parse_args():
    """
    Initializes command line arguments and
    parses them on startup returning the parsed
    args namespace.
    """
    parser = argparse.ArgumentParser()

    bot = parser.add_argument_group('Discord Bot')
    bot.add_argument(
        '--token', '-t', required=True, type=str,
        help='The discord bot token')
    bot.add_argument(
        '--prefix', '-p', default='>', type=str,
        help='The command prefix of the bot (def: \'>\')')
    bot.add_argument(
        '--allow-sudo', default=False, action='store_true',
        help='Whether or not sudo command should be enabled')

    rcon = parser.add_argument_group('RCON Connection')
    rcon.add_argument(
        '--rcon-address', '-raddr', default='localhost:25575', type=str,
        help='The address of the RCON server (def: \'localhost:25575\')')
    rcon.add_argument(
        '--rcon-password', '-rpw', required=True, type=str,
        help='The password of the RCON server')
    rcon.add_argument(
        '--rcon-encoding', default='utf-8', type=str,
        help='The encoding to be used for RCON payloads')

    parser.add_argument(
        '--log-level', '-l', default=20, type=int,
        help='Set log level of the default logger (def: 20)')
    parser.add_argument(
        '--db-file', '-db', default='database.db', type=str,
        help='Set database file location (def: database.db)')

    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(
        level=args.log_level,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

    rcon = AsyncRCON(args.rcon_address, args.rcon_password,
                     encoding=args.rcon_encoding)

    db = SQLite(args.db_file)

    bot = commands.Bot(command_prefix=args.prefix)

    bot.loop.run_until_complete(rcon.open_connection())

    if args.allow_sudo:
        logging.warning('allow sudo is enabled! This gives acces to the ' +
                        'RCON console directly out of the discord chat!')

    ##########
    # EVENTS #
    ##########

    @bot.event
    async def on_ready():
        logging.info(
            'Ready (logged in as {}#{} [{}])'.format(
                bot.user.name, bot.user.discriminator, bot.user.id))

    @bot.event
    async def on_message(msg: Message):
        if bot.user in msg.mentions:
            em = Embed()
            em.color = EMBED_COLOR
            em.title = 'discord2mcwhitelist'
            em.description = ('Hey, I am a bot which can connect your ' +
                              'Discord Account with your Minecraft User ' +
                              'ID and add you to the Guilds Minecraft ' +
                              'Server Whitelist!\n\n' +
                              'Just enter `{}help` in the chat for more ' +
                              'information on how to use ' +
                              'me.').format(args.prefix)

            versions = [
                '- discord.py: {}'.format(discord.__version__),
                '- asyncrcon: {}'.format(asyncrcon.__version__),
            ]

            em.add_field(
                name='GitHub',
                value='https://github.com/zekroTJA/discord2mcwhitelist',
                inline=False)
            em.add_field(
                name='Package Versions',
                value='\n'.join(versions),
                inline=False)
            em.set_footer(
                text='© 2020 zekro.de')
            await msg.channel.send(embed=em)
        await bot.process_commands(msg)

    @bot.event
    async def on_member_remove(member: Member):
        _, mc_id = db.get_whitelist_by_discord_id(str(member.id))
        if mc_id is not None:
            await rcon.command('whitelist remove {}'.format(mc_id))
            await asyncio.sleep(0.5)
            await rcon.command('whitelist reload')
            db.rem_witelist(str(member.id))

    @bot.event
    async def on_command_error(ctx: commands.Context, err):
        ctx.send(':warning:  Command raised an exception: ```{}```'.format(err))

    ################
    # REGISTRATION #
    ################

    bot.add_cog(WhitelistMgmt(bot, rcon, db))
    bot.add_cog(Admin(bot, rcon, db, args.allow_sudo))

    ###########
    # RUN BOT #
    ###########

    bot.run(args.token)


if __name__ == '__main__':
    main()
