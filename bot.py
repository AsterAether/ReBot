import db
import telegram
import conf
import time
import os
import sys
import threading
import datetime
import binascii
import schedule
import base64
from bs4 import BeautifulSoup
import requests
from difflib import SequenceMatcher

sys.path.append(conf.path_add)
import img


def similar_text(a, b):
    return SequenceMatcher(None, a, b).ratio()


def tmp_clear():
    for the_file in os.listdir('tmp/'):
        file_path = os.path.join('tmp/', the_file)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except Exception as e:
            print(e)


def check_is_overlord(user_id):
    return user_id in conf.bot_overlords


def issue_warning(poster_id, poster_name, message_id, chat_id, reason, chat_type):
    if poster_id in conf.bot_overlords:
        return 0

    warning = db.Warning(message_id=message_id,
                         chat_id=chat_id,
                         timestamp=datetime.datetime.now(),
                         poster_id=poster_id,
                         reason=reason)

    db.save(warning)

    count = db.get_warning_count(poster_id, chat_id)

    props_count = db.get_props_count(poster_id, chat_id)

    poster = db.get_poster(poster_id, poster_name)

    try:
        bot.send_message(chat_id,
                         str(warning.warning_id) +
                         '#W\nYOU [' + poster.name +
                         '] ARE WARNED\nREASON:' + reason + '\nWARNING NUMBER ' + str(count),
                         disable_notification=conf.silent,
                         reply_to_message_id=message_id)
    except telegram.error.BadRequest:
        bot.send_message(chat_id,
                         str(warning.warning_id) +
                         '#W\nYOU [' + poster.name +
                         '] ARE WARNED\nREASON: ' + reason + '\nWARNING NUMBER ' + str(count),
                         disable_notification=conf.silent)

    if chat_type == 'group':
        if conf.max_warnings - conf.kick_warn_threshold < count - min(conf.props_max_minus,
                                                                      props_count) < conf.max_warnings:
            bot.send_message(chat_id, str(
                conf.max_warnings - count + min(conf.props_max_minus, props_count)) + ' MORE WARNING' + (
                                 '' if count == 1 else 'S') + ' AND YOU WILL BE KICKED')
        elif count - min(conf.props_max_minus, props_count) >= conf.max_warnings:
            bot.send_message(chat_id, '0 MORE WARNINGS AND YOU WILL BE KICKED')
            time.sleep(2)
            bot.send_message(chat_id, 'OH WAIT; IT\'S ALREADY TIME TO GO')
            time.sleep(1)
            bot.kick_chat_member(chat_id, poster_id)
            ban = db.Ban(chat_id=chat_id, poster_id=poster_id, timestamp=datetime.datetime.now())
            db.save(ban)
            db.forgive_warnings_for_poster(poster_id)


def issue_props(poster_id, poster_name, message_id, chat_id, reason):
    props = db.Props(message_id=message_id,
                     chat_id=chat_id,
                     timestamp=datetime.datetime.now(),
                     poster_id=poster_id,
                     reason=reason)

    db.save(props)

    count = db.get_props_count(poster_id, chat_id)

    poster = db.get_poster(poster_id, poster_name)

    try:
        bot.send_message(chat_id,
                         str(props.props_id) +
                         '#P\nPROPS TO  [' + poster.name +
                         ']\nREASON: ' + reason + '\nPROPS NUMBER ' + str(count),
                         disable_notification=conf.silent,
                         reply_to_message_id=message_id)
    except telegram.error.BadRequest:
        bot.send_message(chat_id,
                         str(props.props_id) +
                         '#P\nPROPS TO [' + poster.name +
                         ']\nREASON:' + reason + '\nWARNING NUMBER ' + str(count),
                         disable_notification=conf.silent)


def issue_repost(filename, p_hash, text, timestamp, chat_id, original_post_id, original_message_id, post_type_id,
                 sim_index, reposter_id,
                 update, delete,
                 repost_reason, url_repost=False):
    if delete:
        repost = db.Repost(filename=filename,
                           file_hash=p_hash,
                           text=text,
                           timestamp=timestamp,
                           chat_id=chat_id,
                           original_post_id=original_post_id,
                           post_type_id=post_type_id,
                           similarity_index=sim_index,
                           reposter_id=reposter_id
                           )
        db.save(repost)

        try:
            text = str(repost.repost_id) + '#R\nREPOST DETECTED FROM ' + \
                   update.message.from_user.mention_markdown() + ' ON ' + \
                   str(repost.timestamp) + ';'

            if sim_index:
                text += ' SIMILARITY INDEX: ' + str(sim_index)

            if url_repost:
                text += ' REASON: URL'

            if not url_repost:
                text += '\nORIGINAL IMAGE IN REPLY'
            else:
                text += '\nORIGINAL MESSAGE IN REPLY'

            msg = bot.send_message(chat_id,
                                   text,
                                   reply_to_message_id=original_message_id,
                                   parse_mode=telegram.ParseMode.MARKDOWN,
                                   disable_notification=conf.silent)
            if conf.warn_on_repost:
                issue_warning(reposter_id,
                              update.message.from_user.name,
                              update.message.message_id,
                              chat_id, repost_reason,
                              update.message.chat.type)
            try:
                update.message.delete()
            except telegram.error.BadRequest:
                print('MESSAGE ALREADY DELETED')
                return True

            repost.message_id = msg.message_id
            db.save(repost)
        except telegram.error.BadRequest:
            db.post_cleanup(original_post_id, update.message.chat.id)
    else:
        try:
            text = '\nREPOST DETECTED FROM ' + \
                   update.message.from_user.mention_markdown() + ' ON ' + \
                   str(timestamp) + ';'

            if sim_index:
                text += ' SIMILARITY INDEX: ' + str(sim_index)

            if url_repost:
                text += ' REASON: URL'

            try:
                bot.send_message(update.message.chat.id,
                                 text,
                                 reply_to_message_id=update.message.message_id,
                                 parse_mode=telegram.ParseMode.MARKDOWN,
                                 disable_notification=conf.silent)
            except telegram.error.BadRequest:
                print('REPOST ALREADY DELETED')
                return True

            text = 'ORIGINAL IMAGE' if not url_repost else 'ORIGINAL MESSAGE'
            bot.send_message(update.message.chat.id,
                             text,
                             reply_to_message_id=original_message_id, disable_notification=conf.silent)
            if conf.warn_on_repost:
                issue_warning(reposter_id, update.message.from_user.name,
                              update.message.message_id,
                              chat_id, repost_reason,
                              update.message.chat.type)

            repost = db.Repost(filename=filename,
                               file_hash=p_hash,
                               text=text,
                               timestamp=timestamp,
                               chat_id=update.message.chat.id,
                               message_id=update.message.message_id,
                               original_post_id=original_post_id,
                               post_type_id=post_type_id,
                               similarity_index=sim_index,
                               reposter_id=reposter_id
                               )
            db.save(repost)
        except telegram.error.BadRequest:
            db.post_cleanup(original_post_id, update.message.chat.id)
    return False


def handle_repost(update):
    if update.message:
        if update.message.document:
            pass
        if update.message.photo:
            photos = update.message.photo
            photo = max(photos, key=lambda p: p.file_size)
            file = photo.get_file()

            filename = file.file_id + '.jpg'
            file.download(custom_path='files/' + filename)

            img.image_crop(filename)

            p_hash = img.image_perception_hash(filename)

            text = img.image_to_string(filename)

            results = db.get_similar_posts(p_hash, update.message.chat.id)

            is_repost = False

            for result in results:
                print(result)
                r_filename = result['filename']
                if not r_filename:
                    r_filename = result['filename_preview']
                r_text = result['text']
                if not r_text:
                    r_text = result['preview_text']
                img_distance = img.compare_image_ssim(filename, r_filename)
                print(img_distance)
                if img_distance >= conf.img_threshold or (
                        img_distance >= conf.img_text_chk_threshold
                        and text and r_text
                        and (similar_text(text, r_text) >= conf.text_threshold)):
                    is_repost = True

                    reposter = db.get_reposter(update.message.from_user.id,
                                               update.message.from_user.name)

                    delete_repost = conf.delete_reposts and update.message.chat.type == 'group'

                    issue_repost(filename, p_hash, text, datetime.datetime.now(), update.message.chat.id,
                                 result['post_id'], result['message_id'], 1, img_distance, reposter.reposter_id,
                                 update, delete_repost, 'IMAGE REPOST')
                    break
            if not is_repost:
                post = db.Post(filename=filename,
                               file_hash=p_hash,
                               text=text,
                               timestamp=datetime.datetime.now(),
                               chat_id=update.message.chat.id,
                               message_id=update.message.message_id,
                               post_type_id=1,
                               poster_id=db.get_poster(update.message.from_user.id,
                                                       update.message.from_user.name).poster_id)
                db.save(post)
        if update.message.text:
            urls = update.message.parse_entities(types=['url'])
            if len(urls) > 0:
                urlEntity, text = urls.popitem()
                url = text
                filename = str(update.message.chat.id) + '_' + str(update.message.message_id)

                filename = img.handle_url_image(url, filename)

                if filename:

                    img.image_crop(filename)

                    p_hash = img.image_perception_hash(filename)

                    text = img.image_to_string(filename)

                    results = db.get_similar_posts(p_hash, update.message.chat.id)

                    is_repost = False

                    for result in results:
                        print(result)
                        r_filename = result['filename']
                        if not r_filename:
                            r_filename = result['filename_preview']

                        r_text = result['text']
                        if not r_text:
                            r_text = result['preview_text']
                        img_distance = img.compare_image_ssim(filename, r_filename)
                        print(img_distance)
                        if img_distance >= conf.img_threshold or (
                                img_distance >= conf.img_text_chk_threshold
                                and text and r_text
                                and (similar_text(text, r_text) >= conf.text_threshold)):
                            is_repost = True

                            reposter = db.get_reposter(update.message.from_user.id,
                                                       update.message.from_user.name)

                            delete_repost = conf.delete_reposts and update.message.chat.type == 'group'
                            issue_repost(filename, p_hash, text, datetime.datetime.now(), update.message.chat.id,
                                         result['post_id'], result['message_id'], 2, img_distance,
                                         reposter.reposter_id,
                                         update, delete_repost, 'URL IMAGE REPOST')
                            break
                    if not is_repost:
                        post = db.Post(filename_preview=filename,
                                       file_preview_hash=p_hash,
                                       preview_text=text,
                                       url=url,
                                       timestamp=datetime.datetime.now(),
                                       chat_id=update.message.chat.id,
                                       message_id=update.message.message_id,
                                       post_type_id=2,
                                       poster_id=db.get_poster(update.message.from_user.id,
                                                               update.message.from_user.name).poster_id)
                        db.save(post)
                else:
                    url_same_post = db.get_same_url_post(url, update.message.chat.id)

                    if url_same_post:
                        reposter = db.get_reposter(update.message.from_user.id,
                                                   update.message.from_user.name)

                        delete_repost = conf.delete_reposts and update.message.chat.type == 'group'
                        issue_repost(filename, None, text, datetime.datetime.now(), update.message.chat.id,
                                     url_same_post.post_id, url_same_post.message_id, 2, None,
                                     reposter.reposter_id,
                                     update, delete_repost, 'URL REPOST', True)


def handle_import(update):
    if update.message:
        if not update.message.forward_from:
            return

        print(update)
        poster = db.get_poster(update.message.forward_from.id,
                               update.message.forward_from.name)

        timestamp = update.message.forward_date

        if update.message.photo:
            photos = update.message.photo
            photo = max(photos, key=lambda p: p.file_size)
            file = photo.get_file()

            filename = file.file_id + '.jpg'

            if db.post_exists(filename):
                print('ALREADY EXISTS: ' + filename)
                return

            file.download(custom_path='files/' + filename)

            img.image_crop(filename)

            p_hash = img.image_perception_hash(filename)

            text = img.image_to_string(filename)
            post = db.Post(filename=filename,
                           file_hash=p_hash,
                           text=text,
                           timestamp=timestamp,
                           post_type_id=1,
                           poster_id=poster.poster_id)
            db.save(post)
            print('IMPORTED ' + filename)


def cmd_start(args, update):
    bot.send_message(update.message.chat.id, 'HELLO; IF YOU NEED HELP CALL /help', disable_notification=conf.silent)


def cmd_warn(args, update):
    if not check_is_overlord(update.message.from_user.id):
        poster = db.get_poster(update.message.from_user.id, update.message.from_user.name)
        bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')
        if conf.warn_on_admin:
            issue_warning(poster.poster_id, poster.name, update.message.message_id,
                          update.message.chat.id,
                          'UNAUTHORIZED WARNING ATTEMPT',
                          update.message.chat.type)
        return

    try:
        reason = 'MANUAL WARNING'
        if len(args) >= 1:
            reason = args[0]
        poster = db.get_poster(update.message.reply_to_message.from_user.id,
                               update.message.reply_to_message.from_user.name)

        if poster.poster_id == conf.bot_id:
            bot.send_message(update.message.chat.id, 'OUCH; THAT HURT MY FEELINGS', disable_notification=conf.silent)
            return

        issue_warning(poster.poster_id,
                      update.message.reply_to_message.from_user.name,
                      update.message.reply_to_message.message_id,
                      update.message.chat.id, reason,
                      update.message.chat.type)
    except AttributeError:
        bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A MESSAGE TO WARN IT',
                         disable_notification=conf.silent)


def cmd_props(args, update):
    if not check_is_overlord(update.message.from_user.id):
        poster = db.get_poster(update.message.from_user.id, update.message.from_user.name)
        bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')
        if conf.warn_on_admin:
            issue_warning(poster.poster_id, poster.name, update.message.message_id,
                          update.message.chat.id,
                          'UNAUTHORIZED PROPS ATTEMPT',
                          update.message.chat.type)
        return

    try:
        reason = 'GENERAL PROPS'
        if len(args) >= 1:
            reason = args[0]
        poster = db.get_poster(update.message.reply_to_message.from_user.id,
                               update.message.reply_to_message.from_user.name)

        if poster.poster_id == conf.bot_id:
            bot.send_message(update.message.chat.id, 'I ALREADY KNOW I\'M GOOD', disable_notification=conf.silent)
            return

        issue_props(poster.poster_id,
                    update.message.reply_to_message.from_user.name,
                    update.message.reply_to_message.message_id,
                    update.message.chat.id, reason)
    except AttributeError:
        bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A MESSAGE TO GIVE PROPS TO IT',
                         disable_notification=conf.silent)


def cmd_my_warnings(args, update):
    poster = db.get_poster(update.message.from_user.id,
                           update.message.from_user.name)

    count = db.get_warning_count(poster.poster_id, update.message.chat.id)
    bot.send_message(update.message.chat.id,
                     'YOU [' + update.message.from_user.mention_markdown() +
                     '] HAVE ' + str(count) + ' WARNING' + ('' if count == 1 else 'S'),
                     parse_mode=telegram.ParseMode.MARKDOWN, disable_notification=conf.silent)


def cmd_my_props(args, update):
    poster = db.get_poster(update.message.from_user.id,
                           update.message.from_user.name)

    count = db.get_props_count(poster.poster_id, update.message.chat.id)
    bot.send_message(update.message.chat.id,
                     'YOU [' + update.message.from_user.mention_markdown() +
                     '] HAVE ' + str(count) + ' PROPS',
                     parse_mode=telegram.ParseMode.MARKDOWN, disable_notification=conf.silent)


def cmd_list_props(args, update):
    try:
        poster = None

        if len(args) >= 1:
            poster = db.find_user(' '.join(args))

        if poster is None:
            poster = db.get_poster(update.message.reply_to_message.from_user.id,
                                   update.message.reply_to_message.from_user.name)

        if poster.poster_id != update.message.from_user.id and not check_is_overlord(update.message.from_user.id):
            bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
                             disable_notification=conf.silent)
            return

        props = db.get_props(poster.poster_id, update.message.chat.id)

        if len(props) == 0:
            bot.send_message(update.message.chat.id,
                             'NO PROPS FOR USER ' + poster.name, disable_notification=conf.silent)
            return

        i = 1
        for prop in props:
            msg_text = str(prop.props_id) + '#P\nPROPS ' + str(
                i) + ' OF ' + poster.name + '\nREASON: ' + prop.reason
            try:
                bot.send_message(update.message.chat.id,
                                 msg_text,
                                 reply_to_message_id=prop.message_id, disable_notification=conf.silent)
            except telegram.error.BadRequest:
                bot.send_message(update.message.chat.id,
                                 msg_text + '\nORIGINAL MESSAGE DELETED', disable_notification=conf.silent)
            i += 1

    except AttributeError as e:
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A MESSAGE TO LIST THE USERS PROPS OR PASS THE USER AS AN ARGUMENT',
                         disable_notification=conf.silent)
        print('LISTPROPS: ' + str(e))


def cmd_list_warnings(args, update):
    try:
        poster = None

        if len(args) >= 1:
            poster = db.find_user(' '.join(args))

        if poster is None:
            poster = db.get_poster(update.message.reply_to_message.from_user.id,
                                   update.message.reply_to_message.from_user.name)

        if poster.poster_id != update.message.from_user.id and not check_is_overlord(update.message.from_user.id):
            bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
                             disable_notification=conf.silent)
            return

        warnings = db.get_warnings(poster.poster_id, update.message.chat.id)

        if len(warnings) == 0:
            bot.send_message(update.message.chat.id,
                             'NO WARNINGS FOR USER ' + poster.name, disable_notification=conf.silent)
            return

        i = 1
        for warning in warnings:
            msg_text = str(warning.warning_id) + '#W\nWARNING ' + str(
                i) + ' OF ' + poster.name + '\nREASON: ' + warning.reason
            try:
                bot.send_message(update.message.chat.id,
                                 msg_text,
                                 reply_to_message_id=warning.message_id, disable_notification=conf.silent)
            except telegram.error.BadRequest:
                bot.send_message(update.message.chat.id,
                                 msg_text + '\nORIGINAL MESSAGE DELETED', disable_notification=conf.silent)
            i += 1

    except AttributeError as e:
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A MESSAGE TO LIST THE USERS WARNINGS OR PASS THE USER AS AN ARGUMENT',
                         disable_notification=conf.silent)
        print('LISTWARNINGS: ' + str(e))


def cmd_post_stats(args, update):
    try:
        poster = None
        if len(args) >= 1:
            poster = db.find_user(' '.join(args))

        if poster is None:
            poster = db.get_poster(update.message.reply_to_message.from_user.id,
                                   update.message.reply_to_message.from_user.name)

        post_count, repost_count = db.get_post_stats(poster.poster_id, update.message.chat.id)

        bot.send_message(update.message.chat.id, 'USER [' + poster.name + '] HAS ' + str(post_count) + ' POST' +
                         ('' if post_count == 1 else 'S') + ' AND ' + str(repost_count) + ' REPOST' +
                         ('' if repost_count == 1 else 'S'), disable_notification=conf.silent)

    except AttributeError:
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A MESSAGE TO LIST THE USERS STATS OR PASS THE USER AS AN ARGUMENT',
                         disable_notification=conf.silent)


def cmd_get_repost(args, update):
    if not check_is_overlord(update.message.from_user.id):
        bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
                         disable_notification=conf.silent)
        return

    try:
        repost_info = update.message.reply_to_message

        if repost_info.from_user.id != conf.bot_id:
            bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A REPOST DETECTION',
                             disable_notification=conf.silent)
            return

        repost_id = int(repost_info.text.split('#R')[0])

        repost = db.get_repost(repost_id)
        poster = db.get_poster(repost.reposter_id, None)

        if repost.post_type_id == 1:
            bot.send_photo(update.message.chat.id, repost.filename.replace('.jpg', ''),
                           caption='REPOST FROM ' + poster.name + ' AT ' + str(repost.timestamp))
        elif repost.post_type_id == 2:
            bot.send_message(update.message.chat.id,
                             repost.url + '\nREPOST FROM ' + poster.name + ' AT ' + str(repost.timestamp),
                             disable_notification=conf.silent)

    except (AttributeError, ValueError):
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A REPOST DETECTION TO GET THE REPOST', disable_notification=conf.silent)


def cmd_random_post(args, update):
    if not check_is_overlord(update.message.from_user.id):
        bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
                         disable_notification=conf.silent)
        return

    post_random(update.message.chat.id)


def post_random(chat_id):
    post = db.get_random_post(chat_id)
    if not post:
        bot.send_message(chat_id, 'NO POSTS FOUND', conf.silent)
        return
    poster = db.get_poster(post.poster_id, None)
    if post.post_type_id == 1:
        bot.send_photo(chat_id, post.filename.replace('.jpg', ''),
                       caption='POST FROM ' + poster.name + ' AT ' + str(post.timestamp))
    elif post.post_type_id == 2:
        bot.send_message(chat_id,
                         post.url + '\nPOST FROM ' + poster.name + ' AT ' + str(post.timestamp),
                         disable_notification=conf.silent)


def cmd_get_text(args, update):
    try:
        post_info = update.message.reply_to_message

        post = db.get_post_per_message(post_info.message_id, update.message.chat.id)
        if post:
            bot.send_message(update.message.chat.id,
                             'TEXT:\n' + post.text,
                             reply_to_message_id=post.message_id, disable_notification=conf.silent)
        else:
            bot.send_message(update.message.chat.id,
                             'I DON\'T HAVE THIS POST SAVED', disable_notification=conf.silent)

    except AttributeError:
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A POST TO GET ITS TEXT', disable_notification=conf.silent)


def cmd_no_repost(args, update):
    if not check_is_overlord(update.message.from_user.id):
        poster = db.get_poster(update.message.from_user.id, update.message.from_user.name)
        bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')
        if conf.warn_on_admin:
            issue_warning(poster.poster_id, update.message.from_user.name, update.message.message_id,
                          update.message.chat.id,
                          'UNAUTHORIZED NO-REPOST ATTEMPT',
                          update.message.chat.type)
        return

    try:
        repost_info = update.message.reply_to_message

        if repost_info.from_user.id != conf.bot_id:
            bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A REPOST DETECTION',
                             disable_notification=conf.silent)
            return

        repost_id = int(repost_info.text.split('#R')[0])

        repost = db.get_repost(repost_id)

        db.forgive_repost(repost)

        poster = db.get_poster(repost.reposter_id, None)

        if conf.delete_reposts:
            if repost.post_type_id == 1:
                bot.send_photo(update.message.chat.id, repost.filename.replace('.jpg', ''),
                               caption='FORGIVEN REPOST FROM ' + poster.name + ' AT ' + str(repost.timestamp))
            elif repost.post_type_id == 2:
                bot.send_message(update.message.chat.id,
                                 repost.url + '\nFORGIVEN REPOST FROM ' + poster.name + ' AT ' + str(repost.timestamp),
                                 disable_notification=conf.silent)

            try:
                bot.delete_message(update.message.chat.id, repost.message_id)
            except telegram.error.BadRequest:
                print('MESSAGE ALREADY DELETED')
        else:
            bot.send_message(update.message.chat.id,
                             'REPOST FORGIVEN FROM ' + poster.name + ' AT ' + str(repost.timestamp),
                             disable_notification=conf.silent,
                             reply_to_message_id=repost.message_id)

        if repost.filename:
            os.remove('files/' + repost.filename)
        if repost.filename_preview:
            os.remove('files/' + repost.filename_preview)
    except (AttributeError, ValueError):
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A REPOST DETECTION TO FORGIVE THE REPOST',
                         disable_notification=conf.silent)


def cmd_forgive(args, update):
    if not check_is_overlord(update.message.from_user.id):
        poster = db.get_poster(update.message.from_user.id, update.message.from_user.name)
        bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')
        if conf.warn_on_admin:
            issue_warning(poster.poster_id, update.message.from_user.name, update.message.message_id,
                          update.message.chat.id,
                          'UNAUTHORIZED FORGIVE ATTEMPT',
                          update.message.chat.type)
        return

    try:
        warn_info = update.message.reply_to_message

        if warn_info.from_user.id != conf.bot_id:
            bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A WARNING TO FORGIVE IT',
                             disable_notification=conf.silent)
            return

        warning_id = int(warn_info.text.split('#')[0])

        warning = db.get_warning(warning_id)

        if warning is None:
            bot.send_message(update.message.chat.id, 'NO WARNING FOUND; MAY BE FORGIVEN ALREADY',
                             disable_notification=conf.silent)
            return

        db.forgive_warning(warning)

        poster = db.get_poster(warning.poster_id, None)

        msg_text = 'WARNING OF USER ' + poster.name + ' ON ' + str(warning.timestamp) + ' FORGIVEN'
        try:
            bot.send_message(update.message.chat.id,
                             msg_text + '\nORIGINAL MESSAGE IN REPLY',
                             reply_to_message_id=warning.message_id, disable_notification=conf.silent)
        except telegram.error.BadRequest:
            bot.send_message(update.message.chat.id,
                             msg_text + '\nORIGINAL MESSAGE DELETED', disable_notification=conf.silent)
    except (AttributeError, ValueError) as e:
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A WARNING TO FORGIVE IT',
                         disable_notification=conf.silent)
        print('FORGIVE: ' + str(e))


def cmd_withdraw(args, update):
    if not check_is_overlord(update.message.from_user.id):
        poster = db.get_poster(update.message.from_user.id, update.message.from_user.name)
        bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')
        if conf.warn_on_admin:
            issue_warning(poster.poster_id, update.message.from_user.name, update.message.message_id,
                          update.message.chat.id,
                          'UNAUTHORIZED WITHDRAW ATTEMPT',
                          update.message.chat.type)
        return

    try:
        props_info = update.message.reply_to_message

        if props_info.from_user.id != conf.bot_id:
            bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A PROPS TO WITHDRAW IT',
                             disable_notification=conf.silent)
            return

        props_id = int(props_info.text.split('#P')[0])

        props = db.get_prop(props_id)

        if props is None:
            bot.send_message(update.message.chat.id, 'NO PROPS FOUND; MAY BE WITHDRAWN ALREADY',
                             disable_notification=conf.silent)
            return

        db.withdraw(props.props_id)

        poster = db.get_poster(props.poster_id, None)

        msg_text = 'PROPS OF USER ' + poster.name + ' ON ' + str(props.timestamp) + ' WITHDRAWN'
        try:
            bot.send_message(update.message.chat.id,
                             msg_text + '\nORIGINAL MESSAGE IN REPLY',
                             reply_to_message_id=props.message_id, disable_notification=conf.silent)
        except telegram.error.BadRequest:
            bot.send_message(update.message.chat.id,
                             msg_text + '\nORIGINAL MESSAGE DELETED', disable_notification=conf.silent)
    except (AttributeError, ValueError) as e:
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A PROPS TO WITHDRAW IT',
                         disable_notification=conf.silent)
        print('WITHDRAW: ' + str(e))


def cmd_base64(args, update):
    text = ''

    try:
        text = update.message.reply_to_message.text
    except AttributeError:
        pass

    if not text and len(args) == 0:
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A MESSAGE OR PROVIDE TEXT', disable_notification=conf.silent)
        return
    elif not text:
        text = ' '.join(args)

    b64_text = str(base64.b64encode(bytes(text, 'utf8')), 'utf8')

    try:
        bot.send_message(update.message.chat.id,
                         b64_text,
                         disable_notification=conf.silent,
                         reply_to_message_id=update.message.message_id)
    except telegram.error.BadRequest:
        pass


def cmd_unbase64(args, update):
    b64_text = ''

    try:
        b64_text = update.message.reply_to_message.text
    except AttributeError:
        pass

    if not b64_text and len(args) == 0:
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A MESSAGE OR PROVIDE TEXT', disable_notification=conf.silent)
        return
    elif not b64_text:
        b64_text = ' '.join(args)

    try:
        text = str(base64.b64decode(bytes(b64_text, 'utf8')), 'utf8')
    except binascii.Error:
        bot.send_message(update.message.chat.id,
                         'NOT A BASE64 STRING', disable_notification=conf.silent)
        return

    try:
        bot.send_message(update.message.chat.id,
                         text,
                         disable_notification=conf.silent,
                         reply_to_message_id=update.message.message_id)
    except telegram.error.BadRequest:
        pass


def post_bad_joke(chat_id):
    joke_resp = requests.get('https://www.davepagurek.com/badjokes/getjoke.php')
    bs4 = BeautifulSoup(joke_resp.text, 'html.parser')

    headline = bs4.find('h2').text.upper()
    joke = bs4.find('h3').text.upper()
    id = bs4.find('input', {}).get('value')
    bot.send_message(chat_id, id + '#J\n*' + headline + '*\n\n' + joke,
                     parse_mode=telegram.ParseMode.MARKDOWN,
                     disable_notification=conf.silent)


def cmd_bad_joke(args, update):
    post_bad_joke(update.message.chat.id)


def cmd_flag_joke(args, update):
    try:
        if update.message.reply_to_message.from_user.id != conf.bot_id:
            bot.send_message(update.message.chat.id,
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
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A JOKE TO FLAG IT', disable_notification=conf.silent)


def cmd_del(args, update):
    if not check_is_overlord(update.message.from_user.id):
        # bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
        #                  disable_notification=conf.silent)
        poster = db.get_poster(update.message.from_user.id, update.message.from_user.name)
        print('USER ' + poster.name + ' TRIED TO CALL DEL')
        return

    try:
        info = update.message.reply_to_message
        try:
            info.delete()
        except telegram.error.BadRequest:
            print('ERROR ON DEL: MESSAGE ALREADY DELETED')
        except AttributeError:
            print('ERROR ON DEL: NO MESSAGE IN REPLY TO DELETE')

        try:
            update.message.delete()
        except telegram.error.BadRequest:
            print('ERROR ON DEL: COMMAND MESSAGE DELETED')
    except (AttributeError, ValueError) as e:
        print('ERROR ON DEL' + str(e))


def cmd_msg(args, update):
    if not check_is_overlord(update.message.from_user.id):
        # bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
        #                  disable_notification=conf.silent)
        poster = db.get_poster(update.message.from_user.id, update.message.from_user.name)
        print('USER ' + poster.name + ' TRIED TO CALL MSG')
        return

    if len(args) == 0:
        print('ERROR ON MSG: ARGUMENT NEEDED')
        return

    text = ' '.join(args)

    bot.send_message(update.message.chat.id, text.upper())

    try:
        update.message.delete()
    except telegram.error.BadRequest:
        print('ERROR ON MSG: COMMAND MESSAGE DELETED')


def cmd_msg_chat(args, update):
    if not check_is_overlord(update.message.from_user.id):
        # bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
        #                  disable_notification=conf.silent)
        poster = db.get_poster(update.message.from_user.id, update.message.from_user.name)
        print('USER ' + poster.name + ' TRIED TO CALL MSG_CHAT')
        return

    if len(args) <= 1:
        print('ERROR ON MSG_CHAT: ARGUMENT NEEDED')
        return

    text = ' '.join(args[1:])
    try:
        chat_id = int(args[0])
    except ValueError:
        print('ERROR ON MSG_CHAT: ID NOT INT')
        return

    try:
        bot.send_message(chat_id, text.upper())
    except telegram.error.BadRequest as e:
        print('ERROR ON MSG_CHAT: ' + str(e))

    try:
        update.message.delete()
    except telegram.error.BadRequest:
        print('ERROR ON MSG_CHAT: COMMAND MESSAGE DELETED')


commands = {'start': cmd_start,
            'warn': cmd_warn,
            'mywarnings': cmd_my_warnings,
            'listwarnings': cmd_list_warnings,
            'poststats': cmd_post_stats,
            'getrepost': cmd_get_repost,
            'randompost': cmd_random_post,
            'gettext': cmd_get_text,
            'norepost': cmd_no_repost,
            'forgive': cmd_forgive,
            'b64': cmd_base64,
            'unb64': cmd_unbase64,
            'props': cmd_props,
            'listprops': cmd_list_props,
            'myprops': cmd_my_props,
            'withdraw': cmd_withdraw,
            'badjoke': cmd_bad_joke,
            'flagjoke': cmd_flag_joke,
            'help': lambda args, update: bot.send_message(update.message.chat.id,
                                                          'COMMANDS: ' + ', '.join(
                                                              ['/' + c for c in commands.keys()]),
                                                          disable_notification=conf.silent)}

# Admin CMDs (silent):
admin_commands = {
    'del': cmd_del,
    'msg': cmd_msg,
    'msgc': cmd_msg_chat
}


def command_allowed(poster_id, chat_id, user_jail):
    if chat_id not in user_jail:
        user_jail[chat_id] = {}

    chat_jail = user_jail[chat_id]

    if poster_id in conf.bot_overlords:
        return True

    if poster_id not in chat_jail:
        chat_jail[poster_id] = 1
        return True

    if chat_jail[poster_id] >= conf.max_cmds:
        return False

    chat_jail[poster_id] += 1
    return True


def handle_commands(update, user_jail):
    if update.message and update.message.text and update.message.text.startswith('/'):
        command = update.message.text[1:]
        print('COMMAND RECEIVED: ' + command + ' FROM ' + update.message.from_user.name)
        if update.message.from_user.id in user_jail:
            print('TRIES: ' + str(user_jail[update.message.from_user.id]))
        if update.message.chat.type == 'group':
            if not command_allowed(update.message.from_user.id, update.message.chat.id, user_jail):
                return
        cmd_split = command.split(' ')
        cmd = cmd_split[0]
        args = cmd_split[1:]

        if update.message.chat.type == 'group':
            if conf.bot_name in cmd:
                cmd = cmd.replace(conf.bot_name, '')
            elif '@' in cmd:
                return

        try:
            commands[cmd](args, update)
        except KeyError:
            if cmd not in admin_commands or not check_is_overlord(update.message.from_user.id):
                bot.send_message(update.message.chat.id, 'I DON\'T RECOGNIZE THIS COMMAND: ' + cmd,
                                 disable_notification=conf.silent)
        try:
            admin_commands[cmd](args, update)
        except KeyError:
            pass


def reset_jail(user_jail):
    user_jail.clear()


def main(pill):
    user_jail = {}
    dirs = ['files', 'tmp']
    for dir in dirs:
        if not os.path.exists(dir):
            os.mkdir(dir)

    db.start_engine()
    db.start_session()

    offset = 0
    clear_count = 0

    schedule.every().thursday.at('8:00').do(post_random, conf.schedue_chat_id)
    schedule.every().day.at('8:00').at('12:00').at('18:00').do(post_bad_joke, conf.schedue_chat_id)
    schedule.every(conf.reset_cmds).minutes.do(reset_jail, user_jail)
    while not pill.is_set():
        try:
            updates = bot.get_updates(offset=offset)
            for update in updates:
                # print(update)
                # if update.message:
                #     print(update.message.parse_entities())
                if conf.import_mode:
                    handle_import(update)
                else:
                    handle_repost(update)
                    handle_commands(update, user_jail)
            if len(updates) > 0:
                offset = updates[-1].update_id + 1
        except telegram.error.TimedOut:
            # print('No updates.')
            pass
        except telegram.error.TelegramError as e:
            print('Error: ' + str(e))
        clear_count += 1
        if clear_count == conf.clear_every:
            tmp_clear()
            clear_count = 0

        schedule.run_pending()
        time.sleep(conf.timeout)

    db.stop_session()
    db.stop_engine()


if __name__ == '__main__':
    bot = telegram.Bot(token=conf.token)
    stop_pill = threading.Event()
    bot_thread = threading.Thread(target=main, name='bot_thread', args=(stop_pill,))
    bot_thread.start()
    line_input = ''
    while line_input != 'exit':
        line_input = input('').strip()
        # try:
        #     cmd = line_input.split(' ')
        # except (KeyError, ValueError):
        #     print('ERROR IN INPUT: ' + line_input)

    stop_pill.set()
