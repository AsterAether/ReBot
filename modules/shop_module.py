import datetime
import bcrypt
from flask import jsonify, request
from eve import Eve
from eve.auth import BasicAuth, requires_auth
from eve_sqlalchemy import SQL
from eve_sqlalchemy.validation import ValidatorSQL
from sqlalchemy.exc import IntegrityError

import modules.shop_conf as mod_conf
import conf
import telegram
import threading
import db

db_conn = None
app = None
rebot_instance = None


class BCryptAuth(BasicAuth):
    def check_auth(self, username, password, allowed_roles, resource, method):
        user = db_conn.get_user(username)
        print('AUTH REQUEST WITH: ' + username + '+' + password)
        if user and user.poster_id:
            self.set_request_auth_value(str(user.poster_id) + '#' + user.username)
        return user and bcrypt.hashpw(password.encode('utf8'), user.password.encode('utf8')).decode(
            'utf8') == user.password


def register(rebot):
    commands = rebot.get_module_commands('shop_module')
    commands['listshops'] = cmd_list_shops
    commands['order'] = cmd_order
    commands['listopen'] = cmd_list_orders
    commands['myorders'] = cmd_list_my_orders
    commands['listunapproved'] = cmd_list_orders_unapproved
    commands['finish'] = cmd_finish
    commands['editshop'] = cmd_edit_shop
    commands['editproduct'] = cmd_edit_product
    commands['approve'] = cmd_approve
    commands['deny'] = cmd_deny
    commands['ordercancel'] = cmd_order_cancel

    commands['addstore'] = cmd_add_store
    commands['delproduct'] = cmd_del_product
    rebot.register_update_handle('shop_module', update_handle=handle_update)
    store = rebot.get_module_store('shop_module')
    store['chatmode'] = {}
    store['tele_token'] = {}
    if mod_conf.rest_enabled:
        global db_conn
        global rebot_instance
        db_conn = rebot.db_conn
        rebot_instance = rebot
        eve_t = threading.Thread(target=start_eve, daemon=True)
        eve_t.start()


def unregister(rebot):
    rebot.del_module_commands('shop_module')
    rebot.del_update_handles('shop_module')


def start_eve():
    global app
    global db_conn
    global rebot_instance
    app = Eve(data=SQL, validator=ValidatorSQL, auth=BCryptAuth)

    @app.route('/api/login/')
    @requires_auth('login')
    def login_check():
        return jsonify({'success': True})

    @app.route('/api/order/<prod_id>/<anz>/<comment>')
    @requires_auth('order')
    def order(prod_id, anz, comment):
        auth_val = app.auth.get_request_auth_value().split('#')
        customer_id = int(auth_val[0])
        customer = db_conn.get_poster(customer_id, None)

        try:
            ordered = order_product(rebot_instance, prod_id, anz, comment, customer)

            return jsonify({'success': True, 'order_id': ordered.order_id})
        except ValueError as e:
            return jsonify({'success': False, 'reason': str(e)})

    @app.route('/api/order/cancel/<order_id>/<reason>')
    @requires_auth('order_cancel')
    def order_cancel(order_id, reason):
        auth_val = app.auth.get_request_auth_value().split('#')
        customer_id = int(auth_val[0])
        customer = db_conn.get_poster(customer_id, None)

        if cancel_order(rebot_instance, order_id, reason, customer.poster_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'reason': 'NOT AUTHORIZED'})

    @app.route('/api/user/register', methods=['POST'])
    def user_reg():
        body = request.get_json(force=True)
        try:
            username = body.get('username')
            if username is None:
                raise AttributeError('BODY HAS NO ATTRIBUTE: username')
            password = body.get('password')
            if password is None:
                raise AttributeError('BODY HAS NO ATTRIBUTE: password')
            ret = register_user(rebot_instance, username, password,
                                body.get('telegram_id') if 'telegram_id' in body else None)
            if ret is not True:
                return jsonify({'success': False, 'reason': ret})
            else:
                return jsonify({'success': True})
        except AttributeError as e:
            return jsonify({'success': False, 'reason': str(e)})

    @app.route('/api/user/register-telegram/<tele_id>')
    @requires_auth('telegram_register')
    def user_reg_tele(tele_id):
        auth_val = app.auth.get_request_auth_value().split('#')
        ret = register_telegram(rebot_instance, auth_val[1], tele_id)
        if ret is not True:
            return jsonify({'success': False, 'reason': ret})
        else:
            return jsonify({'success': True})

    @app.route('/api/user/update/password/', methods=['POST'])
    @requires_auth('user_pass_update')
    def user_update_pass():
        auth_val = app.auth.get_request_auth_value().split('#')

        body = request.get_json(force=True)
        try:
            password = body.get('password')
            if password is None:
                raise AttributeError('BODY HAS NO ATTRIBUTE: password')
            ret = change_password(db_conn, auth_val[1], password)
            if ret is not True:
                return jsonify({'success': False, 'reason': ret})
            else:
                return jsonify({'success': True})
        except AttributeError as e:
            return jsonify({'success': False, 'reason': str(e)})

    @app.route('/api/order/approve/<order_id>')
    @requires_auth('order_approve')
    def order_approve(order_id):
        auth_val = app.auth.get_request_auth_value().split('#')
        customer_id = int(auth_val[0])
        customer = db_conn.get_poster(customer_id, None)

        if approve_order(rebot_instance, order_id, customer.poster_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'reason': 'NOT AUTHORIZED'})

    @app.route('/api/order/finish/<order_id>')
    @requires_auth('order_finish')
    def order_finish(order_id):
        auth_val = app.auth.get_request_auth_value().split('#')
        customer_id = int(auth_val[0])
        customer = db_conn.get_poster(customer_id, None)

        if finish_order(rebot_instance, order_id, customer.poster_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'reason': 'NOT AUTHORIZED'})

    @app.route('/api/order/deny/<order_id>/<reason>')
    @requires_auth('order_deny')
    def order_deny(order_id, reason):
        auth_val = app.auth.get_request_auth_value().split('#')
        customer_id = int(auth_val[0])
        customer = db_conn.get_poster(customer_id, None)

        if deny_order(rebot_instance, order_id, reason, customer.poster_id):
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'reason': 'NOT AUTHORIZED'})

    @app.route('/api/edit/shop/<shop_id>', methods=['POST'])
    @requires_auth('shop_edit')
    def edit_shop(shop_id):
        auth_val = app.auth.get_request_auth_value().split('#')
        owner = int(auth_val[0])
        shop = db_conn.get_shop(shop_id)

        if shop.owner != owner:
            return jsonify({'success': False, 'reason': 'NOT OWNER'})

        body = request.get_json(force=True)

        shop.name = body.get('name') if body.get('name') is not None else shop.name
        shop.description = body.get('description') if body.get('description') is not None else shop.name

        db_conn.save(shop)

        return jsonify({'success': True, 'shop': {
            'name': shop.name,
            'description': shop.description,
            'shop_id': shop.shop_id,
            'owner': shop.owner
        }})

    @app.route('/api/edit/product/<product_id>', methods=['POST'])
    @requires_auth('product_edit')
    def edit_product(product_id):
        auth_val = app.auth.get_request_auth_value().split('#')
        issuer = int(auth_val[0])
        shop_owner, product, shop = db_conn.get_owner(product_id)

        if shop_owner != issuer:
            return jsonify({'success': False, 'reason': 'NOT OWNER'})

        body = request.get_json(force=True)

        product.name = body.get('name') if body.get('name') is not None else product.name
        product.comment = body.get('comment') if body.get('comment') is not None else product.comment
        try:
            product.price = float(body.get('price')) if body.get('price') is not None else product.price
        except ValueError:
            return jsonify({'success': False, 'reason': 'NOT A NUMBER'})

        db_conn.save(product)

        return jsonify({'success': True, 'product': {
            'product_id': product.product_id,
            'name': product.name,
            'shop': product.shop_id,
            'comment': product.comment,
            'price': product.price
        }})

    @app.route('/api/add/product/<shop_id>')
    @requires_auth('product_add')
    def add_product(shop_id):
        auth_val = app.auth.get_request_auth_value().split('#')
        issuer = int(auth_val[0])
        shop = db_conn.get_shop(shop_id)

        if shop.owner != issuer:
            return jsonify({'success': False, 'reason': 'NOT OWNER'})

        product = db.Product(name='NEW PRODUCT', price=0, comment='[ ]')

        body = request.get_json(force=True)

        product.name = body.get('name') if body.get('name') is not None else product.name
        product.comment = body.get('comment') if body.get('comment') is not None else product.comment
        try:
            product.price = float(body.get('price')) if body.get('price') is not None else product.price
        except ValueError:
            return jsonify({'success': False, 'reason': 'NOT A NUMBER'})

        db_conn.save(product)

        return jsonify({'success': True, 'product': {
            'product_id': product.product_id,
            'name': product.name,
            'shop': product.shop_id,
            'comment': product.comment,
            'price': product.price
        }})

    @app.route('/api/delete/product/<product_id>')
    @requires_auth('product_delete')
    def delete_product(product_id):
        auth_val = app.auth.get_request_auth_value().split('#')
        issuer = int(auth_val[0])
        shop_owner, product, shop = db_conn.get_owner(product_id)

        if shop_owner != issuer:
            return jsonify({'success': False, 'reason': 'NOT OWNER'})

        db_conn.delete(product)

        return jsonify({'success': True, 'product_id': product_id})

    @app.route('/api/orders/unapproved/')
    @requires_auth('orders')
    def user_unapproved_orders():
        auth_val = app.auth.get_request_auth_value().split('#')
        owner = int(auth_val[0])
        if not owner:
            return jsonify([])
        unap = db_conn.get_unapproved_orders(owner)
        ret_list = []

        # rebot.bot.send_message(update.message.chat.id, str(order['order_id']) + '#O\nFROM ' + customer.name + ':\n' +
        #                        str(order['amount']) + 'x' + order['name'] + '\n' + order['comment'])
        for order in unap:
            product = db_conn.get_product(order.product_id)
            # customer = db_conn.get_poster(row['customer'], None)
            obj = {'order_id': order['order_id'],
                   'amount': order['amount'],
                   'comment': order['comment'],
                   'product_id': order['product_id'],
                   'customer': order['customer'],
                   'timestamp_ordered': db.dump_datetime(order['timestamp_ordered']),
                   'timestamp_done': db.dump_datetime(order['timestamp_done']),
                   'timestamp_approved': db.dump_datetime(order['timestamp_approved']),
                   'product': {
                       'product_id': product.product_id,
                       'name': product.name,
                       'shop': product.shop_id,
                       'comment': product.comment,
                       'price': product.price
                   }
                   }
            ret_list.append(obj)
        return jsonify(json_list=ret_list)

    @app.route('/api/orders/open/')
    @requires_auth('orders')
    def user_open_orders():
        auth_val = app.auth.get_request_auth_value().split('#')
        owner = int(auth_val[0])
        if not owner:
            return jsonify([])
        unap = db_conn.get_open_orders(owner)
        ret_list = []

        # rebot.bot.send_message(update.message.chat.id, str(order['order_id']) + '#O\nFROM ' + customer.name + ':\n' +
        #                        str(order['amount']) + 'x' + order['name'] + '\n' + order['comment'])
        for order in unap:
            product = db_conn.get_product(order.product_id)
            # customer = db_conn.get_poster(row['customer'], None)
            obj = {'order_id': order['order_id'],
                   'amount': order['amount'],
                   'comment': order['comment'],
                   'product_id': order['product_id'],
                   'customer': order['customer'],
                   'timestamp_ordered': db.dump_datetime(order['timestamp_ordered']),
                   'timestamp_done': db.dump_datetime(order['timestamp_done']),
                   'timestamp_approved': db.dump_datetime(order['timestamp_approved']),
                   'product': {
                       'product_id': product.product_id,
                       'name': product.name,
                       'shop': product.shop_id,
                       'comment': product.comment,
                       'price': product.price
                   }
                   }
            ret_list.append(obj)
        return jsonify(json_list=ret_list)

    @app.route('/api/orders/my/')
    @requires_auth('orders')
    def user_my_orders():
        auth_val = app.auth.get_request_auth_value().split('#')
        issuer = int(auth_val[0])
        if not issuer:
            return jsonify([])
        my = db_conn.get_orders(issuer)
        ret_list = []

        # rebot.bot.send_message(update.message.chat.id, str(order['order_id']) + '#O\nFROM ' + customer.name + ':\n' +
        #                        str(order['amount']) + 'x' + order['name'] + '\n' + order['comment'])
        for order in my:
            product = db_conn.get_product(order.product_id)
            # customer = db_conn.get_poster(row['customer'], None)
            obj = {'order_id': order.order_id,
                   'amount': order.amount,
                   'comment': order.comment,
                   'product_id': order.product_id,
                   'customer': order.customer,
                   'timestamp_ordered': db.dump_datetime(order.timestamp_ordered),
                   'timestamp_done': db.dump_datetime(order.timestamp_done),
                   'timestamp_approved': db.dump_datetime(order.timestamp_approved),
                   'product': {
                       'product_id': product.product_id,
                       'name': product.name,
                       'shop': product.shop_id,
                       'comment': product.comment,
                       'price': product.price
                   }
                   }
            ret_list.append(obj)
        return jsonify(json_list=ret_list)

    db_eve = app.data.driver
    db.Base.metadata.bind = db_eve.engine
    db_eve.Model = db.Base

    app.run(port=mod_conf.rest_port, host=mod_conf.rest_host, use_reloader=False)


def register_user(rebot, username, password, poster_id=None):
    db_conn = rebot.db_conn
    try:
        user = db_conn.get_user(username)
        if user:
            raise ValueError

        lposter = db_conn.get_lowest_poster().poster_id - 1
        new_poster_id = lposter - 1 if lposter < 0 else -1
        db_conn.get_poster(new_poster_id, username)
        user = db.User(username=username,
                       password=bcrypt.hashpw(password.encode('utf8'), bcrypt.gensalt()).decode('utf8'),
                       poster_id=new_poster_id)

        db_conn.save(user)
        if poster_id is not None:
            return register_telegram(rebot, username, poster_id)
        return True
    except ValueError:
        return 'USERNAME ALREADY TAKEN'


def register_telegram(rebot, username, poster_id):
    db_conn = rebot.db_conn
    user = db_conn.get_user(username)
    if not user:
        return 'NOT A USER'

    if db_conn.get_user_by_poster(poster_id):
        return 'ID ALREADY REGISTERED'

    try:
        token = bcrypt.gensalt().decode('utf8')
        markup = telegram.InlineKeyboardMarkup([[
            telegram.InlineKeyboardButton('ALLOW',
                                          callback_data='teleuser#' + token),
            telegram.InlineKeyboardButton('DENY',
                                          callback_data='teledeny#' + token)
        ]])
        rebot.bot.send_message(poster_id,
                               'USER *' + username + '* HAS REQUESTED TO LINK THIS TELEGRAM USER TO THEIR ACCOUNT',
                               disable_notification=conf.silent,
                               reply_markup=markup,
                               parse_mode=telegram.ParseMode.MARKDOWN)
        store = rebot.get_module_store('shop_module')
        store['tele_token'][token] = (username, poster_id)
        return True
    except telegram.error.BadRequest:
        return 'ERROR MESSAGING USER'
    # try:
    #     user.poster_id = poster_id
    #     db_conn.get_poster(poster_id, username)
    #     db_conn.save(user)
    #     return True
    # except IntegrityError:
    #     return False


def change_password(db_conn, username, password):
    user = db_conn.get_user(username)
    try:
        user.password = bcrypt.hashpw(password.encode('utf8'), bcrypt.gensalt()).decode('utf8')
        db_conn.save(user)
        return True
    except IntegrityError:
        return False


def shop_markup(shop_id):
    return telegram.InlineKeyboardMarkup([
        [telegram.InlineKeyboardButton('EDIT NAME', callback_data='seditname#' + str(shop_id)),
         telegram.InlineKeyboardButton('EDIT DESCRIPTION', callback_data='seditdescr#' + str(shop_id))],
        [telegram.InlineKeyboardButton('ADD PRODUCT', callback_data='addproduct#' + str(shop_id))]
    ])


def product_markup(prod_id):
    return telegram.InlineKeyboardMarkup([
        [telegram.InlineKeyboardButton('EDIT NAME', callback_data='peditname#' + str(prod_id)),
         telegram.InlineKeyboardButton('EDIT PRICE', callback_data='peditprice#' + str(prod_id))],
        [telegram.InlineKeyboardButton('EDIT COMMENT', callback_data='peditcomment#' + str(prod_id))]
    ])


def handle_update(rebot, update: telegram.Update):
    if update.message:
        chatmode = rebot.get_module_store('shop_module')['chatmode']
        if update.message.chat.id in chatmode:
            if update.message.text.startswith('/cancel'):
                rebot.bot.send_message(update.message.chat.id, 'ACTION CANCELED',
                                       disable_notification=conf.silent)
                del chatmode[update.message.chat.id]
                return
            mode = chatmode[update.message.chat.id].split('#')
            if mode[0] == 'sname':
                shop = rebot.db_conn.get_shop(int(mode[1]))
                shop.name = update.message.text
                rebot.db_conn.save(shop)
                markup = shop_markup(shop.shop_id)
                rebot.bot.send_message(update.message.chat.id,
                                       'NAME SAVED\nCLICK THE BUTTONS TO EDIT *' + shop.name + '*',
                                       disable_notification=conf.silent,
                                       reply_markup=markup,
                                       parse_mode=telegram.ParseMode.MARKDOWN)
                del chatmode[update.message.chat.id]
            elif mode[0] == 'orderam':
                try:
                    amount = int(update.message.text)
                    rebot.bot.send_message(update.message.chat.id,
                                           'PLEASE SEND ME A COMMENT FOR YOUR ORDER NEXT',
                                           disable_notification=conf.silent)
                    chatmode[update.message.chat.id] = 'ordercomm#' + mode[1] + '#' + str(amount)
                except ValueError:
                    rebot.bot.send_message(update.message.chat.id,
                                           'YOU NEED TO PASS A NUMBER AS AN AMOUNT',
                                           disable_notification=conf.silent)
            elif mode[0] == 'ordercomm':
                prod_id = int(mode[1])
                amount = int(mode[2])

                del chatmode[update.message.chat.id]

                order = db.Order(timestamp_ordered=datetime.datetime.now(), comment=update.message.text,
                                 product_id=prod_id,
                                 amount=amount,
                                 customer=rebot.db_conn.get_poster(update.message.from_user.id,
                                                                   update.message.from_user.name).poster_id)

                rebot.db_conn.save(order)

                rebot.bot.send_message(update.message.chat.id, 'ORDER RECEIVED', disable_notification=conf.silent)

                owner, product, shop = rebot.db_conn.get_owner(prod_id)

                rebot.bot.send_message(owner, str(order.order_id) + '#O\n' +
                                       'ORDER RECEIVED FROM ' +
                                       update.message.from_user.name + '\n' + str(
                    order.amount) + 'x' + product.name + '\n' +
                                       order.comment,
                                       disable_notification=conf.silent)
            elif mode[0] == 'sdescr':
                shop = rebot.db_conn.get_shop(int(mode[1]))
                shop.description = update.message.text
                rebot.db_conn.save(shop)
                markup = shop_markup(shop.shop_id)
                rebot.bot.send_message(update.message.chat.id,
                                       'DESCRIPTION SAVED\nCLICK THE BUTTONS TO EDIT *' + shop.name + '*',
                                       disable_notification=conf.silent,
                                       reply_markup=markup,
                                       parse_mode=telegram.ParseMode.MARKDOWN)
                del chatmode[update.message.chat.id]
            elif mode[0] == 'pname':
                prod = rebot.db_conn.get_product(int(mode[1]))
                prod.name = update.message.text
                rebot.db_conn.save(prod)
                markup = product_markup(prod.product_id)
                rebot.bot.send_message(update.message.chat.id,
                                       'NAME SAVED\nCLICK THE BUTTONS TO EDIT *' + prod.name + '*',
                                       disable_notification=conf.silent,
                                       reply_markup=markup,
                                       parse_mode=telegram.ParseMode.MARKDOWN)
                del chatmode[update.message.chat.id]
            elif mode[0] == 'pcomment':
                prod = rebot.db_conn.get_product(int(mode[1]))
                prod.comment = update.message.text
                rebot.db_conn.save(prod)
                markup = product_markup(prod.product_id)
                rebot.bot.send_message(update.message.chat.id,
                                       'COMMENT SAVED\nCLICK THE BUTTONS TO EDIT *' + prod.name + '*',
                                       disable_notification=conf.silent,
                                       reply_markup=markup,
                                       parse_mode=telegram.ParseMode.MARKDOWN)
                del chatmode[update.message.chat.id]
            elif mode[0] == 'pprice':
                prod = rebot.db_conn.get_product(int(mode[1]))
                try:
                    prod.price = float(update.message.text)
                    rebot.db_conn.save(prod)
                    markup = product_markup(prod.product_id)
                    rebot.bot.send_message(update.message.chat.id,
                                           'PRICE SAVED\nCLICK THE BUTTONS TO EDIT *' + prod.name + '*',
                                           disable_notification=conf.silent,
                                           reply_markup=markup,
                                           parse_mode=telegram.ParseMode.MARKDOWN)
                    del chatmode[update.message.chat.id]
                except ValueError:
                    rebot.bot.send_message(update.message.chat.id,
                                           'YOU NEED TO PASS A FLOAT VALUE AS A PRICE',
                                           disable_notification=conf.silent,
                                           parse_mode=telegram.ParseMode.MARKDOWN)

    if update.callback_query:
        show_alert = False
        text = None
        query = update.callback_query
        if query.data:
            split = query.data.split('#')
            cmd = split[0]
            args = split[1:]

            chat_id = query.message.chat.id
            if cmd == 'getproducts':

                shop_id = int(args[0])
                products = rebot.db_conn.get_products(shop_id)
                for product in products:
                    # markup = telegram.InlineKeyboardMarkup([
                    #     [telegram.InlineKeyboardButton('Order',
                    #                                    callback_data='order#' + str(product.product_id))]
                    # ])
                    markup = telegram.InlineKeyboardMarkup(
                        [[telegram.InlineKeyboardButton('ORDER', callback_data='order#' + str(product.product_id))]])
                    rebot.bot.send_message(chat_id,
                                           str(
                                               product.product_id) + '#P\n*' + product.name + '; {:3.2f}€*'.format(
                                               product.price) + '\n' + product.comment,
                                           disable_notification=conf.silent,
                                           reply_markup=markup,
                                           parse_mode=telegram.ParseMode.MARKDOWN
                                           # reply_markup=markup
                                           )
                # rebot.bot.send_message(chat_id, 'REPLY TO A PRODUCT WITH THE /order COMMAND TO ORDER IT')
            if cmd == 'order':
                prod_id = args[0]
                chatmode = rebot.get_module_store('shop_module')['chatmode']
                chatmode[chat_id] = 'orderam#' + prod_id

                rebot.bot.send_message(chat_id=chat_id, message_id=query.message.message_id,
                                       text='PLEASE SEND ME THE AMOUNT YOU WANT TO ORDER\nTO CANCEL CALL /cancel')
            elif cmd == 'teleuser':
                token = args[0]

                try:
                    username, poster_id = rebot.get_module_store('shop_module')['tele_token'][token]

                    rebot.db_conn.get_poster(poster_id, query.from_user.name)

                    user = rebot.db_conn.get_user(username)
                    user.poster_id = poster_id
                    rebot.db_conn.save(user)

                    query.message.delete()
                    rebot.bot.send_message(chat_id=chat_id,
                                           text='REQUEST ACCEPTED')
                except KeyError:
                    query.message.delete()
                    rebot.bot.send_message(chat_id=chat_id,
                                           text='TOKEN NOT FOUND')
            elif cmd == 'teledeny':
                token = args[0]

                try:
                    del rebot.get_module_store('shop_module')['tele_token'][token]
                except KeyError:
                    pass
                query.message.delete()
                rebot.bot.send_message(chat_id=chat_id,
                                       text='REQUEST DENIED')
            elif cmd == 'addproduct':
                shop_id = args[0]

                prod = db.Product(name='NEW PRODUCT', price=0, comment='[ ]', shop_id=shop_id)
                rebot.db_conn.save(prod)
                rebot.bot.send_message(chat_id=chat_id,
                                       text=str(prod.product_id) + '#P\nPRODUCT ADDED')
            elif cmd == 'seditname':
                shop_id = args[0]
                chatmode = rebot.get_module_store('shop_module')['chatmode']
                chatmode[chat_id] = 'sname#' + shop_id

                rebot.bot.edit_message_text(chat_id=chat_id, message_id=query.message.message_id,
                                            text='PLEASE SEND ME A NEW NAME FOR YOUR STORE\nTO CANCEL CALL /cancel',
                                            reply_markup=None)
            elif cmd == 'seditdescr':
                shop_id = args[0]
                chatmode = rebot.get_module_store('shop_module')['chatmode']
                chatmode[chat_id] = 'sdescr#' + shop_id

                rebot.bot.edit_message_text(chat_id=chat_id, message_id=query.message.message_id,
                                            text='PLEASE SEND ME A NEW DESCRIPTION FOR YOUR STORE\nTO CANCEL CALL /cancel',
                                            reply_markup=None)
            elif cmd == 'peditname':
                prod_id = args[0]
                chatmode = rebot.get_module_store('shop_module')['chatmode']
                chatmode[chat_id] = 'pname#' + prod_id

                rebot.bot.edit_message_text(chat_id=chat_id, message_id=query.message.message_id,
                                            text='PLEASE SEND ME A NEW NAME FOR YOUR PRODUCT\nTO CANCEL CALL /cancel',
                                            reply_markup=None)
            elif cmd == 'peditcomment':
                prod_id = args[0]
                chatmode = rebot.get_module_store('shop_module')['chatmode']
                chatmode[chat_id] = 'pcomment#' + prod_id

                rebot.bot.edit_message_text(chat_id=chat_id, message_id=query.message.message_id,
                                            text='PLEASE SEND ME A NEW COMMENT FOR YOUR PRODUCT\nTO CANCEL CALL /cancel',
                                            reply_markup=None)
            elif cmd == 'peditprice':
                prod_id = args[0]
                chatmode = rebot.get_module_store('shop_module')['chatmode']
                chatmode[chat_id] = 'pprice#' + prod_id

                rebot.bot.edit_message_text(chat_id=chat_id, message_id=query.message.message_id,
                                            text='PLEASE SEND ME A NEW PRICE FOR YOUR PRODUCT\nTO CANCEL CALL /cancel',
                                            reply_markup=None)

        try:
            query.answer(show_alert=show_alert, text=text)
        except telegram.error.BadRequest as e:
            print(str(e))


def cmd_list_shops(rebot, args, update):
    shops = rebot.db_conn.get_shops()

    for shop in shops:
        poster = rebot.db_conn.get_poster(shop.owner, None)
        markup = telegram.InlineKeyboardMarkup([
            [telegram.InlineKeyboardButton('GET PRODUCTS', callback_data='getproducts#' + str(shop.shop_id))]
        ])
        rebot.bot.send_message(update.message.chat.id,
                               str(
                                   shop.shop_id) + '#S\n*' + shop.name + '* BY ' + poster.name + '\n' + shop.description,
                               disable_notification=conf.silent,
                               reply_markup=markup,
                               parse_mode=telegram.ParseMode.MARKDOWN)


def order_product(rebot, p_id, amount, comment, customer):
    order = db.Order(timestamp_ordered=datetime.datetime.now(), comment=comment, product_id=p_id, amount=amount,
                     customer=customer.poster_id)

    rebot.db_conn.save(order)

    owner, product, shop = rebot.db_conn.get_owner(p_id)

    if owner >= 0:
        rebot.bot.send_message(owner, str(order.order_id) + '#O\n' +
                               'ORDER RECEIVED FROM ' +
                               customer.name + '\n' + str(order.amount) + 'x' + product.name + '\n' +
                               order.comment,
                               disable_notification=conf.silent)
    return order


def cmd_order(rebot, args, update):
    try:
        p_text = update.message.reply_to_message.text
        p_id = p_text.split('#P')[0]

        amount = int(args[0])
        if len(args) <= 1:
            raise ValueError('Too few arguments')
        comment = ' '.join(args[1:])

        order = order_product(rebot, p_id, amount, comment, rebot.db_conn.get_poster(update.message.from_user.id,
                                                                                     update.message.from_user.name))

        rebot.bot.send_message(update.message.chat.id, str(order.order_id) + '#O\nORDER RECEIVED',
                               disable_notification=conf.silent)

    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'USAGE: /order [amount] [comment...]')


def cmd_list_orders(rebot, args, update):
    user_id = update.message.from_user.id
    open = rebot.db_conn.get_open_orders(user_id)
    if len(open) == 0:
        return
    rebot.bot.send_message(update.message.chat.id, 'START;ORDERS-------------------')
    for order in open:
        print(order.keys())
        customer = rebot.db_conn.get_poster(order['customer'], None)
        rebot.bot.send_message(update.message.chat.id, str(order['order_id']) + '#O\nFROM ' + customer.name + ':\n' +
                               str(order['amount']) + 'x' + order['name'] + '\n' + order['comment'])

    rebot.bot.send_message(update.message.chat.id, 'END;ORDERS---------------------')


def cancel_order(rebot, order_id, reason, issuer):
    order = rebot.db_conn.get_order(order_id)

    owner, prod, shop = rebot.db_conn.get_owner(order.product_id)

    if order.customer != issuer and issuer not in conf.bot_overlords:
        return False

    rebot.db_conn.del_order(order.order_id)

    if owner >= 0:
        rebot.bot.send_message(owner,
                               'ORDER CANCELED: ' + str(order.amount) + 'x' + prod.name + '\n' +
                               order.comment + '\nREASON: ' + reason,
                               disable_notification=conf.silent)
    return True


def cmd_order_cancel(rebot, args, update):
    try:
        o_text = update.message.reply_to_message.text
        o_id = o_text.split('#O')[0]

        if not cancel_order(rebot, o_id, ' '.join(args), update.message.from_user.id):
            rebot.bot.send_message(update.message.chat.id, 'YOU ARE NOT THE ISSUER OF THIS ORDER',
                                   disable_notification=conf.silent)
            return

        rebot.bot.send_message(update.message.chat.id, 'ORDER CANCELED', disable_notification=conf.silent)
    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'REPLY TO A ORDER TO CANCEL IT')


def cmd_list_orders_unapproved(rebot, args, update):
    user_id = update.message.from_user.id
    open = rebot.db_conn.get_unapproved_orders(user_id)
    if len(open) == 0:
        return
    rebot.bot.send_message(update.message.chat.id, 'START;ORDERS-------------------')
    for order in open:
        print(order.keys())
        customer = rebot.db_conn.get_poster(order['customer'], None)
        rebot.bot.send_message(update.message.chat.id, str(order['order_id']) + '#O\nFROM ' + customer.name + ':\n' +
                               str(order['amount']) + 'x' + order['name'] + '\n' + order['comment'])

    rebot.bot.send_message(update.message.chat.id, 'END;ORDERS---------------------')


def cmd_list_my_orders(rebot, args, update):
    user_id = update.message.from_user.id
    orders = rebot.db_conn.get_orders(user_id)
    if len(orders) == 0:
        return
    rebot.bot.send_message(update.message.chat.id, 'START;ORDERS-------------------')
    for order in orders:
        prod = rebot.db_conn.get_product(order.product_id)
        customer = rebot.db_conn.get_poster(order.customer, None)
        rebot.bot.send_message(update.message.chat.id, str(order.order_id) + '#O\nFROM ' + customer.name + ':\n' +
                               str(order.amount) + 'x' + prod.name + '\n' + order.comment)

    rebot.bot.send_message(update.message.chat.id, 'END;ORDERS---------------------')


def approve_order(rebot, order_id, issuer):
    order = rebot.db_conn.get_order(order_id)

    owner, prod, shop = rebot.db_conn.get_owner(order.product_id)

    if owner != issuer and issuer not in conf.bot_overlords:
        return False

    order.timestamp_approved = datetime.datetime.now()
    rebot.db_conn.save(order)

    if order.customer >= 0:
        rebot.bot.send_message(order.customer,
                               'ORDER APPROVED: ' + str(order.amount) + 'x' + prod.name + '\n' +
                               order.comment,
                               disable_notification=conf.silent)
    return True


def cmd_approve(rebot, args, update):
    try:
        o_text = update.message.reply_to_message.text
        o_id = o_text.split('#O')[0]

        if not approve_order(rebot, o_id, update.message.from_user.id):
            rebot.bot.send_message(update.message.chat.id, 'YOU ARE NOT THE OWNER OF THIS STORE',
                                   disable_notification=conf.silent)
            return

        rebot.bot.send_message(update.message.chat.id, 'ORDER APPROVED', disable_notification=conf.silent)
    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'REPLY TO A ORDER TO APPROVE IT')


def deny_order(rebot, order_id, reason, issuer):
    order = rebot.db_conn.get_order(order_id)

    owner, prod, shop = rebot.db_conn.get_owner(order.product_id)

    if owner != issuer and issuer not in conf.bot_overlords:
        return False

    rebot.db_conn.del_order(order.order_id)

    if order.customer >= 0:
        rebot.bot.send_message(order.customer,
                               'ORDER DENIED: ' + str(order.amount) + 'x' + prod.name + '\n' +
                               order.comment + '\nREASON: ' + reason,
                               disable_notification=conf.silent)
    return True


def cmd_deny(rebot, args, update):
    try:
        o_text = update.message.reply_to_message.text
        o_id = o_text.split('#O')[0]

        if not deny_order(rebot, o_id, ' '.join(args), update.message.from_user.id):
            rebot.bot.send_message(update.message.chat.id, 'YOU ARE NOT THE OWNER OF THIS STORE',
                                   disable_notification=conf.silent)
            return

        rebot.bot.send_message(update.message.chat.id, 'ORDER DENIED', disable_notification=conf.silent)
    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'REPLY TO A ORDER TO APPROVE IT')


def finish_order(rebot, order_id, issuer):
    order = rebot.db_conn.get_order(order_id)

    owner, prod, shop = rebot.db_conn.get_owner(order.product_id)

    if owner != issuer and issuer not in conf.bot_overlords:
        return False

    order.timestamp_done = datetime.datetime.now()
    rebot.db_conn.save(order)

    if order.customer >= 0:
        rebot.bot.send_message(order.customer,
                               'ORDER FINISHED: ' + str(order.amount) + 'x' + prod.name + '\n' +
                               order.comment,
                               disable_notification=conf.silent)
    return True


def cmd_finish(rebot, args, update):
    try:
        o_text = update.message.reply_to_message.text
        o_id = o_text.split('#O')[0]

        if not finish_order(rebot, o_id, update.message.from_user.id):
            rebot.bot.send_message(update.message.chat.id, 'YOU ARE NOT THE OWNER OF THIS STORE',
                                   disable_notification=conf.silent)
            return

        rebot.bot.send_message(update.message.chat.id, 'ORDER FINISHED', disable_notification=conf.silent)
    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'REPLY TO A ORDER TO FINISH IT')


def cmd_edit_shop(rebot, args, update):
    try:
        s_text = update.message.reply_to_message.text
        s_id = s_text.split('#S')[0]

        shop = rebot.db_conn.get_shop(s_id)

        if shop.owner != update.message.from_user.id and update.message.from_user.id not in conf.bot_overlords:
            rebot.bot.send_message(update.message.chat.id, 'YOU ARE NOT THE OWNER OF THIS STORE',
                                   disable_notification=conf.silent)
            return

        markup = shop_markup(shop.shop_id)
        rebot.bot.send_message(update.message.chat.id,
                               'CLICK THE BUTTONS TO EDIT *' + shop.name + '*',
                               disable_notification=conf.silent,
                               reply_markup=markup,
                               parse_mode=telegram.ParseMode.MARKDOWN)
    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'REPLY TO A SHOP TO EDIT IT')


def cmd_edit_product(rebot, args, update):
    try:
        p_text = update.message.reply_to_message.text
        p_id = p_text.split('#P')[0]

        owner, prod, shop = rebot.db_conn.get_owner(p_id)

        if owner != update.message.from_user.id and update.message.from_user.id not in conf.bot_overlords:
            rebot.bot.send_message(update.message.chat.id, 'YOU ARE NOT THE OWNER OF THIS STORE',
                                   disable_notification=conf.silent)
            return

        markup = product_markup(prod.product_id)
        rebot.bot.send_message(update.message.chat.id,
                               'CLICK THE BUTTONS TO EDIT *' + prod.name + '*',
                               disable_notification=conf.silent,
                               reply_markup=markup,
                               parse_mode=telegram.ParseMode.MARKDOWN)
    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'REPLY TO A PRODUCT TO EDIT IT')


def cmd_add_store(rebot, args, update):
    try:
        if update.message.from_user.id not in conf.bot_overlords:
            rebot.bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
                                   disable_notification=conf.silent)
            return

        reply_user = update.message.reply_to_message.from_user.id

        store = db.Shop(name='NEW STORE',
                        owner=rebot.db_conn.get_poster(reply_user,
                                                       'NEWUSER [PLEASE USE /userreg TO REGISTER YOUR NAME]').poster_id,
                        description='[ ]')
        rebot.db_conn.save(store)
        rebot.bot.send_message(update.message.chat.id, 'STORE CREATED',
                               disable_notification=conf.silent)
    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'REPLY TO A USER TO ADD A STORE TO HIM')


def cmd_del_product(rebot, args, update):
    try:
        p_text = update.message.reply_to_message.text
        p_id = p_text.split('#P')[0]

        owner, prod, shop = rebot.db_conn.get_owner(p_id)

        if owner != update.message.from_user.id and update.message.from_user.id not in conf.bot_overlords:
            rebot.bot.send_message(update.message.chat.id, 'YOU ARE NOT THE OWNER OF THIS STORE',
                                   disable_notification=conf.silent)
            return

        rebot.db_conn.delete_product(prod)
        rebot.bot.send_message(update.message.chat.id, 'PRODUCT DELETED',
                               disable_notification=conf.silent)
    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'REPLY TO A PRODUCT TO DELETE IT')
