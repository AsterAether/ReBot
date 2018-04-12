import db
import telegram
import conf
import time
import os
import sys
import threading

sys.path.append(conf.path_add)
import img
import datetime
import schedule
from difflib import SequenceMatcher


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


def issue_warning(poster_id, poster_name, message_id, chat_id, reason):
    if poster_id in conf.bot_overlords:
        return 0

    warning = db.Warning(message_id=message_id,
                         chat_id=chat_id,
                         timestamp=datetime.datetime.now(),
                         poster_id=poster_id,
                         reason=reason)

    db.save(warning)

    count = db.get_warning_count(poster_id, chat_id)

    poster = db.get_poster(poster_id, poster_name)

    try:
        bot.send_message(chat_id,
                         str(warning.warning_id) +
                         '#\nYOU [' + poster.name +
                         '] ARE WARNED\nREASON:' + reason + '\nWARNING NUMBER ' + str(count),
                         disable_notification=conf.silent,
                         reply_to_message_id=message_id)
    except telegram.error.BadRequest:
        bot.send_message(chat_id,
                         str(warning.warning_id) +
                         '#\nYOU [' + poster.name +
                         '] ARE WARNED\nREASON:' + reason + '\nWARNING NUMBER ' + str(count),
                         disable_notification=conf.silent)

    if update.message.chat.type == 'group':
        if conf.max_warnings - conf.kick_warn_threshold < count < conf.max_warnings:
            bot.send_message(chat_id, str(conf.max_warnings - count) + ' MORE WARNING' + (
                '' if count == 1 else 'S') + ' AND YOU WILL BE KICKED')
        elif count >= conf.max_warnings:
            bot.send_message(chat_id, '0 MORE WARNINGS AND YOU WILL BE KICKED')
            time.sleep(2)
            bot.send_message(chat_id, 'OH WAIT; IT\'S ALREADY TIME TO GO')
            time.sleep(1)
            bot.kick_chat_member(chat_id, poster_id)
            ban = db.Ban(chat_id=chat_id, poster_id=poster_id, timestamp=datetime.datetime.now())
            db.save(ban)
            db.forgive_warnings_for_poster(poster_id)


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

                    if conf.delete_reposts and update.message.chat.type == 'group':
                        repost = db.Repost(filename=filename,
                                           file_hash=p_hash,
                                           text=text,
                                           timestamp=datetime.datetime.now(),
                                           chat_id=update.message.chat.id,
                                           original_post_id=result['post_id'],
                                           post_type_id=1,
                                           similarity_index=img_distance,
                                           reposter_id=reposter.reposter_id
                                           )
                        db.save(repost)

                        try:
                            msg = bot.send_message(update.message.chat.id,
                                                   str(
                                                       repost.repost_id) + ';\nREPOST DETECTED FROM ' + update.message.from_user.mention_markdown()
                                                   + ' ON ' + result['timestamp'] + '; SIMILARITY INDEX: ' + str(
                                                       img_distance) + '\nORIGINAL IMAGE IN REPLY',
                                                   reply_to_message_id=result['message_id'],
                                                   parse_mode=telegram.ParseMode.MARKDOWN,
                                                   disable_notification=conf.silent)
                            if conf.warn_on_repost:
                                issue_warning(reposter.reposter_id,
                                              update.message.from_user.name,
                                              update.message.message_id,
                                              update.message.chat.id, 'IMAGE REPOST')
                            try:
                                update.message.delete()
                            except telegram.error.BadRequest:
                                print('MESSAGE ALREADY DELETED')
                                break

                            repost.message_id = msg.message_id
                            db.save(repost)
                        except telegram.error.BadRequest:
                            db.post_cleanup(result['message_id'], update.message.chat.id)
                    else:
                        try:
                            bot.send_message(update.message.chat.id,
                                             'REPOST DETECTED FROM ' + update.message.from_user.mention_markdown()
                                             + ' ON ' + result['timestamp'] + '; SIMILARITY INDEX: ' + str(
                                                 img_distance),
                                             reply_to_message_id=update.message.message_id,
                                             parse_mode=telegram.ParseMode.MARKDOWN,
                                             disable_notification=conf.silent)
                            bot.send_message(update.message.chat.id,
                                             'ORIGINAL IMAGE',
                                             reply_to_message_id=result['message_id'], disable_notification=conf.silent)
                            if conf.warn_on_repost:
                                issue_warning(reposter.reposter_id, update.message.from_user.name,
                                              update.message.message_id,
                                              update.message.chat.id, 'IMAGE REPOST')

                            repost = db.Repost(filename=filename,
                                               file_hash=p_hash,
                                               text=text,
                                               timestamp=datetime.datetime.now(),
                                               chat_id=update.message.chat.id,
                                               message_id=update.message.message_id,
                                               original_post_id=result['post_id'],
                                               post_type_id=1,
                                               similarity_index=img_distance,
                                               reposter_id=reposter.reposter_id
                                               )
                            db.save(repost)
                        except telegram.error.BadRequest:
                            db.post_cleanup(result['message_id'], update.message.chat.id)

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

                            if conf.delete_reposts and update.message.chat.type == 'group':

                                repost = db.Repost(filename_preview=filename,
                                                   file_preview_hash=p_hash,
                                                   preview_text=text,
                                                   url=url,
                                                   timestamp=datetime.datetime.now(),
                                                   chat_id=update.message.chat.id,
                                                   original_post_id=result['post_id'],
                                                   post_type_id=2,
                                                   similarity_index=img_distance,
                                                   reposter_id=reposter.reposter_id)
                                db.save(repost)
                                try:
                                    msg = bot.send_message(update.message.chat.id,
                                                           str(
                                                               repost.repost_id) + ';\nREPOST DETECTED FROM ' + update.message.from_user.mention_markdown()
                                                           + ' ON ' + result[
                                                               'timestamp'] + '; SIMILARITY INDEX: ' + str(
                                                               img_distance) +
                                                           '\nORIGINAL IMAGE IN REPLY',
                                                           reply_to_message_id=result['message_id'],
                                                           parse_mode=telegram.ParseMode.MARKDOWN,
                                                           disable_notification=conf.silent)
                                    if conf.warn_on_repost:
                                        issue_warning(reposter.reposter_id, update.message.from_user.name,
                                                      update.message.message_id,
                                                      update.message.chat.id, 'URL IMAGE REPOST')

                                    try:
                                        update.message.delete()
                                    except telegram.error.BadRequest:
                                        print('MESSAGE ALREADY DELETED')
                                        break

                                    repost.message_id = msg.message_id
                                    db.save(repost)
                                except telegram.error.BadRequest:
                                    db.post_cleanup(result['message_id'], update.message.chat.id)
                            else:
                                try:
                                    bot.send_message(update.message.chat.id,
                                                     'REPOST DETECTED FROM ' + update.message.from_user.mention_markdown() + ' ON ' +
                                                     result[
                                                         'timestamp'] + '; SIMILARITY INDEX: ' + str(
                                                         img_distance),
                                                     reply_to_message_id=update.message.message_id,
                                                     parse_mode=telegram.ParseMode.MARKDOWN,
                                                     disable_notification=conf.silent)
                                    bot.send_message(update.message.chat.id,
                                                     'ORIGINAL IMAGE',
                                                     reply_to_message_id=result['message_id'],
                                                     disable_notification=conf.silent)
                                    if conf.warn_on_repost:
                                        issue_warning(reposter.reposter_id, update.message.from_user.name,
                                                      update.message.message_id,
                                                      update.message.chat.id, 'URL IMAGE REPOST')
                                except telegram.error.BadRequest:
                                    db.post_cleanup(result['message_id'], update.message.chat.id)

                                repost = db.Repost(filename_preview=filename,
                                                   file_preview_hash=p_hash,
                                                   preview_text=text,
                                                   url=url,
                                                   timestamp=datetime.datetime.now(),
                                                   chat_id=update.message.chat.id,
                                                   message_id=update.message.message_id,
                                                   original_post_id=result['post_id'],
                                                   post_type_id=2,
                                                   similarity_index=img_distance,
                                                   reposter_id=reposter.reposter_id)
                                db.save(repost)
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

                        if conf.delete_reposts and update.message.chat.type == 'group':

                            repost = db.Repost(url=url,
                                               timestamp=datetime.datetime.now(),
                                               chat_id=update.message.chat.id,
                                               original_post_id=url_same_post.post_id,
                                               post_type_id=2,
                                               similarity_index=1,
                                               reposter_id=reposter.reposter_id)
                            db.save(repost)
                            try:
                                msg = bot.send_message(update.message.chat.id,
                                                       str(
                                                           repost.repost_id) + ';\nREPOST DETECTED FROM ' + update.message.from_user.mention_markdown()
                                                       + ' ON ' +
                                                       url_same_post.timestamp + '; REASON: URL\n' +
                                                       'ORIGINAL IMAGE IN REPLY',
                                                       reply_to_message_id=url_same_post.message_id,
                                                       parse_mode=telegram.ParseMode.MARKDOWN,
                                                       disable_notification=conf.silent)
                                if conf.warn_on_repost:
                                    issue_warning(reposter.reposter_id, update.message.from_user.name,
                                                  update.message.message_id,
                                                  update.message.chat.id, 'URL REPOST')

                                try:
                                    update.message.delete()
                                except telegram.error.BadRequest:
                                    print('MESSAGE ALREADY DELETED')

                                repost.message_id = msg.message_id
                                db.save(repost)
                            except telegram.error.BadRequest:
                                db.post_cleanup(url_same_post.message_id, update.message.chat.id)
                        else:
                            try:
                                bot.send_message(update.message.chat.id,
                                                 'REPOST DETECTED FROM ' + update.message.from_user.mention_markdown() + ' ON ' +
                                                 url_same_post.timestamp + '; REASON: URL',
                                                 reply_to_message_id=update.message.message_id,
                                                 parse_mode=telegram.ParseMode.MARKDOWN,
                                                 disable_notification=conf.silent)
                                bot.send_message(update.message.chat.id,
                                                 'ORIGINAL POST',
                                                 reply_to_message_id=url_same_post.message_id,
                                                 disable_notification=conf.silent)
                                if conf.warn_on_repost:
                                    issue_warning(reposter.reposter_id, update.message.from_user.name,
                                                  update.message.message_id,
                                                  update.message.chat.id, 'URL REPOST')

                                repost = db.Repost(url=url,
                                                   timestamp=datetime.datetime.now(),
                                                   chat_id=update.message.chat.id,
                                                   message_id=update.message.message_id,
                                                   original_post_id=url_same_post.post_id,
                                                   post_type_id=2,
                                                   similarity_index=1,
                                                   reposter_id=reposter.reposter_id)
                                db.save(repost)
                            except telegram.error.BadRequest:
                                db.post_cleanup(url_same_post.message_id, update.message.chat.id)
                    else:
                        post = db.Post(
                            url=url,
                            timestamp=datetime.datetime.now(),
                            chat_id=update.message.chat.id,
                            message_id=update.message.message_id,
                            post_type_id=2,
                            poster_id=db.get_poster(update.message.from_user.id,
                                                    update.message.from_user.name).poster_id)
                        db.save(post)


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
        issue_warning(poster.poster_id, poster.name, update.message.message_id,
                      update.message.chat.id,
                      'UNAUTHORIZED WARNING ATTEMPT')
        return

    try:
        reason = 'MANUAL WARNING'
        if len(args) >= 1:
            reason = args[0]
        poster = db.get_poster(update.message.reply_to_message.from_user.id,
                               update.message.reply_to_message.from_user.name)

        if poster.poster_id == conf.bot_id:
            bot.send_message(update.message.chat.id, 'PLEASE DON\'T TRY TO WARN ME', disable_notification=conf.silent)
            return

        issue_warning(poster.poster_id,
                      update.message.reply_to_message.from_user.name,
                      update.message.reply_to_message.message_id,
                      update.message.chat.id, reason)
    except AttributeError:
        bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A MESSAGE TO WARN IT',
                         disable_notification=conf.silent)


def cmd_my_warnings(args, update):
    poster = db.get_poster(update.message.from_user.id,
                           update.message.from_user.name)

    count = db.get_warning_count(poster.poster_id, update.message.chat.id)
    bot.send_message(update.message.chat.id,
                     'YOU [' + update.message.from_user.mention_markdown() +
                     '] HAVE ' + str(count) + ' WARNING' + ('' if count == 1 else 'S'),
                     parse_mode=telegram.ParseMode.MARKDOWN, disable_notification=conf.silent)


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
            msg_text = str(warning.warning_id) + '#\nWARNING ' + str(
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

        repost_id = int(repost_info.text.split(';')[0])

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
        issue_warning(poster.poster_id, update.message.from_user.name, update.message.message_id,
                      update.message.chat.id,
                      'UNAUTHORIZED NO-REPOST ATTEMPT')
        return

    try:
        repost_info = update.message.reply_to_message

        if repost_info.from_user.id != conf.bot_id:
            bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A REPOST DETECTION',
                             disable_notification=conf.silent)
            return

        repost_id = int(repost_info.text.split(';')[0])

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
        issue_warning(poster.poster_id, update.message.from_user.name, update.message.message_id,
                      update.message.chat.id,
                      'UNAUTHORIZED FORGIVE ATTEMPT')
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
            'help': lambda args, update: bot.send_message(update.message.chat.id,
                                                          'COMMANDS: ' + ', '.join(
                                                              ['/' + c for c in commands.keys()]),
                                                          disable_notification=conf.silent)}

# Admin CMDs (silent):
admin_commands = {
    'del': cmd_del
}


def handle_commands(update):
    if update.message and update.message.text and update.message.text.startswith('/'):
        command = update.message.text[1:]
        print('COMMAND RECEIVED: ' + command)
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


def main(pill):
    dirs = ['files', 'tmp']
    for dir in dirs:
        if not os.path.exists(dir):
            os.mkdir(dir)

    db.start_engine()
    db.start_session()

    offset = 0
    clear_count = 0

    schedule.every().thursday.at('8:00').do(post_random, conf.schedue_chat_id)
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
                    handle_commands(update)
            if len(updates) > 0:
                offset = updates[-1].update_id + 1
        except telegram.error.TimedOut:
            # print('No updates.')
            pass
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
    bot_thread = threading.Thread(target=main, name='bot_thread', args=(stop_pill, ))
    bot_thread.start()
    line_input = ''
    while line_input != 'exit':
        line_input = input('').strip()

    stop_pill.set()
