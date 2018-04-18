import base64
import binascii
import telegram
import conf


def register(rebot):
    rebot.commands['b64'] = cmd_base64
    rebot.commands['unb64'] = cmd_unbase64


def unregister(rebot):
    del rebot.commands['b64']
    del rebot.commands['unb64']


def cmd_base64(rebot, args, update):
    text = ''

    try:
        text = update.message.reply_to_message.text
    except AttributeError:
        pass

    if not text and len(args) == 0:
        rebot.bot.send_message(update.message.chat.id,
                               'YOU NEED TO REPLY TO A MESSAGE OR PROVIDE TEXT', disable_notification=conf.silent)
        return
    elif not text:
        text = ' '.join(args)

    b64_text = str(base64.b64encode(bytes(text, 'utf8')), 'utf8')

    try:
        rebot.bot.send_message(update.message.chat.id,
                               b64_text,
                               disable_notification=conf.silent,
                               reply_to_message_id=update.message.message_id)
    except telegram.error.BadRequest:
        pass


def cmd_unbase64(rebot, args, update):
    b64_text = ''

    try:
        b64_text = update.message.reply_to_message.text
    except AttributeError:
        pass

    if not b64_text and len(args) == 0:
        rebot.bot.send_message(update.message.chat.id,
                               'YOU NEED TO REPLY TO A MESSAGE OR PROVIDE TEXT', disable_notification=conf.silent)
        return
    elif not b64_text:
        b64_text = ' '.join(args)

    try:
        text = str(base64.b64decode(bytes(b64_text, 'utf8')), 'utf8')
    except binascii.Error:
        rebot.bot.send_message(update.message.chat.id,
                               'NOT A BASE64 STRING', disable_notification=conf.silent)
        return

    try:
        rebot.bot.send_message(update.message.chat.id,
                               text,
                               disable_notification=conf.silent,
                               reply_to_message_id=update.message.message_id)
    except telegram.error.BadRequest:
        pass
