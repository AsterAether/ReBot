import os
import threading
import time
import traceback

import schedule
import telegram

import conf
import db

import importlib


class ReBot:

    def __init__(self):
        self.bot = telegram.Bot(conf.token)
        self.scheduler = schedule.Scheduler()
        self.db_conn = db.Database(driver=conf.db_driver, db_user=conf.db_user, db_pass=conf.db_password,
                                   db_host=conf.db_host, db_name=conf.db_name)
        self.user_jail = {}
        self.can = {}
        self.commands = {
            'bot':
                {'start': ReBot.cmd_start,
                 'help': ReBot.cmd_help,
                 'userreg': ReBot.cmd_userreg,
                 'userid': ReBot.cmd_user_id}
        }
        # Admin CMDs (silent):
        self.admin_commands = {
            'del': ReBot.cmd_del,
            'msg': ReBot.cmd_msg,
            'msgc': ReBot.cmd_msg_chat
        }

        self.module_store = {}
        self.module_chat_config = {}
        self.modules = {}
        self.handle_update = {}
        self.chat_config = {}

    def get_module_store(self, module):
        if module not in self.module_store:
            self.module_store[module] = {}

        return self.module_store[module]

    @staticmethod
    def cmd_userreg(rebot, args, update):
        rebot.db_conn.update_poster(update.message.from_user.id, update.message.from_user.name)

    @staticmethod
    def cmd_help(rebot, args, update):
        text = 'COMMANDS;\n'
        for module in rebot.commands.keys():
            if not rebot.module_enabled(module, update.message.chat.id):
                continue
            cmds = rebot.commands[module]
            cmd_text = ', '.join('/' + c for c in
                                 sorted(cmds.keys()))
            text += module.upper() + ': ' + cmd_text + '\n'
        rebot.bot.send_message(update.message.chat.id,
                               text,
                               disable_notification=conf.silent)

    def register_chat_conf(self, module, conf):
        self.module_chat_config[module] = conf

    def start(self):
        stop_pill = threading.Event()
        bot_thread = threading.Thread(target=self.bot_loop, name='bot_thread', args=(stop_pill,))
        bot_thread.start()
        line_input = ''
        while line_input != 'exit':
            line_input = input('').strip()
            # try:
            #     cmd = line_input.split(' ')
            # except (KeyError, ValueError):
            #     print('ERROR IN INPUT: ' + line_input)

        stop_pill.set()

    def get_module_commands(self, module):
        if module not in self.commands:
            self.commands[module] = {}
        return self.commands[module]

    def del_module_commands(self, module):
        if module in self.commands:
            del self.commands[module]

    @staticmethod
    def tmp_clear():
        for the_file in os.listdir('tmp/'):
            file_path = os.path.join('tmp/', the_file)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(e)

    def register_update_handle(self, module, update_handle):
        if module not in self.handle_update:
            self.handle_update[module] = []

        self.handle_update[module].append(update_handle)

    def del_update_handles(self, module):
        del self.handle_update[module]

    def bot_loop(self, pill):

        dirs = ['files', 'tmp', 'config']
        for dir in dirs:
            if not os.path.exists(dir):
                os.mkdir(dir)

        self.db_conn.start_engine()
        self.db_conn.start_session()

        offset = 0

        self.scheduler.every(conf.reset_cmds).minutes.do(self.reset_jail)
        self.scheduler.every(conf.clear_every).minutes.do(ReBot.tmp_clear)

        for module_name in conf.modules:
            module = importlib.import_module('modules.' + module_name)
            module.register(self)
            print('Loaded; ' + module_name)
            self.modules[module_name] = module

        default_conf = {}
        for module in self.modules.keys():
            default_conf[module + '_enabled'] = True
            try:
                mod_conf = self.module_chat_config[module]
                for key in mod_conf.keys():
                    default_conf[key] = mod_conf[key]
            except KeyError:
                pass

        for the_file in os.listdir('config/'):
            file_path = os.path.join('config/', the_file)
            conf_chat_id = int(file_path.replace('.conf', '').replace('config/', ''))
            try:
                if os.path.isfile(file_path):
                    with open(file_path, 'r', encoding='utf8') as f:
                        chat_conf = eval(f.read())
                    self.chat_config[conf_chat_id] = chat_conf
            except Exception as e:
                print(e)

        while not pill.is_set():
            try:
                updates = self.bot.get_updates(offset=offset)
                for update in updates:
                    if update.message:
                        message = update.message
                        if message.chat.id not in self.chat_config:
                            self.chat_config[message.chat.id] = default_conf
                            with open('config/' + str(message.chat.id) + '.conf', 'w') as f:
                                f.write(str(default_conf))
                    # print(update)
                    # if update.message:
                    #     print(update.message.parse_entities())
                    # if conf.import_mode:
                    #     handle_import(update)
                    # else:
                    #     handle_repost(update)
                    for module in self.handle_update.keys():
                        if update.message:
                            if self.module_enabled(module, update.message.chat.id):
                                for update_handle in self.handle_update[module]:
                                    update_handle(self, update)
                        else:
                            for update_handle in self.handle_update[module]:
                                update_handle(self, update)
                    self.handle_commands(update)
                if len(updates) > 0:
                    offset = updates[-1].update_id + 1
            except telegram.error.TimedOut:
                # print('No updates.')
                pass
            except telegram.error.TelegramError as e:
                print('Error: ' + str(e))
                traceback.print_exc()

            self.scheduler.run_pending()
            time.sleep(conf.timeout)

        for module in self.modules.values():
            module.unregister(self)
            print('Unloaded ' + str(module))

        self.db_conn.stop_session()
        self.db_conn.stop_engine()

    def module_enabled(self, module, chat_id):
        if module == 'bot':
            return True
        return self.chat_config[chat_id][module + '_enabled']

    def get_chat_conf(self, chat_id, conf):
        if conf not in self.chat_config[chat_id]:
            return False
        return self.chat_config[chat_id][conf]

    @staticmethod
    def check_is_overlord(user_id):
        return user_id in conf.bot_overlords

    @staticmethod
    def get_text(message):
        msg_text = None

        if message.text:
            msg_text = message.text

        if message.caption:
            msg_text = message.caption

        return msg_text

    @staticmethod
    def cmd_user_id(rebot, args, update):
        rebot.bot.send_message(update.message.chat.id, 'YOUR ID IS: ' + str(update.message.from_user.id),
                               disable_notification=conf.silent)

    @staticmethod
    def cmd_start(rebot, args, update):
        rebot.bot.send_message(update.message.chat.id, 'HELLO; IF YOU NEED HELP CALL /help',
                               disable_notification=conf.silent)

    @staticmethod
    def cmd_del(rebot, args, update):
        if not ReBot.check_is_overlord(update.message.from_user.id):
            # bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
            #                  disable_notification=conf.silent)
            poster = rebot.db.get_poster(update.message.from_user.id, update.message.from_user.name)
            print('USER ' + poster.name + ' TRIED TO CALL DEL')
            return

        try:
            info = update.message.reply_to_message
            try:
                info.delete()
            except telegram.error.BadRequest:
                print('ERROR ON DEL: MESSAGE ALREADY DELETED')
            except AttributeError:
                print('ERROR ON DEL: NO MESSAGE IN REPLY TO DELETE')

            try:
                update.message.delete()
            except telegram.error.BadRequest:
                print('ERROR ON DEL: COMMAND MESSAGE DELETED')
        except (AttributeError, ValueError) as e:
            print('ERROR ON DEL' + str(e))

    @staticmethod
    def cmd_msg(rebot, args, update):
        if not ReBot.check_is_overlord(update.message.from_user.id):
            # bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
            #                  disable_notification=conf.silent)
            poster = rebot.db.get_poster(update.message.from_user.id, update.message.from_user.name)
            print('USER ' + poster.name + ' TRIED TO CALL MSG')
            return

        if len(args) == 0:
            print('ERROR ON MSG: ARGUMENT NEEDED')
            return

        text = ' '.join(args)

        rebot.bot.send_message(update.message.chat.id, text.upper())

        try:
            update.message.delete()
        except telegram.error.BadRequest:
            print('ERROR ON MSG: COMMAND MESSAGE DELETED')

    @staticmethod
    def cmd_msg_chat(rebot, args, update):
        if not ReBot.check_is_overlord(update.message.from_user.id):
            # bot.send_message(update.message.chat.id, 'SORRY YOU ARE NOT ONE OF MY OVERLORDS',
            #                  disable_notification=conf.silent)
            poster = rebot.db.get_poster(update.message.from_user.id, update.message.from_user.name)
            print('USER ' + poster.name + ' TRIED TO CALL MSG_CHAT')
            return

        if len(args) <= 1:
            print('ERROR ON MSG_CHAT: ARGUMENT NEEDED')
            return

        text = ' '.join(args[1:])
        try:
            chat_id = int(args[0])
        except ValueError:
            print('ERROR ON MSG_CHAT: ID NOT INT')
            return

        try:
            rebot.bot.send_message(chat_id, text.upper())
        except telegram.error.BadRequest as e:
            print('ERROR ON MSG_CHAT: ' + str(e))

        try:
            update.message.delete()
        except telegram.error.BadRequest:
            print('ERROR ON MSG_CHAT: COMMAND MESSAGE DELETED')

    def command_allowed(self, poster_id, chat_id):
        if chat_id not in self.user_jail:
            self.user_jail[chat_id] = {}

        chat_jail = self.user_jail[chat_id]

        if poster_id in conf.bot_overlords:
            return True

        if poster_id not in chat_jail:
            chat_jail[poster_id] = 1
            return True

        if chat_jail[poster_id] >= conf.max_cmds:
            return False

        chat_jail[poster_id] += 1
        return True

    def handle_commands(self, update):
        if update.message and update.message.text and update.message.text.startswith('/'):
            command = update.message.text[1:]
            print('COMMAND RECEIVED: ' + command + ' FROM ' + update.message.from_user.name)
            cmd_split = command.split(' ')
            cmd = cmd_split[0]
            args = cmd_split[1:]
            if update.message.chat.type != 'private':
                if conf.bot_name in cmd:
                    cmd = cmd.replace(conf.bot_name, '')
                elif '@' in cmd:
                    return

            if update.message.from_user.id not in conf.bot_overlords and not self.can_call(cmd, update.message.chat.id):
                return

            if update.message.from_user.id in self.user_jail:
                print('TRIES: ' + str(self.user_jail[update.message.from_user.id]))
            if update.message.chat.type == 'group':
                if not self.command_allowed(update.message.from_user.id, update.message.chat.id):
                    return
            for module in self.commands.keys():
                if self.module_enabled(module, update.message.chat.id):
                    try:
                        self.commands[module][cmd](self, args, update)
                    except KeyError:
                        pass
            try:
                self.admin_commands[cmd](self, args, update)
            except KeyError:
                pass

    def reset_jail(self):
        self.user_jail.clear()

    def set_can(self, cmd, chat_id, val=True):
        if chat_id not in self.can:
            self.can[chat_id] = {}

        chat_can = self.can[chat_id]

        chat_can[cmd] = val

    def can_call(self, cmd, chat_id):
        if chat_id not in self.can:
            self.can[chat_id] = {}

        chat_can = self.can[chat_id]

        if cmd not in chat_can:
            chat_can[cmd] = True

        return chat_can[cmd]

    def reset_can(self, cmd):
        for chat in self.can.keys():
            self.can[chat][cmd] = True


if __name__ == '__main__':
    rebot = ReBot()
    rebot.start()
