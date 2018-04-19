import sqlalchemy as sqa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, CHAR, Float, TEXT, and_
from sqlalchemy.orm import sessionmaker, relationship
import os

Base = declarative_base()


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
    photo_filename = Column(String(length=100))
    text = Column(TEXT)


class Props(Base):
    __tablename__ = 'props'

    props_id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer)
    chat_id = Column(Integer)
    timestamp = Column(DateTime)
    poster_id = Column(Integer, ForeignKey('poster.poster_id'))
    reason = Column(String(255))
    photo_filename = Column(String(length=100))
    text = Column(TEXT)


class Poster(Base):
    __tablename__ = 'poster'

    poster_id = Column(Integer, primary_key=True)
    name = Column(String(length=100))
    shops = relationship('Shop', backref='owner_ref')


class Reposter(Base):
    __tablename__ = 'reposter'

    reposter_id = Column(Integer, ForeignKey('poster.poster_id'), primary_key=True)


class Ban(Base):
    __tablename__ = 'ban'

    chat_id = Column(Integer, primary_key=True)
    poster_id = Column(Integer, ForeignKey('poster.poster_id'), primary_key=True)
    timestamp = Column(DateTime)


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


class Shop(Base):
    __tablename__ = 'shop'

    shop_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))
    owner = Column(Integer, ForeignKey('poster.poster_id'))
    description = Column(String(255))
    products = relationship('Product', backref='shop')


class Product(Base):
    __tablename__ = 'product'

    product_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100))
    price = Column(Float)
    comment = Column(String(255))
    shop_id = Column(Integer, ForeignKey('shop.shop_id'))


class Order(Base):
    __tablename__ = 'order'

    order_id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp_ordered = Column(DateTime)
    timestamp_done = Column(DateTime)
    timestamp_approved = Column(DateTime)
    comment = Column(String(255))
    product_id = Column(Integer, ForeignKey('product.product_id'))
    customer = Column(Integer, ForeignKey('poster.poster_id'))
    amount = Column(Integer)


class User(Base):
    __tablename__ = 'user'

    username = Column(String(50), primary_key=True)
    password = Column(String(255), nullable=False)
    poster_id = Column(Integer, ForeignKey('poster.poster_id'), unique=True)


def dump_datetime(value):
    """Deserialize datetime object into string form for JSON processing."""
    if value is None:
        return None
    return [value.strftime("%Y-%m-%d"), value.strftime("%H:%M:%S")]


class Database:

    def __init__(self, driver, db_user, db_pass, db_host, db_name):
        self.db_driver = driver
        self.db_user = db_user
        self.db_pass = db_pass
        self.db_host = db_host
        self.db_name = db_name
        self.engine = None
        self.session = None

    def create_ddl(self):

        self.start_engine()

        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)

        self.start_session()

        post_types = [PostType(post_type_id=1, description='Image Post'),
                      PostType(post_type_id=2, description='URL Post')]

        self.session.add_all(post_types)
        self.session.commit()

        with open('module.sql') as f:
            self.session.execute(''.join(f.readlines()))

            self.session.commit()

        self.stop_session()
        self.stop_engine()

    def get_user_by_poster(self, poster_id):
        return self.session.query(User).filter(User.poster_id == poster_id).first()

    def get_user(self, username):
        return self.session.query(User).filter(User.username == username).first()

    def get_random_post(self, chat_id):
        result = self.session.execute(
            'SELECT * FROM post WHERE chat_id= ' + str(chat_id) + ' ORDER BY RAND()').fetchall()
        if len(result) == 0:
            return None
        else:
            return result[0]

    def get_lowest_poster(self):
        return self.session.query(Poster).order_by(Poster.poster_id).first()

    def start_engine(self):
        self.engine = sqa.create_engine(
            self.db_driver + '://' + self.db_user + ':' + self.db_pass + '@' + self.db_host + '/' + self.db_name,
            echo=True,
            encoding='utf-8')
        self.engine.connect()

    def start_session(self):
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

    def save(self, obj):

        self.session.add(obj)
        self.session.commit()

    def get_poster(self, poster_id, name):
        poster = self.session.query(Poster).filter(Poster.poster_id == poster_id).first()
        if not poster:
            poster = Poster(poster_id=poster_id, name=name)
            self.session.add(poster)
            self.session.commit()
        return poster

    def update_poster(self, poster_id, name):
        poster = self.session.query(Poster).filter(Poster.poster_id == poster_id).first()
        if not poster:
            poster = Poster(poster_id=poster_id, name=name)
            self.session.add(poster)
            self.session.commit()
            return
        poster.name = name
        self.session.add(poster)
        self.session.commit()
        return

    def get_reposter(self, reposter_id, name):
        reposter = self.session.query(Reposter).filter(Reposter.reposter_id == reposter_id).first()
        if not reposter:
            poster = self.get_poster(reposter_id, name)
            reposter = Reposter(reposter_id=poster.poster_id)
            self.session.add(reposter)
            self.session.commit()
        return reposter

    def get_same_url_post(self, url, chat_id):
        post = self.session.query(Post).filter(Post.url == url).filter(Post.chat_id == chat_id).first()
        return post

    def get_similar_posts(self, hash, chat_id, hash_threshold):
        self.session.execute(
            'CALL get_post_per_distance(\"' + hash + '\", ' + str(chat_id) + ',' + str(hash_threshold) + ')')
        results = self.session.execute(
            'SELECT post_id, filename,filename_preview, message_id, text, preview_text, distance, distance_preview FROM tmp_post_per_distance')
        results = results.fetchall()
        return results

    def post_exists(self, filename):
        post = self.session.query(Post).filter(
            (Post.filename == filename) | (Post.filename_preview == filename)).first()
        return post is not None

    def get_warning_count(self, poster_id, chat_id):
        return self.session.query(Warning).filter(Warning.poster_id == poster_id).filter(
            Warning.chat_id == chat_id).count()

    def get_props_count(self, poster_id, chat_id):
        return self.session.query(Props).filter(Props.poster_id == poster_id).filter(Props.chat_id == chat_id).count()

    def get_warnings(self, poster_id, chat_id):
        return self.session.query(Warning).filter(Warning.poster_id == poster_id).filter(
            Warning.chat_id == chat_id).order_by(
            Warning.timestamp).all()

    def get_props(self, poster_id, chat_id):
        return self.session.query(Props).filter(Props.poster_id == poster_id).filter(Props.chat_id == chat_id).order_by(
            Props.timestamp).all()

    def get_post_stats(self, poster_id, chat_id):
        post_count = self.session.query(Post).filter(Post.poster_id == poster_id).filter(
            Post.chat_id == chat_id).count()
        repost_count = self.session.query(Repost).filter(Repost.reposter_id == poster_id).filter(
            Repost.chat_id == chat_id).count()
        return post_count, repost_count

    def post_cleanup(self, message_id, chat_id):
        post = self.session.query(Post).filter(Post.message_id == message_id).filter(Post.chat_id == chat_id).first()
        reposts = self.session.query(Repost).filter(Repost.original_post_id == post.post_id).all()

        self.session.query(Repost).filter(Repost.original_post_id == post.post_id).delete()
        self.session.query(Post).filter(Post.post_id == post.post_id).delete()
        self.session.commit()

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

    def get_shops(self):
        return self.session.query(Shop).all()

    def get_owner(self, product_id):
        product = self.session.query(Product).filter(Product.product_id == product_id).first()
        shop = self.session.query(Shop).filter(Shop.shop_id == product.shop_id).first()
        return shop.owner, product, shop

    def get_order(self, order_id):
        return self.session.query(Order).filter(Order.order_id == order_id).first()

    def get_product(self, prod_id):
        return self.session.query(Product).filter(Product.product_id == prod_id).first()

    def get_shop(self, shop_id):
        return self.session.query(Shop).filter(Shop.shop_id == shop_id).first()

    def del_order(self, order_id):
        self.session.query(Order).filter(Order.order_id == order_id).delete()
        self.session.commit()

    def get_open_orders(self, poster_id):
        return self.session.execute(
            'SELECT order_id, customer, o.comment as comment, p.name as name,p.product_id as product_id, amount,timestamp_ordered,timestamp_done,timestamp_approved FROM shop INNER JOIN product p on shop.shop_id = p.shop_id INNER JOIN `order` o ON p.product_id = o.product_id WHERE owner = ' + str(
                poster_id) + ' AND o.timestamp_done IS NULL AND o.timestamp_approved IS NOT NULL').fetchall()

    def get_unapproved_orders(self, poster_id):
        return self.session.execute(
            'SELECT order_id, customer, o.comment as comment, p.name as name,p.product_id as product_id, amount,timestamp_ordered,timestamp_done,timestamp_approved FROM shop INNER JOIN product p on shop.shop_id = p.shop_id INNER JOIN `order` o ON p.product_id = o.product_id WHERE owner = ' + str(
                poster_id) + ' AND o.timestamp_done IS NULL AND o.timestamp_approved IS NULL').fetchall()

    def get_orders(self, customer):
        return self.session.query(Order).filter(
            and_((Order.customer == customer), (Order.timestamp_done == None))).all()

    def get_products(self, shop_id):
        return self.session.query(Product).filter(Product.shop_id == shop_id).all()

    def delete_product(self, prod):
        self.session.query(Order).filter(Order.product_id == prod.product_id).delete()

        self.session.delete(prod)
        self.session.commit()

    def forgive_repost(self, repost):
        self.session.query(Repost).filter(Repost.repost_id == repost.repost_id).delete()
        # session.query(Warning).filter(Warning.message_id == repost.message_id).filter(
        #     Warning.chat_id == repost.chat_id).delete()
        self.session.commit()

    def forgive_warning(self, warning):
        self.session.query(Warning).filter(Warning.warning_id == warning.warning_id).delete()
        self.session.commit()

    def forgive_warnings_for_poster(self, poster_id):
        self.session.query(Warning).filter(Warning.poster_id == poster_id).delete()
        self.session.commit()

    def get_repost(self, repost_id):
        return self.session.query(Repost).filter(Repost.repost_id == repost_id).first()

    def get_warning(self, warning_id):
        return self.session.query(Warning).filter(Warning.warning_id == warning_id).first()

    def get_prop(self, props_id):
        return self.session.query(Props).filter(Props.props_id == props_id).first()

    def withdraw(self, props_id):
        self.session.query(Props).filter(Props.props_id == props_id).delete()

    def get_post(self, post_id):
        return self.session.query(Post).filter(Post.post_id == post_id).first()

    def get_post_per_message(self, message_id, chat_id):
        return self.session.query(Post).filter(Post.message_id == message_id).filter(Post.chat_id == chat_id).first()

    def find_user(self, name):
        return self.session.query(Poster).filter(Poster.name == name).first()

    def db_cleanup(self):
        self.start_engine()
        self.start_session()

        posts = self.session.query(Post).all()
        reposts = self.session.query(Repost).all()

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

        self.stop_session()
        self.stop_engine()

    def stop_session(self):
        self.session.close_all()

    def stop_engine(self):
        self.engine.dispose()


if __name__ == '__main__':
    import conf

    db = Database(driver=conf.db_driver, db_user=conf.db_user, db_pass=conf.db_password,
                  db_host=conf.db_host, db_name=conf.db_name)

    db.create_ddl()
