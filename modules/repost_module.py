import conf
import sys
from difflib import SequenceMatcher
import telegram
import datetime
import os
import db

sys.path.append(conf.path_add)
import img


def register(rebot):
    rebot.register_update_handle('repost_module', handle_update)
    commands = rebot.get_module_commands('repost_module')
    commands['poststats'] = cmd_post_stats
    commands['getrepost'] = cmd_get_repost
    commands['randompost'] = cmd_random_post
    commands['gettext'] = cmd_get_text
    commands['norepost'] = cmd_no_repost
    rebot.scheduler.every().thursday.at('8:00').tag('repost').do(repost_thursday, rebot)


def unregister(rebot):
    rebot.del_module_commands('repost_module')
    rebot.scheduler.clear('repost')
    rebot.del_update_handles('repost_module')


def repost_thursday(rebot):
    for chat in rebot.chat_config:
        if rebot.get_chat_conf(chat, 'repost_thursday'):
            post_random(rebot, chat)


def similar_text(a, b):
    return SequenceMatcher(None, a, b).ratio()


def handle_update(rebot, update):
    if conf.import_mode:
        handle_import(rebot, update)
    else:
        handle_repost(rebot, update)


def issue_repost(rebot, filename, p_hash, text, timestamp, chat_id, original_post_id, original_message_id, post_type_id,
                 sim_index, reposter_id,
                 update, delete,
                 repost_reason, msg_text, url, url_repost=False):
    warn = None
    if 'warn_module' in rebot.modules.keys():
        warn = rebot.modules['warn_module']

    if delete:
        repost = None
        if post_type_id == 1:
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
        elif post_type_id == 2:
            repost = db.Repost(filename_preview=filename,
                               file_preview_hash=p_hash,
                               preview_text=text,
                               url=url,
                               timestamp=timestamp,
                               chat_id=chat_id,
                               original_post_id=original_post_id,
                               post_type_id=post_type_id,
                               similarity_index=sim_index,
                               reposter_id=reposter_id
                               )
        rebot.db_conn.save(repost)

        try:
            text = str(repost.repost_id) + '#R\nREPOST DETECTED FROM ' + \
                   update.message.from_user.mention_markdown() + ' ON ' + \
                   str(repost.timestamp) + ';'

            if sim_index:
                text += ' SIMILARITY INDEX: ' + str(sim_index)

            if url_repost:
                text += ' REASON: URL'

            if original_message_id:
                if not url_repost:
                    text += '\nORIGINAL IMAGE IN REPLY'
                else:
                    text += '\nORIGINAL MESSAGE IN REPLY'
            else:
                text += '\n ORIGINAL MESSAGE NOT SAVED'

            msg = rebot.bot.send_message(chat_id,
                                         text,
                                         reply_to_message_id=original_message_id,
                                         parse_mode=telegram.ParseMode.MARKDOWN,
                                         disable_notification=conf.silent)

            if conf.warn_on_repost and warn and rebot.module_enabled('warn_module', update.message.chat.id):
                warn.issue_warning(reposter_id,
                                   update.message.from_user.name,
                                   update.message.message_id, msg_text, filename,
                                   chat_id, repost_reason,
                                   update.message.chat.type)
            try:
                update.message.delete()
            except telegram.error.BadRequest:
                print('MESSAGE ALREADY DELETED')
                return True

            repost.message_id = msg.message_id
            rebot.db_conn.save(repost)
        except telegram.error.BadRequest:
            rebot.db_conn.post_cleanup(original_message_id, update.message.chat.id)
    else:
        try:
            repost = None
            if post_type_id == 1:
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
            elif post_type_id == 2:
                repost = db.Repost(filename_preview=filename,
                                   file_preview_hash=p_hash,
                                   preview_text=text,
                                   url=url,
                                   timestamp=timestamp,
                                   chat_id=chat_id,
                                   original_post_id=original_post_id,
                                   post_type_id=post_type_id,
                                   similarity_index=sim_index,
                                   reposter_id=reposter_id
                                   )

            rebot.db_conn.save(repost)

            text = str(repost.repost_id) + '#R\nREPOST DETECTED FROM ' + \
                   update.message.from_user.mention_markdown() + ' ON ' + \
                   str(timestamp) + ';'

            if sim_index:
                text += ' SIMILARITY INDEX: ' + str(sim_index)

            if url_repost:
                text += ' REASON: URL'

            try:
                rebot.bot.send_message(update.message.chat.id,
                                       text,
                                       reply_to_message_id=update.message.message_id,
                                       parse_mode=telegram.ParseMode.MARKDOWN,
                                       disable_notification=conf.silent)
            except telegram.error.BadRequest:
                print('REPOST ALREADY DELETED')
                repost.message_id = None
                rebot.db_conn.save(repost)
                return True

            if original_message_id:
                text = 'ORIGINAL IMAGE' if not url_repost else 'ORIGINAL MESSAGE'
            else:
                text = 'ORIGINAL MESSAGE NOT SAVED'
            rebot.bot.send_message(update.message.chat.id,
                                   text,
                                   reply_to_message_id=original_message_id, disable_notification=conf.silent)
            if conf.warn_on_repost and warn and rebot.module_enabled('warn_module', update.message.chat.id):
                warn.issue_warning(reposter_id, update.message.from_user.name,
                                   update.message.message_id, msg_text, filename,
                                   chat_id, repost_reason,
                                   update.message.chat.type)

            rebot.db_conn.save(repost)
        except telegram.error.BadRequest:
            rebot.db_conn.post_cleanup(original_message_id, update.message.chat.id)
    return False


def handle_repost(rebot, update):
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

            results = rebot.db_conn.get_similar_posts(p_hash, update.message.chat.id, conf.hash_threshold)

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

                    reposter = rebot.db_conn.get_reposter(update.message.from_user.id,
                                                          update.message.from_user.name)

                    delete_repost = conf.delete_reposts and update.message.chat.type == 'group'

                    issue_repost(rebot, filename, p_hash, text, datetime.datetime.now(), update.message.chat.id,
                                 result['post_id'], result['message_id'], 1, img_distance, reposter.reposter_id,
                                 update, delete_repost, 'IMAGE REPOST', rebot.get_text(update.message), None)
                    break
            if not is_repost:
                post = db.Post(filename=filename,
                               file_hash=p_hash,
                               text=text,
                               timestamp=datetime.datetime.now(),
                               chat_id=update.message.chat.id,
                               message_id=update.message.message_id,
                               post_type_id=1,
                               poster_id=rebot.db_conn.get_poster(update.message.from_user.id,
                                                                  update.message.from_user.name).poster_id)
                rebot.db_conn.save(post)
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

                    results = rebot.db_conn.get_similar_posts(p_hash, update.message.chat.id, conf.hash_threshold)

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

                            reposter = rebot.db_conn.get_reposter(update.message.from_user.id,
                                                                  update.message.from_user.name)

                            delete_repost = conf.delete_reposts and update.message.chat.type == 'group'
                            issue_repost(rebot, filename, p_hash, text, datetime.datetime.now(), update.message.chat.id,
                                         result['post_id'], result['message_id'], 2, img_distance,
                                         reposter.reposter_id,
                                         update, delete_repost, 'URL IMAGE REPOST', rebot.get_text(update.message), url)
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
                                       poster_id=rebot.db_conn.get_poster(update.message.from_user.id,
                                                                          update.message.from_user.name).poster_id)
                        rebot.db_conn.save(post)
                else:
                    url_same_post = rebot.db_conn.get_same_url_post(url, update.message.chat.id)

                    if url_same_post:
                        reposter = rebot.db_conn.get_reposter(update.message.from_user.id,
                                                              update.message.from_user.name)

                        delete_repost = conf.delete_reposts and update.message.chat.type == 'group'
                        issue_repost(rebot, filename, None, text, datetime.datetime.now(), update.message.chat.id,
                                     url_same_post.post_id, url_same_post.message_id, 2, None,
                                     reposter.reposter_id,
                                     update, delete_repost, 'URL REPOST', rebot.get_text(update.message), url, True)


def handle_import(rebot, update):
    if update.message:
        if not update.message.forward_from:
            return

        print(update)
        poster = rebot.db_conn.get_poster(update.message.forward_from.id,
                                          update.message.forward_from.name)

        timestamp = update.message.forward_date

        if update.message.photo:
            photos = update.message.photo
            photo = max(photos, key=lambda p: p.file_size)
            file = photo.get_file()

            filename = file.file_id + '.jpg'

            if rebot.db_conn.post_exists(filename):
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
            rebot.db_conn.save(post)
            print('IMPORTED ' + filename)


def cmd_post_stats(rebot, args, update):
    try:
        poster = None
        if len(args) >= 1:
            poster = rebot.db_conn.find_user(' '.join(args))

        if poster is None:
            poster = rebot.db_conn.get_poster(update.message.reply_to_message.from_user.id,
                                              update.message.reply_to_message.from_user.name)

        post_count, repost_count = rebot.db_conn.get_post_stats(poster.poster_id, update.message.chat.id)

        rebot.bot.send_message(update.message.chat.id, 'USER [' + poster.name + '] HAS ' + str(post_count) + ' POST' +
                               ('' if post_count == 1 else 'S') + ' AND ' + str(repost_count) + ' REPOST' +
                               ('' if repost_count == 1 else 'S'), disable_notification=conf.silent)

    except AttributeError:
        rebot.bot.send_message(update.message.chat.id,
                               'YOU NEED TO REPLY TO A MESSAGE TO LIST THE USERS STATS OR PASS THE USER AS AN ARGUMENT',
                               disable_notification=conf.silent)


def cmd_get_repost(rebot, args, update):
    if not rebot.check_is_overlord(update.message.from_user.id):
        rebot.bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
                               disable_notification=conf.silent)
        return

    try:
        repost_info = update.message.reply_to_message

        if repost_info.from_user.id != conf.bot_id:
            rebot.bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A REPOST DETECTION',
                                   disable_notification=conf.silent)
            return

        repost_id = int(repost_info.text.split('#R')[0])

        repost = rebot.db_conn.get_repost(repost_id)
        poster = rebot.db_conn.get_poster(repost.reposter_id, None)

        if repost.post_type_id == 1:
            rebot.bot.send_photo(update.message.chat.id, repost.filename.replace('.jpg', ''),
                                 caption='REPOST FROM ' + poster.name + ' AT ' + str(repost.timestamp))
        elif repost.post_type_id == 2:
            rebot.bot.send_message(update.message.chat.id,
                                   repost.url + '\nREPOST FROM ' + poster.name + ' AT ' + str(repost.timestamp),
                                   disable_notification=conf.silent)

    except (AttributeError, ValueError):
        rebot.bot.send_message(update.message.chat.id,
                               'YOU NEED TO REPLY TO A REPOST DETECTION TO GET THE REPOST',
                               disable_notification=conf.silent)


def cmd_random_post(rebot, args, update):
    if not rebot.check_is_overlord(update.message.from_user.id):
        rebot.bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
                               disable_notification=conf.silent)
        return

    post_random(rebot, update.message.chat.id)


def post_random(rebot, chat_id):
    post = rebot.db_conn.get_random_post(chat_id)
    if not post:
        rebot.bot.send_message(chat_id, 'NO POSTS FOUND', conf.silent)
        return
    poster = rebot.db_conn.get_poster(post.poster_id, None)
    if post.post_type_id == 1:
        rebot.bot.send_photo(chat_id, post.filename.replace('.jpg', ''),
                             caption='POST FROM ' + poster.name + ' AT ' + str(post.timestamp))
    elif post.post_type_id == 2:
        rebot.bot.send_message(chat_id,
                               post.url + '\nPOST FROM ' + poster.name + ' AT ' + str(post.timestamp),
                               disable_notification=conf.silent)


def cmd_get_text(rebot, args, update):
    try:
        post_info = update.message.reply_to_message

        post = rebot.db_conn.get_post_per_message(post_info.message_id, update.message.chat.id)
        if post:
            rebot.bot.send_message(update.message.chat.id,
                                   'TEXT:\n' + post.text,
                                   reply_to_message_id=post.message_id, disable_notification=conf.silent)
        else:
            rebot.bot.send_message(update.message.chat.id,
                                   'I DON\'T HAVE THIS POST SAVED', disable_notification=conf.silent)

    except AttributeError:
        rebot.bot.send_message(update.message.chat.id,
                               'YOU NEED TO REPLY TO A POST TO GET ITS TEXT', disable_notification=conf.silent)


def cmd_no_repost(rebot, args, update):
    if not rebot.check_is_overlord(update.message.from_user.id):
        poster = rebot.db_conn.get_poster(update.message.from_user.id, update.message.from_user.name)
        rebot.bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')
        warn = None
        if 'warn_module' in rebot.modules.keys() and rebot.module_enabled('warn_module', update.message.chat.id):
            warn = rebot.modules['warn_module']
        if conf.warn_on_admin and warn:
            warn.issue_warning(rebot, poster.poster_id, update.message.from_user.name, update.message.message_id,
                               update.message.chat.id,
                               rebot.get_text(update.message), None,
                               'UNAUTHORIZED NO-REPOST ATTEMPT',
                               update.message.chat.type)
        return

    try:
        repost_info = update.message.reply_to_message

        if repost_info.from_user.id != conf.bot_id:
            rebot.bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A REPOST DETECTION',
                                   disable_notification=conf.silent)
            return

        repost_id = int(repost_info.text.split('#R')[0])

        repost = rebot.db_conn.get_repost(repost_id)

        rebot.db_conn.forgive_repost(repost)

        poster = rebot.db_conn.get_poster(repost.reposter_id, None)

        if conf.delete_reposts:
            if repost.post_type_id == 1:
                rebot.bot.send_photo(update.message.chat.id, repost.filename.replace('.jpg', ''),
                                     caption='FORGIVEN REPOST FROM ' + poster.name + ' AT ' + str(repost.timestamp))
            elif repost.post_type_id == 2:
                rebot.bot.send_message(update.message.chat.id,
                                       repost.url + '\nFORGIVEN REPOST FROM ' + poster.name + ' AT ' + str(
                                           repost.timestamp),
                                       disable_notification=conf.silent)

            try:
                rebot.bot.delete_message(update.message.chat.id, repost.message_id)
            except telegram.error.BadRequest:
                print('MESSAGE ALREADY DELETED')
        else:
            rebot.bot.send_message(update.message.chat.id,
                                   'REPOST FORGIVEN FROM ' + poster.name + ' AT ' + str(repost.timestamp),
                                   disable_notification=conf.silent,
                                   reply_to_message_id=repost.message_id)

        if repost.filename:
            os.remove('files/' + repost.filename)
        if repost.filename_preview:
            os.remove('files/' + repost.filename_preview)
    except (AttributeError, ValueError):
        rebot.bot.send_message(update.message.chat.id,
                               'YOU NEED TO REPLY TO A REPOST DETECTION TO FORGIVE THE REPOST',
                               disable_notification=conf.silent)
