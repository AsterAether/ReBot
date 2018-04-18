import datetime
import conf
import telegram

import db


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
    rebot.register_update_handle('shop_module', update_handle=handle_update)
    store = rebot.get_module_store('shop_module')
    store['chatmode'] = {}


def unregister(rebot):
    rebot.del_module_commands('shop_module')
    rebot.del_update_handles('shop_module')


def shop_markup(shop_id):
    return telegram.InlineKeyboardMarkup([
        [telegram.InlineKeyboardButton('EDIT NAME', callback_data='seditname#' + str(shop_id)),
         telegram.InlineKeyboardButton('EDIT DESCRIPTION', callback_data='seditdescr#' + str(shop_id))]
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
                               str(shop.shop_id) + '#S\n' + shop.name + ' BY ' + poster.name + '\n' + shop.description,
                               disable_notification=conf.silent,
                               reply_markup=markup)


def cmd_order(rebot, args, update):
    try:
        p_text = update.message.reply_to_message.text
        p_id = p_text.split('#P')[0]

        amount = int(args[0])
        if len(args) <= 1:
            raise ValueError('Too few arguments')
        comment = ' '.join(args[1:])

        order = db.Order(timestamp_ordered=datetime.datetime.now(), comment=comment, product_id=p_id, amount=amount,
                         customer=rebot.db_conn.get_poster(update.message.from_user.id,
                                                           update.message.from_user.name).poster_id)

        rebot.db_conn.save(order)

        rebot.bot.send_message(update.message.chat.id, 'ORDER RECEIVED', disable_notification=conf.silent)

        owner, product, shop = rebot.db_conn.get_owner(p_id)

        rebot.bot.send_message(owner, str(order.order_id) + '#O\n' +
                               'ORDER RECEIVED FROM ' +
                               update.message.from_user.name + '\n' + str(order.amount) + 'x' + product.name + '\n' +
                               order.comment,
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


def cmd_order_cancel(rebot, args, update):
    try:
        o_text = update.message.reply_to_message.text
        o_id = o_text.split('#O')[0]

        order = rebot.db_conn.get_order(o_id)

        owner, prod, shop = rebot.db_conn.get_owner(order.product_id)

        if order.customer != update.message.from_user.id or update.message.from_user.id not in conf.bot_overlords:
            rebot.bot.send_message(update.message.chat.id, 'YOU ARE NOT THE ISSUER OF THIS ORDER',
                                   disable_notification=conf.silent)
            return

        rebot.bot.send_message(owner,
                               'ORDER CANCELED: ' + str(order.amount) + 'x' + prod.name + '\n' +
                               order.comment + '\nREASON: ' + ' '.join(args),
                               disable_notification=conf.silent)

        rebot.db_conn.del_order(order.order_id)

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


def cmd_approve(rebot, args, update):
    try:
        o_text = update.message.reply_to_message.text
        o_id = o_text.split('#O')[0]

        order = rebot.db_conn.get_order(o_id)

        owner, prod, shop = rebot.db_conn.get_owner(order.product_id)

        if owner != update.message.from_user.id or update.message.from_user.id not in conf.bot_overlords:
            rebot.bot.send_message(update.message.chat.id, 'YOU ARE NOT THE OWNER OF THIS STORE',
                                   disable_notification=conf.silent)
            return

        rebot.bot.send_message(order.customer,
                               'ORDER APPROVED: ' + str(order.amount) + 'x' + prod.name + '\n' +
                               order.comment,
                               disable_notification=conf.silent)

        order.timestamp_approved = datetime.datetime.now()
        rebot.db_conn.save(order)

        rebot.bot.send_message(update.message.chat.id, 'ORDER APPROVED', disable_notification=conf.silent)
    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'REPLY TO A ORDER TO APPROVE IT')


def cmd_deny(rebot, args, update):
    try:
        o_text = update.message.reply_to_message.text
        o_id = o_text.split('#O')[0]

        order = rebot.db_conn.get_order(o_id)

        owner, prod, shop = rebot.db_conn.get_owner(order.product_id)

        if owner != update.message.from_user.id or update.message.from_user.id not in conf.bot_overlords:
            rebot.bot.send_message(update.message.chat.id, 'YOU ARE NOT THE OWNER OF THIS STORE',
                                   disable_notification=conf.silent)
            return

        rebot.bot.send_message(order.customer,
                               'ORDER DENIED: ' + str(order.amount) + 'x' + prod.name + '\n' +
                               order.comment + '\nREASON: ' + ' '.join(args),
                               disable_notification=conf.silent)

        rebot.db_conn.del_order(order.order_id)

        rebot.bot.send_message(update.message.chat.id, 'ORDER DENIED', disable_notification=conf.silent)
    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'REPLY TO A ORDER TO APPROVE IT')


def cmd_finish(rebot, args, update):
    try:
        o_text = update.message.reply_to_message.text
        o_id = o_text.split('#O')[0]

        order = rebot.db_conn.get_order(o_id)

        owner, prod, shop = rebot.db_conn.get_owner(order.product_id)

        if owner != update.message.from_user.id or update.message.from_user.id not in conf.bot_overlords:
            rebot.bot.send_message(update.message.chat.id, 'YOU ARE NOT THE OWNER OF THIS STORE',
                                   disable_notification=conf.silent)
            return

        rebot.bot.send_message(order.customer,
                               'ORDER FINISHED: ' + str(order.amount) + 'x' + prod.name + '\n' +
                               order.comment,
                               disable_notification=conf.silent)

        order.timestamp_done = datetime.datetime.now()
        rebot.db_conn.save(order)

        rebot.bot.send_message(update.message.chat.id, 'ORDER FINISHED', disable_notification=conf.silent)
    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'REPLY TO A ORDER TO FINISH IT')


def cmd_edit_shop(rebot, args, update):
    try:
        s_text = update.message.reply_to_message.text
        s_id = s_text.split('#S')[0]

        shop = rebot.db_conn.get_shop(s_id)

        if shop.owner != update.message.from_user.id or update.message.from_user.id not in conf.bot_overlords:
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

        if owner != update.message.from_user.id or update.message.from_user.id not in conf.bot_overlords:
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
