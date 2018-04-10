import db
import telegram
import conf
import time
import os
import re
import urlmarker

re_urls = re.compile(urlmarker.URL_REGEX)

if not os.path.exists('files'):
    os.mkdir('files')

db.start_engine()
db.start_session()
db.create_ddl()

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

                    if os.path.isfile('files/' + file.file_id + '.jpg'):
                        bot.send_message(update.message.chat.id, 'This seems to be the same image I got recently...',
                                         reply_to_message_id=update.message.message_id)

                    file.download(custom_path='files/' + file.file_id + '.jpg')
                if update.message.text:
                    text = update.message.text
                    urls = re_urls.findall(text)
                    f = open('files/urls', 'a')
                    for url in urls:
                        f.write(url + '\n')
                    f.flush()
                    f.close()
                    print(urls)
        if len(updates) > 0:
            offset = updates[-1].update_id + 1
    except telegram.error.TimedOut:
        print('No updates.')

    time.sleep(conf.timeout)
