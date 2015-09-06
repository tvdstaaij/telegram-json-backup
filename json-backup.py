import tgl
import json
import re
import os
import shutil
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

# Wait time after downloading a media file
MEDIA_DELAY = 0.1

# Max size of the backlog per dialog (0 for unlimited)
HISTORY_LIMIT = 0

# Whether to download media files
# Documents include stickers, video and audio (this is a tg issue)
DOWNLOAD_PHOTOS = False
DOWNLOAD_DOCUMENTS = False

# Directory for the backup file(s)
BACKUP_DIR = './json'

missing_date_count = 0
peer_queue = list()
outfile = None
mediadir = None

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
    global peer_queue, outfile, missing_date_count, mediadir
    if missing_date_count > 0:
        print('Warning: %d messages were missing a date and are '
              'probably not backed up correctly' % missing_date_count)
    missing_date_count = 0
    if outfile:
        outfile.close()
        outfile = None
    if not peer_queue:
        print('All backups have been completed')
        return False
    peer = peer_queue.pop(0)
    filename = re.sub(r'[^a-zA-Z0-9\-.,;]', '_', peer.name)
    path = BACKUP_DIR + '/' + filename + '.jsonl'
    print('Backing up %s to %s' % (peer.name, path))
    os.makedirs(BACKUP_DIR, exist_ok=True)
    if DOWNLOAD_PHOTOS or DOWNLOAD_DOCUMENTS:
        mediadir = filename + '_files'
        os.makedirs(BACKUP_DIR + '/' + mediadir, exist_ok=True)
    outfile = open(path, 'w')
    if HISTORY_LIMIT > 0:
        chunk_size = min([HISTORY_CHUNK_SIZE, HISTORY_LIMIT])
    else:
        chunk_size = HISTORY_CHUNK_SIZE
    cb = partial(history_cb, chunk_size, 0, peer)
    tgl.get_history(peer, 0, chunk_size, cb)
    return True

def history_cb(chunk_count, total_count, peer, success, msgs):
    global missing_date_count
    assert success
    next_total = total_count + chunk_count
    dump_calls = []
    print('Backing up %s [messages %d-%d]'
        % (peer.name, total_count, next_total - 1))
    for i in range(0, len(msgs)):
        msg = msgs[i]
        if not msg:
            continue
        if not msg.date:
            missing_date_count += 1
        msg_dict = make_msg_dict(msg)
        if not msg_dict:
            continue
        download_call = None
        media = msg.media
        if media:
            if DOWNLOAD_PHOTOS and media['type'] == 'photo':
                download_call = msg.load_photo
            if DOWNLOAD_DOCUMENTS and media['type'] == 'document':
                download_call = msg.load_document
            # The following two do not seem to occur, but just in case this is fixed in tg
            if DOWNLOAD_DOCUMENTS and media['type'] == 'video':
                download_call = msg.load_video
            if DOWNLOAD_DOCUMENTS and media['type'] == 'audio':
                download_call = msg.load_audio
        # Don't directly process the message, but store the handler invocation
        # so that they can be chained later
        dump_calls.insert(0, partial(dump_message, msg_dict, download_call))
    # Determine the action to take after all messages in this chunk are done
    if (len(msgs) == chunk_count and
        (next_total < HISTORY_LIMIT or HISTORY_LIMIT == 0)):
        if HISTORY_LIMIT > 0 and next_total + chunk_count > HISTORY_LIMIT:
            chunk_count = HISTORY_LIMIT - next_total
        cb = partial(history_cb, chunk_count, next_total, peer)
        next_history_action = partial(tgl.get_history, peer, next_total, chunk_count, cb)
    else:
        next_history_action = backup_next
    # Build the call chain: every message handler calls the next,
    # the last one (= the first in the list) calls the next chunk request
    for i in range(0, len(dump_calls)):
        if i == 0:
            next_call = next_history_action
            sleep_before_next = REQUEST_DELAY
        else:
            next_call = dump_calls[i-1]
            sleep_before_next = None
        dump_calls[i] = partial(dump_calls[i], next_call, sleep_before_next, None, None)
    if dump_calls:
        # Kickstart the call chain by invoking the last function in the list
        dump_calls[-1]()
    else:
        # Just in case the entire chunk was discarded (unlikely)
        next_history_action()
    return True

def dump_message(msg_dict, download_call, next_call, sleep_before_next, file_success, file_path):
    global outfile, mediadir
    if download_call:
        # Need to download a file first, defer processing this message
        # until it has been downloaded by using this function as callback
        cb = partial(dump_message, msg_dict, None, next_call, MEDIA_DELAY)
        download_call(cb)
        return
    elif file_success and msg_dict['media']:
        # Just downloaded a file, move it and add the filename to the msg data
        filename = os.path.basename(file_path)
        destination = BACKUP_DIR + '/' + mediadir + '/' + filename

        # tg seems to produce some weird file extensions, attempt to fix a few
        destination = destination.replace('.oga', '.ogg')
        destination = destination.replace('.mpga', '.mp3')

        shutil.move(file_path, destination)
        msg_dict['media']['file'] = mediadir + '/' + os.path.basename(destination)
    elif file_success is not None:
        print('Failed to save media file for message '
              '#%d (success=%s)' % (msg_dict['id'], file_success))
        if msg_dict['media']:
            msg_dict['media']['file'] = None
    json_str = json.dumps(msg_dict)
    outfile.write(json_str)
    outfile.write("\n")
    if sleep_before_next:
        sleep(sleep_before_next)
    next_call()

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
