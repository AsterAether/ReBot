import sqlalchemy as sqa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CHAR, Float, TEXT
from sqlalchemy.orm import sessionmaker
import conf
import os
import datetime

Base = declarative_base()
engine = None
session = None


class PostType(Base):
    __tablename__ = 'post_type'

    post_type_id = Column(Integer, primary_key=True)
    description = Column(String(length=10))


class Warning(Base):
    __tablename__ = 'warning'

    warning_id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer)
    chat_id = Column(Integer)
    timestamp = Column(DateTime)
    poster_id = Column(Integer, ForeignKey('poster.poster_id'))
    reason = Column(String(255))


class Poster(Base):
    __tablename__ = 'poster'

    poster_id = Column(Integer, primary_key=True)
    name = Column(String(length=100))


class Reposter(Base):
    __tablename__ = 'reposter'

    reposter_id = Column(Integer, ForeignKey('poster.poster_id'), primary_key=True)


class Post(Base):
    __tablename__ = 'post'

    post_id = Column(Integer, primary_key=True, autoincrement=True)
    post_type_id = Column(Integer, ForeignKey('post_type.post_type_id'))
    filename = Column(String(length=100))
    file_hash = Column(CHAR(16))
    text = Column(TEXT)
    url = Column(String(length=255))
    filename_preview = Column(String(length=100))
    file_preview_hash = Column(CHAR(16))
    preview_text = Column(TEXT)
    timestamp = Column(DateTime)
    chat_id = Column(Integer)
    message_id = Column(Integer)
    poster_id = Column(Integer, ForeignKey('poster.poster_id'))


class Repost(Base):
    __tablename__ = 'repost'

    repost_id = Column(Integer, primary_key=True, autoincrement=True)
    post_type_id = Column(Integer, ForeignKey('post_type.post_type_id'))
    original_post_id = Column(Integer, ForeignKey('post.post_id'))
    filename = Column(String(length=100))
    file_hash = Column(CHAR(16))
    text = Column(TEXT)
    url = Column(String(length=255))
    filename_preview = Column(String(length=100))
    file_preview_hash = Column(CHAR(16))
    preview_text = Column(TEXT)
    timestamp = Column(DateTime)
    chat_id = Column(Integer)
    message_id = Column(Integer)
    similarity_index = Column(Float)
    reposter_id = Column(Integer, ForeignKey('reposter.reposter_id'))


def create_ddl():
    global engine
    global session

    start_engine()

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    start_session()

    post_types = [PostType(post_type_id=1, description='Image Post'),
                  PostType(post_type_id=2, description='URL Post')]

    session.add_all(post_types)
    session.commit()

    with open('module.sql') as f:
        session.execute(''.join(f.readlines()))

    session.commit()

    stop_session()
    stop_engine()


def get_random_post(chat_id):
    global session
    result = session.execute('SELECT * FROM post WHERE chat_id= ' + str(chat_id) + ' ORDER BY RAND()').fetchall()
    if len(result) == 0:
        return None
    else:
        return result[0]


def start_engine():
    global engine
    engine = sqa.create_engine(
        conf.db_driver + '://' + conf.db_user + ':' + conf.db_password + '@' + conf.db_host + '/' + conf.db_name,
        echo=True,
        encoding='utf-8')
    engine.connect()


def start_session():
    global session
    Session = sessionmaker(bind=engine)
    session = Session()


def save(obj):
    global session
    session.add(obj)
    session.commit()


def get_poster(poster_id, name):
    poster = session.query(Poster).filter(Poster.poster_id == poster_id).first()
    if not poster:
        poster = Poster(poster_id=poster_id, name=name)
        session.add(poster)
        session.commit()
    return poster


def get_reposter(reposter_id, name):
    reposter = session.query(Reposter).filter(Reposter.reposter_id == reposter_id).first()
    if not reposter:
        poster = get_poster(reposter_id, name)
        reposter = Reposter(reposter_id=poster.poster_id)
        session.add(reposter)
        session.commit()
    return reposter


def get_same_url_post(url, chat_id):
    global session
    post = session.query(Post).filter(Post.url == url).filter(Post.chat_id == chat_id).first()
    return post


def get_similar_posts(hash, chat_id):
    global session
    session.execute(
        'CALL get_post_per_distance(\"' + hash + '\", ' + str(chat_id) + ',' + str(conf.hash_threshold) + ')')
    results = session.execute(
        'SELECT post_id, filename,filename_preview, message_id, text, preview_text, distance, distance_preview FROM tmp_post_per_distance')
    results = results.fetchall()
    return results


def get_warning_count(poster_id, chat_id):
    global session
    return session.query(Warning).filter(Warning.poster_id == poster_id).filter(Warning.chat_id == chat_id).count()


def get_warnings(poster_id, chat_id):
    global session
    return session.query(Warning).filter(Warning.poster_id == poster_id).filter(Warning.chat_id == chat_id).order_by(
        Warning.timestamp).all()


def get_post_stats(poster_id, chat_id):
    global session
    post_count = session.query(Post).filter(Post.poster_id == poster_id).filter(Post.chat_id == chat_id).count()
    repost_count = session.query(Repost).filter(Repost.reposter_id == poster_id).filter(
        Repost.chat_id == chat_id).count()
    return post_count, repost_count


def post_cleanup(message_id, chat_id):
    global session
    post = session.query(Post).filter(Post.message_id == message_id).filter(Post.chat_id == chat_id).first()
    reposts = session.query(Repost).filter(Repost.original_post_id == post.post_id).all()

    session.query(Repost).filter(Repost.original_post_id == post.post_id).delete()
    session.query(Post).filter(Post.post_id == post.post_id).delete()

    try:
        if post.filename:
            os.remove('files/' + post.filename)
        if post.filename_preview:
            os.remove('files/' + post.filename_preview)
    except FileNotFoundError:
        pass

    for repost in reposts:
        try:
            if repost.filename:
                os.remove('files/' + repost.filename)
            if repost.filename_preview:
                os.remove('files/' + repost.filename_preview)
        except FileNotFoundError:
            pass


def forgive_repost(repost):
    global session
    session.query(Repost).filter(Repost.repost_id == repost.repost_id).delete()
    # session.query(Warning).filter(Warning.message_id == repost.message_id).filter(
    #     Warning.chat_id == repost.chat_id).delete()


def forgive_warning(warning):
    global session
    session.query(Warning).filter(Warning.warning_id == warning.warning_id).delete()


def get_repost(repost_id):
    global session
    return session.query(Repost).filter(Repost.repost_id == repost_id).first()


def get_warning(warning_id):
    global session
    return session.query(Warning).filter(Warning.warning_id == warning_id).first()


def get_post_per_message(message_id, chat_id):
    global session
    return session.query(Post).filter(Post.message_id == message_id).filter(Post.chat_id == chat_id).first()


def find_user(name):
    global session
    return session.query(Poster).filter(Poster.name == name).first()


def db_cleanup():
    global engine
    global session

    start_engine()
    start_session()

    posts = session.query(Post).all()
    reposts = session.query(Repost).all()

    filenames = []
    for post in posts:
        if post.filename:
            filenames.append(post.filename)
        if post.filename_preview:
            filenames.append(post.filename_preview)

    for repost in reposts:
        if repost.filename:
            filenames.append(repost.filename)
        if repost.filename_preview:
            filenames.append(repost.filename_preview)

    for the_file in os.listdir('files/'):
        file_path = os.path.join('files/', the_file)
        try:
            if os.path.isfile(file_path) and the_file not in filenames:
                os.remove(file_path)
        except Exception as e:
            print(e)

    stop_session()
    stop_engine()


def stop_session():
    global session
    session.close_all()


def stop_engine():
    global engine
    engine.dispose()


if __name__ == '__main__':
    create_ddl()
