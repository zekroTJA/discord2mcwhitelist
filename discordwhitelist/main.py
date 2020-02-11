import logging
import argparse
from rcon import RCON
from database import SQLite
from discord import Member
from discord.ext import commands
from discord.ext.commands import Context


# TODO:
#  - add list and info command
#  - make rcon requests asyncronous and
#    out-timable that they dont block
#    the bot loop if they stuck

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

    rcon = parser.add_argument_group('RCON Connection')
    rcon.add_argument(
        '--rcon-address', '-raddr', default='localhost:25575', type=str,
        help='The address of the RCON server (def: \'localhost:25575\')')
    rcon.add_argument(
        '--rcon-password', '-rpw', required=True, type=str,
        help='The password of the RCON server')

    parser.add_argument(
        '--log-level', '-l', default=20, type=int,
        help='Set log level of the default logger (def: 20)')

    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(
        level=args.log_level,
        format='%(asctime)s | %(levelname)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S')

    rcon = RCON(args.rcon_address, args.rcon_password)
    rcon.connect()

    db = SQLite('database.db')

    bot = commands.Bot(command_prefix=args.prefix)

    ##########
    # EVENTS #
    ##########

    @bot.event
    async def on_ready():
        logging.info(
            'Ready (logged in as {}#{} [{}])'.format(
                bot.user.name, bot.user.discriminator, bot.user.id))

    @bot.event
    async def on_member_remove(member: Member):
        _, mc_id = db.get_whitelist_by_discord_id(str(member.id))
        if mc_id is not None:
            rcon.command('whitelist remove {}'.format(mc_id))
            db.rem_witelist(str(member.id))

    ############
    # COMMANDS #
    ############

    @bot.command(
        brief='Add to whitelist',
        description='Register a minecraft ID to your discord profile ' +
                    'and add it to the minecraft servers whitelist.',
        aliases=('add', 'set'))
    async def bind(ctx: Context, *args):
        if len(args) == 0:
            return

        mc_id: str = args[0].lower()

        dc_id, curr_mc_id = db.get_whitelist_by_mc_id(mc_id)

        if curr_mc_id is not None and mc_id == curr_mc_id:
            await ctx.send(':warning:  This minecraft ID is already ' +
                           'bound to your account!')
            return

        if dc_id is not None and dc_id != str(ctx.message.author.id):
            await ctx.send(':warning:  This minecraft ID is already ' +
                           'registered by another user!')
            return

        old_mc_id = db.set_witelist(str(ctx.message.author.id), mc_id)

        if old_mc_id is not None:
            rcon.command('whitelist remove {}'.format(old_mc_id))
        rcon.command('whitelist add {}'.format(mc_id))

        await ctx.send(
            ':white_check_mark:  You are now bound to the mc ' +
            'account `{}` and added to the servers whitelist.'.format(mc_id))

    @bot.command(
        brief='Remove from whitelist',
        description='Unregisters a bound minecraft ID from your account ' +
                    'and removes you from the whitelist of the server.',
        aliases=('remove', 'unset'))
    async def unbind(ctx: Context):
        _, mc_id = db.get_whitelist_by_discord_id(str(ctx.message.author.id))
        if mc_id is None:
            await ctx.send(':warning:  Ypur account is not bound to any ' +
                           'minecraft ID.')
            return

        rcon.command('whitelist remove {}'.format(mc_id))
        db.rem_witelist(str(ctx.message.author.id))

        await ctx.send(
            ':white_check_mark:  Successfully removed you from ' +
            'the servers whitelist and account is unbound.'.format(mc_id))

    ###########
    # RUN BOT #
    ###########

    bot.run(args.token)


if __name__ == '__main__':
    main()
