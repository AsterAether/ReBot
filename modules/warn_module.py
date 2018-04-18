import datetime
import telegram
import conf
import time
import os
import db


def register(rebot):
    rebot.commands['warn'] = cmd_warn
    rebot.commands['forgive'] = cmd_forgive
    rebot.commands['props'] = cmd_props
    rebot.commands['withdraw'] = cmd_withdraw
    rebot.commands['listprops'] = cmd_list_props
    rebot.commands['listwarnings'] = cmd_list_warnings
    rebot.commands['myprops'] = cmd_my_props
    rebot.commands['mywarnings'] = cmd_my_warnings


def unregister(rebot):
    del rebot.commands['warn']
    del rebot.commands['forgive']
    del rebot.commands['props']
    del rebot.commands['withdraw']
    del rebot.commands['listprops']
    del rebot.commands['listwarnings']
    del rebot.commands['myprops']
    del rebot.commands['mywarnings']


def issue_warning(rebot, poster_id, poster_name, message_id, chat_id, text, photo, reason, chat_type):
    if poster_id in conf.bot_overlords:
        return 0

    warning = db.Warning(message_id=message_id,
                               chat_id=chat_id,
                               timestamp=datetime.datetime.now(),
                               poster_id=poster_id,
                               reason=reason,
                               photo_filename=photo,
                               text=text)

    rebot.db_conn.save(warning)

    count = rebot.db_conn.get_warning_count(poster_id, chat_id)

    props_count = rebot.db_conn.get_props_count(poster_id, chat_id)

    poster = rebot.db_conn.get_poster(poster_id, poster_name)

    try:
        rebot.bot.send_message(chat_id,
                               str(warning.warning_id) +
                               '#W\nYOU [' + poster.name +
                               '] ARE WARNED\nREASON: ' + reason + '\nWARNING NUMBER ' + str(count),
                               disable_notification=conf.silent,
                               reply_to_message_id=message_id)
    except telegram.error.BadRequest:
        msg_text = str(
            warning.warning_id) + '#W\nYOU [' + poster.name + '] ARE WARNED\nREASON: ' + reason + '\nWARNING NUMBER ' + str(
            count) + '\nORIGINAL MESSAGE: "' + str(text) + '"'
        if photo:
            rebot.bot.send_photo(chat_id,
                                 photo=open('files/' + photo, 'rb'),
                                 caption=msg_text,
                                 disable_notification=conf.silent)
        else:
            rebot.bot.send_message(chat_id,
                                   msg_text,
                                   disable_notification=conf.silent)

    if chat_type != 'private':
        if conf.max_warnings - conf.kick_warn_threshold < count - min(conf.props_max_minus,
                                                                      props_count) < conf.max_warnings:
            rebot.bot.send_message(chat_id, str(
                conf.max_warnings - count + min(conf.props_max_minus, props_count)) + ' MORE WARNING' + (
                                       '' if count == 1 else 'S') + ' AND YOU WILL BE KICKED')
        elif count - min(conf.props_max_minus, props_count) >= conf.max_warnings:
            rebot.bot.send_message(chat_id, '0 MORE WARNINGS AND YOU WILL BE KICKED')
            time.sleep(2)
            rebot.bot.send_message(chat_id, 'OH WAIT; IT\'S ALREADY TIME TO GO')
            time.sleep(1)
            try:
                rebot.bot.kick_chat_member(chat_id, poster_id)
                ban = rebot.db_conn.Ban(chat_id=chat_id, poster_id=poster_id, timestamp=datetime.datetime.now())
                rebot.db_conn.save(ban)
            except telegram.error.BadRequest:
                pass
            rebot.db_conn.forgive_warnings_for_poster(poster_id)


def issue_props(rebot, poster_id, poster_name, message_id, chat_id, text, photo, reason):
    props = db.Props(message_id=message_id,
                           chat_id=chat_id,
                           timestamp=datetime.datetime.now(),
                           poster_id=poster_id,
                           reason=reason,
                           photo_filename=photo,
                           text=text)

    rebot.db_conn.save(props)

    count = rebot.db_conn.get_props_count(poster_id, chat_id)

    poster = rebot.db_conn.get_poster(poster_id, poster_name)

    try:
        rebot.bot.send_message(chat_id,
                               str(props.props_id) +
                               '#P\nPROPS TO  [' + poster.name +
                               ']\nREASON: ' + reason + '\nPROPS NUMBER ' + str(count),
                               disable_notification=conf.silent,
                               reply_to_message_id=message_id)
    except telegram.error.BadRequest:
        msg_text = str(
            props.props_id) + '#P\nPROPS TO [' + poster.name + ']\nREASON:' + reason + '\nWARNING NUMBER ' + str(
            count) + '\nORIGINAL MESSAGE: "' + str(text) + '"'
        if photo:
            rebot.bot.send_photo(chat_id,
                                 photo=open('files/' + photo, 'rb'),
                                 caption=msg_text,
                                 disable_notification=conf.silent)
        else:
            rebot.bot.send_message(chat_id,
                                   msg_text,
                                   disable_notification=conf.silent)


def cmd_warn(rebot, args, update):
    if not rebot.check_is_overlord(update.message.from_user.id):
        poster = rebot.db_conn.get_poster(update.message.from_user.id, update.message.from_user.name)
        rebot.bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')

        if conf.warn_on_admin:
            issue_warning(rebot, poster.poster_id, poster.name, update.message.message_id,
                          update.message.chat.id, rebot.get_text(update.message), None,
                          'UNAUTHORIZED WARNING ATTEMPT',
                          update.message.chat.type)
        return

    try:
        reason = 'MANUAL WARNING'
        if len(args) >= 1:
            reason = ' '.join(args)
        poster = rebot.db_conn.get_poster(update.message.reply_to_message.from_user.id,
                                     update.message.reply_to_message.from_user.name)

        if poster.poster_id == conf.bot_id:
            rebot.bot.send_message(update.message.chat.id, 'OUCH; THAT HURT MY FEELINGS',
                                   disable_notification=conf.silent)
            return

        filename = None

        if update.message.reply_to_message.photo:
            photos = update.message.reply_to_message.photo
            photo = max(photos, key=lambda p: p.file_size)
            file = photo.get_file()

            filename = file.file_id + '.jpg'

            if not os.path.exists('files/' + filename):
                file.download(custom_path='files/' + filename)

        issue_warning(rebot, poster.poster_id,
                      update.message.reply_to_message.from_user.name,
                      update.message.reply_to_message.message_id,
                      update.message.chat.id, rebot.get_text(update.message.reply_to_message), filename, reason,
                      update.message.chat.type)
    except AttributeError:
        rebot.bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A MESSAGE TO WARN IT',
                               disable_notification=conf.silent)


def cmd_props(rebot, args, update):
    if not rebot.check_is_overlord(update.message.from_user.id):
        poster = rebot.db_conn.get_poster(update.message.from_user.id, update.message.from_user.name)
        rebot.bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')
        if conf.warn_on_admin:
            issue_warning(rebot, poster.poster_id, poster.name, update.message.message_id,
                          update.message.chat.id, rebot.get_text(update.message), None,
                          'UNAUTHORIZED PROPS ATTEMPT',
                          update.message.chat.type)
        return

    try:
        reason = 'GENERAL PROPS'
        if len(args) >= 1:
            reason = ' '.join(args)
        poster = rebot.db_conn.get_poster(update.message.reply_to_message.from_user.id,
                                     update.message.reply_to_message.from_user.name)

        if poster.poster_id == conf.bot_id:
            rebot.bot.send_message(update.message.chat.id, 'I ALREADY KNOW I\'M GOOD', disable_notification=conf.silent)
            return

        filename = None
        if update.message.reply_to_message.photo:
            photos = update.message.reply_to_message.photo
            photo = max(photos, key=lambda p: p.file_size)
            file = photo.get_file()

            filename = file.file_id + '.jpg'

            if not os.path.exists('files/' + filename):
                file.download(custom_path='files/' + filename)

        issue_props(rebot, poster.poster_id,
                    update.message.reply_to_message.from_user.name,
                    update.message.reply_to_message.message_id,
                    update.message.chat.id, rebot.get_text(update.message.reply_to_message), filename, reason)
    except AttributeError:
        rebot.bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A MESSAGE TO GIVE PROPS TO IT',
                               disable_notification=conf.silent)


def cmd_my_warnings(rebot, args, update):
    poster = rebot.db_conn.get_poster(update.message.from_user.id,
                                 update.message.from_user.name)

    count = rebot.db_conn.get_warning_count(poster.poster_id, update.message.chat.id)
    rebot.bot.send_message(update.message.chat.id,
                           'YOU [' + update.message.from_user.mention_markdown() +
                           '] HAVE ' + str(count) + ' WARNING' + ('' if count == 1 else 'S'),
                           parse_mode=telegram.ParseMode.MARKDOWN, disable_notification=conf.silent)


def cmd_my_props(rebot, args, update):
    poster = rebot.db_conn.get_poster(update.message.from_user.id,
                                 update.message.from_user.name)

    count = rebot.db_conn.get_props_count(poster.poster_id, update.message.chat.id)
    rebot.bot.send_message(update.message.chat.id,
                           'YOU [' + update.message.from_user.mention_markdown() +
                           '] HAVE ' + str(count) + ' PROPS',
                           parse_mode=telegram.ParseMode.MARKDOWN, disable_notification=conf.silent)


def cmd_list_props(rebot, args, update):
    try:
        poster = None

        if len(args) >= 1:
            poster = rebot.db_conn.find_user(' '.join(args))

        if poster is None:
            poster = rebot.db_conn.get_poster(update.message.reply_to_message.from_user.id,
                                         update.message.reply_to_message.from_user.name)

        if poster.poster_id != update.message.from_user.id and not rebot.check_is_overlord(update.message.from_user.id):
            rebot.bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
                                   disable_notification=conf.silent)
            return

        props = rebot.db_conn.get_props(poster.poster_id, update.message.chat.id)

        if len(props) == 0:
            rebot.bot.send_message(update.message.chat.id,
                                   'NO PROPS FOR USER ' + poster.name, disable_notification=conf.silent)
            return

        i = 1
        for prop in props:
            msg_text = str(prop.props_id) + '#P\nPROPS ' + str(
                i) + ' OF ' + poster.name + '\nREASON: ' + prop.reason
            try:
                rebot.bot.send_message(update.message.chat.id,
                                       msg_text,
                                       reply_to_message_id=prop.message_id, disable_notification=conf.silent)
            except telegram.error.BadRequest:
                if prop.photo_filename:
                    rebot.bot.send_photo(update.message.chat.id,
                                         open('files/' + prop.photo_filename, 'rb'),
                                         caption=msg_text + '\nORIGINAL MESSAGE: ' + str(prop.text),
                                         disable_notification=conf.silent)
                else:
                    rebot.bot.send_message(update.message.chat.id,
                                           msg_text + '\nORIGINAL MESSAGE: "' + str(prop.text) + '"',
                                           disable_notification=conf.silent)
            i += 1

    except AttributeError as e:
        rebot.bot.send_message(update.message.chat.id,
                               'YOU NEED TO REPLY TO A MESSAGE TO LIST THE USERS PROPS OR PASS THE USER AS AN ARGUMENT',
                               disable_notification=conf.silent)
        print('LISTPROPS: ' + str(e))


def cmd_list_warnings(rebot, args, update):
    try:
        poster = None

        if len(args) >= 1:
            poster = rebot.db_conn.find_user(' '.join(args))

        if poster is None:
            poster = rebot.db_conn.get_poster(update.message.reply_to_message.from_user.id,
                                         update.message.reply_to_message.from_user.name)

        if poster.poster_id != update.message.from_user.id and not rebot.check_is_overlord(update.message.from_user.id):
            rebot.bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
                                   disable_notification=conf.silent)
            return

        warnings = rebot.db_conn.get_warnings(poster.poster_id, update.message.chat.id)

        if len(warnings) == 0:
            rebot.bot.send_message(update.message.chat.id,
                                   'NO WARNINGS FOR USER ' + poster.name, disable_notification=conf.silent)
            return

        i = 1
        for warning in warnings:
            msg_text = str(warning.warning_id) + '#W\nWARNING ' + str(
                i) + ' OF ' + poster.name + '\nREASON: ' + warning.reason
            try:
                rebot.bot.send_message(update.message.chat.id,
                                       msg_text,
                                       reply_to_message_id=warning.message_id, disable_notification=conf.silent)
            except telegram.error.BadRequest:
                if warning.photo_filename:
                    rebot.bot.send_photo(update.message.chat.id,
                                         open('files/' + warning.photo_filename, 'rb'),
                                         caption=msg_text + '\nORIGINAL MESSAGE: "' + str(warning.text) + '"',
                                         disable_notification=conf.silent)
                else:
                    rebot.bot.send_message(update.message.chat.id,
                                           msg_text + '\nORIGINAL MESSAGE: "' + str(warning.text) + '"',
                                           disable_notification=conf.silent)
            i += 1

    except AttributeError as e:
        rebot.bot.send_message(update.message.chat.id,
                               'YOU NEED TO REPLY TO A MESSAGE TO LIST THE USERS WARNINGS OR PASS THE USER AS AN ARGUMENT',
                               disable_notification=conf.silent)
        print('LISTWARNINGS: ' + str(e))


def cmd_forgive(rebot, args, update):
    if not rebot.check_is_overlord(update.message.from_user.id):
        poster = rebot.db_conn.get_poster(update.message.from_user.id, update.message.from_user.name)
        rebot.bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')
        if conf.warn_on_admin:
            issue_warning(rebot, poster.poster_id, update.message.from_user.name, update.message.message_id,
                          update.message.chat.id, rebot.get_text(update.message), None,
                          'UNAUTHORIZED FORGIVE ATTEMPT',
                          update.message.chat.type)
        return

    try:
        warn_info = update.message.reply_to_message

        if warn_info.from_user.id != conf.bot_id:
            rebot.bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A WARNING TO FORGIVE IT',
                                   disable_notification=conf.silent)
            return

        warning_id = int(warn_info.text.split('#')[0])

        warning = rebot.db_conn.get_warning(warning_id)

        if warning is None:
            rebot.bot.send_message(update.message.chat.id, 'NO WARNING FOUND; MAY BE FORGIVEN ALREADY',
                                   disable_notification=conf.silent)
            return

        rebot.db_conn.forgive_warning(warning)

        poster = rebot.db_conn.get_poster(warning.poster_id, None)

        msg_text = 'WARNING OF USER ' + poster.name + ' ON ' + str(warning.timestamp) + ' FORGIVEN'
        try:
            rebot.bot.send_message(update.message.chat.id,
                                   msg_text + '\nORIGINAL MESSAGE IN REPLY',
                                   reply_to_message_id=warning.message_id, disable_notification=conf.silent)
        except telegram.error.BadRequest:
            rebot.bot.send_message(update.message.chat.id,
                                   msg_text + '\nORIGINAL MESSAGE DELETED', disable_notification=conf.silent)
    except (AttributeError, ValueError) as e:
        rebot.bot.send_message(update.message.chat.id,
                               'YOU NEED TO REPLY TO A WARNING TO FORGIVE IT',
                               disable_notification=conf.silent)
        print('FORGIVE: ' + str(e))


def cmd_withdraw(rebot, args, update):
    if not rebot.check_is_overlord(update.message.from_user.id):
        poster = rebot.db_conn.get_poster(update.message.from_user.id, update.message.from_user.name)
        rebot.bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')
        if conf.warn_on_admin:
            issue_warning(rebot, poster.poster_id, update.message.from_user.name, update.message.message_id,
                          update.message.chat.id, rebot.get_text(update.message), None,
                          'UNAUTHORIZED WITHDRAW ATTEMPT',
                          update.message.chat.type)
        return

    try:
        props_info = update.message.reply_to_message

        if props_info.from_user.id != conf.bot_id:
            rebot.bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A PROPS TO WITHDRAW IT',
                                   disable_notification=conf.silent)
            return

        props_id = int(props_info.text.split('#P')[0])

        props = rebot.db_conn.get_prop(props_id)

        if props is None:
            rebot.bot.send_message(update.message.chat.id, 'NO PROPS FOUND; MAY BE WITHDRAWN ALREADY',
                                   disable_notification=conf.silent)
            return

        rebot.db_conn.withdraw(props.props_id)

        poster = rebot.db_conn.get_poster(props.poster_id, None)

        msg_text = 'PROPS OF USER ' + poster.name + ' ON ' + str(props.timestamp) + ' WITHDRAWN'
        try:
            rebot.bot.send_message(update.message.chat.id,
                                   msg_text + '\nORIGINAL MESSAGE IN REPLY',
                                   reply_to_message_id=props.message_id, disable_notification=conf.silent)
        except telegram.error.BadRequest:
            rebot.bot.send_message(update.message.chat.id,
                                   msg_text + '\nORIGINAL MESSAGE DELETED', disable_notification=conf.silent)
    except (AttributeError, ValueError) as e:
        rebot.bot.send_message(update.message.chat.id,
                               'YOU NEED TO REPLY TO A PROPS TO WITHDRAW IT',
                               disable_notification=conf.silent)
        print('WITHDRAW: ' + str(e))
