import sqlalchemy as sqa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
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


class Poster(Base):
    __tablename__ = 'poster'

    poster_id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer)
    name = Column(String(length=100))


class Reposter(Base):
    __tablename__ = 'reposter'

    reposter_id = Column(Integer, primary_key=True)


class Post(Base):
    __tablename__ = 'post'

    post_id = Column(Integer, primary_key=True, autoincrement=True)
    post_type_id = Column(Integer)
    filename = Column(String(length=100))
    file_hash = Column(String(length=255))
    text = Column(String(length=255))
    url = Column(String(length=255))
    filename_preview = Column(String(length=100))
    file_preview_hash = Column(String(length=255))
    preview_text = Column(String(length=255))
    timestamp = Column(DateTime)
    chat_id = Column(Integer)
    message_id = Column(Integer)


class Repost(Base):
    __tablename__ = 'repost'

    repost_id = Column(Integer, primary_key=True, autoincrement=True)
    post_type_id = Column(Integer)
    original_post_id = Column(Integer)
    filename = Column(String(length=100))
    file_hash = Column(String(length=255))
    text = Column(String(length=255))
    url = Column(String(length=255))
    filename_preview = Column(String(length=100))
    file_preview_hash = Column(String(length=255))
    preview_text = Column(String(length=255))
    timestamp = Column(DateTime)
    chat_id = Column(Integer)
    message_id = Column(Integer)


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


def stop_session():
    global session
    session.close_all()


def stop_engine():
    global engine
    engine.dispose()


if __name__ == '__main__':
    create_ddl()
