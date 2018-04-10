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


def handle_repost(update):
    if update.message:
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
                        and similar_text(text, r_text)) >= conf.text_threshold:
                    bot.send_message(update.message.chat.id,
                                     'REPOST DETECTED; SIMILARITY INDEX: ' + str(img_distance),
                                     reply_to_message_id=update.message.message_id)
                    bot.send_message(update.message.chat.id,
                                     'ORIGINAL IMAGE',
                                     reply_to_message_id=result['message_id'])
                    is_repost = True
                    repost = db.Repost(filename=filename,
                                       file_hash=p_hash,
                                       text=text,
                                       timestamp=datetime.datetime.now(),
                                       chat_id=update.message.chat.id,
                                       message_id=update.message.message_id,
                                       original_post_id=result['post_id'],
                                       post_type_id=1,
                                       similarity_index=img_distance,
                                       reposter_id=db.get_reposter(update.message.from_user.id,
                                                                   update.message.from_user.name).reposter_id
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
                                and similar_text(text, r_text)) >= conf.text_threshold:
                            bot.send_message(update.message.chat.id,
                                             'REPOST DETECTED; SIMILARITY INDEX: ' + str(img_distance),
                                             reply_to_message_id=update.message.message_id)
                            bot.send_message(update.message.chat.id,
                                             'ORIGINAL IMAGE',
                                             reply_to_message_id=result['message_id'])
                            is_repost = True
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
                                               reposter_id=db.get_reposter(update.message.from_user.id,
                                                                           update.message.from_user.name).reposter_id)
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
                        bot.send_message(update.message.chat.id,
                                         'REPOST DETECTED; REASON: URL',
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
                                           reposter_id=db.get_reposter(update.message.from_user.id,
                                                                       update.message.from_user.name).reposter_id)
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
    bot.send_message(update.message.chat.id, 'HELLO')


def cmd_warn(args, update):

    if update.message.from_user.name not in conf.bot_overlords:
        bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS')
        return

    poster = db.get_poster(update.message.reply_to_message.from_user.id,
                           update.message.reply_to_message.from_user.name)

    warning = db.Warning(message_id=update.message.message_id,
                         chat_id=update.message.chat.id,
                         timestamp=datetime.datetime.now(),
                         poster_id=poster.poster_id)

    db.save(warning)

    count = db.get_warning_count(poster.poster_id, update.message.chat.id)

    bot.send_message(update.message.chat.id,
                     'YOU [' + update.message.reply_to_message.from_user.mention_markdown() +
                     '] ARE WARNED; WARNING NUMBER ' + str(count),
                     parse_mode=telegram.ParseMode.MARKDOWN)


def cmd_my_warnings(args, update):
    poster = db.get_poster(update.message.from_user.id,
                           update.message.from_user.name)

    count = db.get_warning_count(poster.poster_id, update.message.chat.id)
    bot.send_message(update.message.chat.id,
                     'YOU [' + update.message.from_user.mention_markdown() +
                     '] HAVE ' + str(count) + ' WARNING' + '' if count == 1 else 'S',
                     parse_mode=telegram.ParseMode.MARKDOWN)


def handle_commands(update):
    if update.message.text and update.message.text.startswith('/'):
        command = update.message.text[1:]
        print('COMMAND RECEIVED: ' + command)
        cmd_split = command.split(' ')
        cmd = cmd_split[0]
        args = cmd_split[1:]

        try:
            {
                'start': cmd_start,
                'warn': cmd_warn,
                'mywarnings': cmd_my_warnings
            }[cmd](args, update)
        except KeyError:
            bot.send_message(update.message.chat.id, 'I DON\'T RECOGNIZE THIS COMMAND: ' + cmd)


while True:
    try:
        updates = bot.get_updates(offset=offset)
        for update in updates:
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
