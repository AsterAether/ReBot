import db
import telegram
import conf
import time
import os
import re
import urlmarker
import img
import datetime
from difflib import SequenceMatcher

re_urls = re.compile(urlmarker.URL_REGEX)


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


dirs = ['files', 'tmp']
for dir in dirs:
    if not os.path.exists(dir):
        os.mkdir(dir)

db.start_engine()
db.start_session()

bot = telegram.Bot(token=conf.token)

offset = 0
clear_count = 0


def issue_warning(poster_id, message_id, chat_id, reason):
    warning = db.Warning(message_id=message_id,
                         chat_id=chat_id,
                         timestamp=datetime.datetime.now(),
                         poster_id=poster_id,
                         reason=reason)

    db.save(warning)

    return db.get_warning_count(poster_id, chat_id)


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
                    count = issue_warning(reposter.reposter_id, update.message.message_id,
                                          update.message.chat.id, 'IMAGE REPOST')

                    bot.send_message(update.message.chat.id,
                                     'REPOST DETECTED; SIMILARITY INDEX: ' + str(
                                         img_distance) + '\nWARNING NUMBER ' + str(count) + ' ISSUED',
                                     reply_to_message_id=update.message.message_id)
                    bot.send_message(update.message.chat.id,
                                     'ORIGINAL IMAGE',
                                     reply_to_message_id=result['message_id'])

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
            text = update.message.text
            urls = re_urls.findall(text)
            if len(urls) > 0:
                url = urls[0]
                filename = str(update.message.chat.id) + '_' + str(update.message.message_id)

                filename = img.handle_url_image(url, filename)
                if filename:

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
                            count = issue_warning(reposter.reposter_id, update.message.message_id,
                                                  update.message.chat.id, 'URL IMAGE REPOST')

                            bot.send_message(update.message.chat.id,
                                             'REPOST DETECTED; SIMILARITY INDEX: ' + str(
                                                 img_distance) + '\nWARNING NUMBER ' + str(count) + ' ISSUED',
                                             reply_to_message_id=update.message.message_id)
                            bot.send_message(update.message.chat.id,
                                             'ORIGINAL IMAGE',
                                             reply_to_message_id=result['message_id'])

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
                        count = issue_warning(reposter.reposter_id, update.message.message_id,
                                              update.message.chat.id, 'URL REPOST')

                        bot.send_message(update.message.chat.id,
                                         'REPOST DETECTED; REASON: URL' + '\nWARNING NUMBER ' + str(count) + ' ISSUED',
                                         reply_to_message_id=update.message.message_id)
                        bot.send_message(update.message.chat.id,
                                         'ORIGINAL POST',
                                         reply_to_message_id=url_same_post.message_id)
                        repost = db.Repost(url=url,
                                           timestamp=datetime.datetime.now(),
                                           chat_id=update.message.chat.id,
                                           message_id=update.message.message_id,
                                           original_post_id=url_same_post.post_id,
                                           post_type_id=2,
                                           similarity_index=1,
                                           reposter_id=reposter.reposter_id)
                        db.save(repost)
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


def cmd_start(args, update):
    bot.send_message(update.message.chat.id, 'HELLO; IF YOU NEED HELP CALL /help')


def cmd_warn(args, update):
    if update.message.from_user.name not in conf.bot_overlords:
        bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')
        return

    try:
        reason = 'MANUAL WARNING'
        if len(args) >= 1:
            reason = args[0]
        poster = db.get_poster(update.message.reply_to_message.from_user.id,
                               update.message.reply_to_message.from_user.name)

        if poster.poster_id == conf.bot_id:
            bot.send_message(update.message.chat.id, 'PLEASE DON\'T TRY TO WARN ME')
            return

        count = issue_warning(poster.poster_id, update.message.reply_to_message.message_id, update.message.chat.id,
                              reason)

        bot.send_message(update.message.chat.id,
                         'YOU [' + update.message.reply_to_message.from_user.mention_markdown() +
                         '] ARE WARNED; WARNING NUMBER ' + str(count),
                         parse_mode=telegram.ParseMode.MARKDOWN)
    except AttributeError:
        bot.send_message(update.message.chat.id, 'YOU NEED TO REPLY TO A MESSAGE TO WARN IT')


def cmd_my_warnings(args, update):
    poster = db.get_poster(update.message.from_user.id,
                           update.message.from_user.name)

    count = db.get_warning_count(poster.poster_id, update.message.chat.id)
    bot.send_message(update.message.chat.id,
                     'YOU [' + update.message.from_user.mention_markdown() +
                     '] HAVE ' + str(count) + ' WARNING' + ('' if count == 1 else 'S'),
                     parse_mode=telegram.ParseMode.MARKDOWN)


def cmd_list_warnings(args, update):

    try:
        poster = None
        if len(args) >= 1:
            poster = db.find_user(' '.join(args))

        if not poster:
            poster = db.get_poster(update.message.reply_to_message.from_user.id,
                                   update.message.reply_to_message.from_user.name)

        if poster.poster_id != update.message.from_user.id and update.message.from_user.name not in conf.bot_overlords:
            bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')
            return

        i = 1
        for warning in db.get_warnings(poster.poster_id, update.message.chat.id):
            bot.send_message(update.message.chat.id,
                             'WARNING ' + str(
                                 i) + ' OF ' + update.message.reply_to_message.from_user.mention_markdown() + '\nREASON: ' + warning.reason,
                             parse_mode=telegram.ParseMode.MARKDOWN,
                             reply_to_message_id=warning.message_id)
            i += 1

    except AttributeError:
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A MESSAGE TO LIST THE USERS WARNINGS OR PASS THE USER AS AN ARGUMENT')


def cmd_post_stats(args, update):
    try:
        poster = None
        if len(args) >= 1:
            poster = db.find_user(' '.join(args))

        if not poster:
            poster = db.get_poster(update.message.reply_to_message.from_user.id,
                                   update.message.reply_to_message.from_user.name)

        post_count, repost_count = db.get_post_stats(poster.poster_id, update.message.chat.id)

        bot.send_message(update.message.chat.id, 'USER [' + poster.name + '] HAS ' + str(post_count) + ' POST' +
                         ('' if post_count == 1 else 'S') + ' AND ' + str(repost_count) + ' REPOST' +
                         ('' if repost_count == 1 else 'S'))

    except AttributeError:
        bot.send_message(update.message.chat.id,
                         'YOU NEED TO REPLY TO A MESSAGE TO LIST THE USERS STATS OR PASS THE USER AS AN ARGUMENT')


def handle_commands(update):
    if update.message and update.message.text and update.message.text.startswith('/'):
        command = update.message.text[1:]
        command = command.replace(conf.bot_name, '')
        print('COMMAND RECEIVED: ' + command)
        cmd_split = command.split(' ')
        cmd = cmd_split[0]
        args = cmd_split[1:]

        commands = {'start': cmd_start,
                    'warn': cmd_warn,
                    'mywarnings': cmd_my_warnings,
                    'listwarnings': cmd_list_warnings,
                    'poststats': cmd_post_stats,
                    'help': lambda args, update: bot.send_message(update.message.chat.id,
                                                                  'COMMANDS: ' + ', '.join(
                                                                      ['/' + c for c in commands.keys()]))}

        try:
            commands[cmd](args, update)
        except KeyError:
            bot.send_message(update.message.chat.id, 'I DON\'T RECOGNIZE THIS COMMAND: ' + cmd)


while True:
    try:
        updates = bot.get_updates(offset=offset)
        for update in updates:
            print(update)
            if update.message:
                print(update.message.parse_entities())
            handle_repost(update)
            handle_commands(update)
        if len(updates) > 0:
            offset = updates[-1].update_id + 1
    except telegram.error.TimedOut:
        print('No updates.')
    clear_count += 1
    if clear_count == conf.clear_every:
        tmp_clear()
        clear_count = 0

    time.sleep(conf.timeout)
