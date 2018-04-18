def register(rebot):
    commands = rebot.get_module_commands('shop_module')
    commands['listshops'] = cmd_list_shops


def unregister(rebot):
    rebot.del_module_commands('shop_module')


def cmd_list_shops(rebot, args, update):
    pass
