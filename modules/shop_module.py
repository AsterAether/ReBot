import datetime
import conf
import telegram

import db


def register(rebot):
    commands = rebot.get_module_commands('shop_module')
    commands['listshops'] = cmd_list_shops
    commands['order'] = cmd_order
    commands['listorders'] = cmd_list_orders
    commands['finish'] = cmd_finish
    commands['editshop'] = cmd_edit_shop
    commands['editproduct'] = cmd_edit_product
    rebot.register_update_handle('shop_module', update_handle=handle_update)


def unregister(rebot):
    rebot.del_module_commands('shop_module')
    rebot.del_update_handles('shop_module')


def handle_update(rebot, update: telegram.Update):
    if update.callback_query:
        query = update.callback_query
        if query.data:
            split = query.data.split('#')
            cmd = split[0]
            args = split[1:]

            if cmd == 'getproducts':
                chat_id = query.message.chat.id

                shop_id = int(args[0])
                products = rebot.db_conn.get_products(shop_id)
                for product in products:
                    # markup = telegram.InlineKeyboardMarkup([
                    #     [telegram.InlineKeyboardButton('Order',
                    #                                    callback_data='order#' + str(product.product_id))]
                    # ])
                    rebot.bot.send_message(chat_id,
                                           str(
                                               product.product_id) + '#P\n' + product.name + '; {:3.2f}€'.format(
                                               product.price) + '\n' + product.comment,
                                           disable_notification=conf.silent,
                                           # reply_markup=markup
                                           )
                rebot.bot.send_message(chat_id, 'REPLY TO A PRODUCT WITH THE /order COMMAND TO ORDER IT')
        try:
            query.answer()
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
                               str(shop.shop_id) + '#S\n' + shop.name + ' by ' + poster.name + '\n' + shop.description,
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


def cmd_finish(rebot, args, update):
    try:
        o_text = update.message.reply_to_message.text
        o_id = o_text.split('#O')[0]

        order = rebot.db_conn.get_order(o_id)

        owner, prod, shop = rebot.db_conn.get_owner(order.product_id)

        if owner != update.message.from_user.id:
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
        s_id = s_text.split('#O')[0]

        shop = rebot.db_conn.get_shops(s_id)

        if shop.owner != update.message.from_user.id:
            rebot.bot.send_message(update.message.chat.id, 'YOU ARE NOT THE OWNER OF THIS STORE',
                                   disable_notification=conf.silent)
            return

        markup = telegram.InlineKeyboardMarkup([
            [telegram.InlineKeyboardButton('EDIT NAME', callback_data='seditname#' + str(shop.shop_id)),
             telegram.InlineKeyboardButton('EDIT DESCRIPTION', callback_data='seditdescr#' + str(shop.shop_id))]
        ])
        rebot.bot.send_message(update.message.chat.id,
                               'CLICK THE BUTTONS TO EDIT ' + shop.name,
                               disable_notification=conf.silent,
                               reply_markup=markup)
    except (AttributeError, KeyError, ValueError, IndexError) as e:
        print(str(e))
        rebot.bot.send_message(update.message.chat.id, 'REPLY TO A SHOP TO EDIT IT')


def cmd_edit_product(rebot, args, update):
    pass
