import tgl
import json
import re
import os
from functools import partial
from time import sleep

# List of (partial) dialog names to backup
# To backup everything: TARGET_DIALOGS = set()
TARGET_DIALOGS = {'MyChat'}

# Amount of messages to fetch in one partial request
# Changing this may cause problems (see readme)
HISTORY_CHUNK_SIZE = 100

# Wait time between requesting chunks in seconds
# Decreasing this may cause problems (see readme)
REQUEST_DELAY = 1 

# Max size of the backlog per dialog (0 for unlimited)
HISTORY_LIMIT = 0

# Directory for the backup file(s)
BACKUP_DIR = './json'

peer_queue = list()
outfile = None

# The below three functions are a workaround for
# https://github.com/vysheng/tg/issues/664
def props(obj):
    realprops = dict((k, getattr(obj, k)) for k in dir(obj) if not k.startswith('__'))
    return {k: v for k, v in realprops.items() if not callable(v)}

def make_peer_dict(peer):
    if not peer:
        return None
    peer_dict = {}
    copy_keys = {'id', 'type_name', 'name'}
    if peer.type == tgl.PEER_ENCR_CHAT:
        copy_keys |= {'user_id'}
    if peer.type == tgl.PEER_USER:
        copy_keys |= {'phone', 'username', 'first_name', 'last_name'}
    for key in copy_keys:
        peer_dict[key] = getattr(peer, key) if hasattr(peer, key) else None
    return peer_dict

def make_msg_dict(msg):
    if not msg:
        return None
    msg_dict = props(msg)
    for peer_key in {'src', 'dest', 'fwd_src'}:
        if msg_dict[peer_key]:
            peer = msg_dict[peer_key]
            if peer.type_name != 'user' or peer.first_name:
                msg_dict[peer_key] = make_peer_dict(peer)
            else:
                msg_dict[peer_key] = None
    msg_dict.pop('reply', None)
    for date_key in {'date', 'fwd_date'}:
        if msg_dict[date_key]:
            msg_dict[date_key] = msg_dict[date_key].isoformat()
    msg_dict['action'] = get_action_name(msg_dict['action'])
    return msg_dict

def get_action_name(action):
    enums = props(tgl)
    for enum, value in enums.items():
        if enum.startswith('ACTION_') and action == value:
            return enum
    return None

def backup_next():
    global peer_queue, outfile
    if outfile:
        outfile.close()
        outfile = None
    if not peer_queue:
        print('All backups have been completed')
        return False
    peer = peer_queue.pop(0)
    filename = re.sub(r'[^a-zA-Z0-9\-.,;]', '_', peer.name)
    path = BACKUP_DIR + '/' + filename + '.json'
    print('Backing up %s to %s' % (peer.name, path))
    os.makedirs(BACKUP_DIR, exist_ok=True)
    outfile = open(path, 'w')
    cb = partial(history_cb, HISTORY_CHUNK_SIZE, 0, peer)
    tgl.get_history(peer, 0, HISTORY_CHUNK_SIZE, cb)
    return True

def history_cb(chunk_count, total_count, peer, success, msgs):
    global outfile
    assert success
    next_total = total_count + chunk_count
    print('Backing up %s [messages %d-%d]'
        % (peer.name, total_count, next_total - 1))
    for i in range(0, len(msgs)):
        msg = msgs[i]
        if not msg:
            continue
        msg_dict = make_msg_dict(msg)
        if not msg_dict:
            continue
        json_obj = json.dumps(msg_dict)
        outfile.write(json_obj)
        outfile.write("\n")
    sleep(REQUEST_DELAY)
    if (len(msgs) == chunk_count and
        (next_total < HISTORY_LIMIT or HISTORY_LIMIT == 0)):
        cb = partial(history_cb, chunk_count, next_total, peer)
        tgl.get_history(peer, total_count, chunk_count, cb)
    else:
        backup_next()
    return True

def dialog_list_cb(success, dialog_list):
    global peer_queue
    assert success
    print('Selecting dialogs from list')
    for i in range(0, len(dialog_list)):
        peer = dialog_list[i]['peer']
        if peer.type_name == 'user' and not peer.first_name:
            continue
        selected = len(TARGET_DIALOGS) == 0
        for dialog_keyword in TARGET_DIALOGS:
            if dialog_keyword.replace(' ', '_') in peer.name:
                selected = True
                break
        if selected:
            peer_queue.append(peer)
    queue_length = len(peer_queue)
    if queue_length > 0:
        print('Proceeding to backup %d dialog(s)' % queue_length)
        backup_next()
    else:
        print('No dialogs selected for backup')
    return True

def on_binlog_replay_end():
    print('Fetching dialog list')
    tgl.get_dialog_list(dialog_list_cb)
    return True

def on_get_difference_end():
    return True

def on_our_id(our_id):
    return True

def on_msg_receive(msg):
    return True

def on_secret_chat_update(peer, types):
    return True

def on_user_update(peer, what_changed):
    return True

def on_chat_update(peer, what_changed):
    return True

tgl.set_on_binlog_replay_end(on_binlog_replay_end)
tgl.set_on_get_difference_end(on_get_difference_end)
tgl.set_on_our_id(on_our_id)
tgl.set_on_msg_receive(on_msg_receive)
tgl.set_on_secret_chat_update(on_secret_chat_update)
tgl.set_on_user_update(on_user_update)
tgl.set_on_chat_update(on_chat_update)
