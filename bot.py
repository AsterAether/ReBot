import db
import telegram
import conf
import time
import os
import re
import urlmarker
import img
import datetime

re_urls = re.compile(urlmarker.URL_REGEX)

dirs = ['files', 'tmp']
for dir in dirs:
    if not os.path.exists(dir):
        os.mkdir(dir)

db.start_engine()
db.start_session()

bot = telegram.Bot(token=conf.token)

offset = 0

while True:
    try:
        updates = bot.get_updates(offset=offset)
        for update in updates:
            if update.message:
                if update.message.photo:
                    photos = update.message.photo
                    photo = max(photos, key=lambda p: p.file_size)
                    print(photo.file_id)
                    file = photo.get_file()

                    # if os.path.isfile('files/' + file.file_id + '.jpg'):
                    #     bot.send_message(update.message.chat.id, 'This seems to be the same image I got recently...',
                    #                      reply_to_message_id=update.message.message_id)
                    filename = file.file_id + '.jpg'
                    file.download(custom_path='files/' + filename)
                    post = db.Post(filename=filename,
                                   file_hash=img.image_perception_hash(filename),
                                   text=img.image_to_string(filename),
                                   timestamp=datetime.datetime.now(),
                                   chat_id=update.message.chat.id,
                                   message_id=update.message.message_id,
                                   post_type_id=1)
                    db.save(post)
                if update.message.text:
                    text = update.message.text
                    urls = re_urls.findall(text)
                    if len(urls) > 0:
                        url = urls[0]
                        filename = str(update.message.chat.id) + '_' + str(update.message.message_id)

                        filename = img.handle_url_image(url, filename)

                        post = db.Post(filename_preview=filename,
                                       file_preview_hash=img.image_perception_hash(filename) if filename else None,
                                       preview_text=img.image_to_string(filename) if filename else None,
                                       timestamp=datetime.datetime.now(),
                                       chat_id=update.message.chat.id,
                                       message_id=update.message.message_id,
                                       post_type_id=2)
                        db.save(post)
        if len(updates) > 0:
            offset = updates[-1].update_id + 1
    except telegram.error.TimedOut:
        print('No updates.')

    time.sleep(conf.timeout)
