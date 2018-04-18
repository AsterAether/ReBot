import requests
from bs4 import BeautifulSoup
import telegram
import conf


def register(rebot):
    rebot.commands['badjoke'] = cmd_bad_joke
    rebot.commands['flagjoke'] = cmd_flag_joke


def unregister(rebot):
    del rebot.commands['badjoke']
    del rebot.commands['flagjoke']


def post_bad_joke(rebot, chat_id):
    joke_resp = requests.get('https://www.davepagurek.com/badjokes/getjoke.php')
    bs4 = BeautifulSoup(joke_resp.text, 'html.parser')

    headline = bs4.find('h2').text.upper()
    joke = bs4.find('h3').text.upper()
    id = bs4.find('input', {}).get('value')
    rebot.bot.send_message(chat_id, id + '#J\n*' + headline + '*\n\n' + joke,
                           parse_mode=telegram.ParseMode.MARKDOWN,
                           disable_notification=conf.silent)


def cmd_bad_joke(rebot, args, update):
    post_bad_joke(rebot, update.message.chat.id)

    if update.message.from_user.id not in conf.bot_overlords:
        rebot.set_can('badjoke', update.message.chat.id, False)
        return


def cmd_flag_joke(rebot, args, update):
    try:
        if update.message.reply_to_message.from_user.id != conf.bot_id:
            rebot.bot.send_message(update.message.chat.id,
                                   'YOU NEED TO REPLY TO A JOKE TO FLAG IT', disable_notification=conf.silent)

        joke = update.message.reply_to_message.text
        id = joke.split('#J')[0]
        requests.get('https://www.davepagurek.com/badjokes/flag.php?=' + id)
        try:
            update.message.reply_to_message.delete()
        except telegram.error.BadRequest:
            pass
        try:
            update.message.delete()
        except telegram.error.BadRequest:
            pass
    except (AttributeError, ValueError):
        rebot.bot.send_message(update.message.chat.id,
                               'YOU NEED TO REPLY TO A JOKE TO FLAG IT', disable_notification=conf.silent)
