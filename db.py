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
    filename = Column(String(length=100))
    file_hash = Column(String(length=255))
    url = Column(String(length=255))
    filename_preview = Column(String(length=100))
    file_preview_hash = Column(String(length=255))
    timestamp = Column(DateTime)
    chat_id = Column(Integer)
    message_id = Column(Integer)


class Repost(Base):
    __tablename__ = 'repost'

    repost_id = Column(Integer, primary_key=True, autoincrement=True)
    original_post_id = Column(Integer)
    filename = Column(String(length=100))
    file_hash = Column(String(length=255))
    url = Column(String(length=255))
    filename_preview = Column(String(length=100))
    file_preview_hash = Column(String(length=255))
    timestamp = Column(DateTime)
    chat_id = Column(Integer)
    message_id = Column(Integer)


def create_ddl():
    global engine
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def start_engine():
    global engine
    engine = sqa.create_engine(
        conf.db_driver + '://' + conf.db_user + ':' + conf.db_password + '@' + conf.db_host + '/' + conf.db_name,
        echo=True)
    engine.connect()


def start_session():
    global session
    Session = sessionmaker(bind=engine)
    session = Session()


def stop_session():
    global session
    session.close_all()


def stop_engine():
    global engine
    engine.dispose()
