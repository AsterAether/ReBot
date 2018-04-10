import sqlalchemy as sqa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CHAR, Float
from sqlalchemy.orm import sessionmaker
import conf

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
    text = Column(String(length=255))
    url = Column(String(length=255))
    filename_preview = Column(String(length=100))
    file_preview_hash = Column(CHAR(16))
    preview_text = Column(String(length=255))
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
    text = Column(String(length=255))
    url = Column(String(length=255))
    filename_preview = Column(String(length=100))
    file_preview_hash = Column(CHAR(16))
    preview_text = Column(String(length=255))
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


def stop_session():
    global session
    session.close_all()


def stop_engine():
    global engine
    engine.dispose()


if __name__ == '__main__':
    create_ddl()
