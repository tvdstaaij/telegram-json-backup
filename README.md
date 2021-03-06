# telegram-json-backup

***Telegram-json-backup has been deprecated in favor of [telegram-history-dump](https://github.com/tvdstaaij/telegram-history-dump). This script may still work, but note that the required Python support in telegram-cli is broken as of January 2016.***

## Summary

Python script for telegram-cli that creates [JSON Lines](http://jsonlines.org) compliant dumps of Telegram message backlogs.

Support for downloading media files is available on the experimental branch (`git checkout experimental`). It changes the backup process significantly and may be unstable.

## Usage

1. Edit the script configuration at the top of [json-backup.py](json-backup.py)
2. Run telegram-cli with the script: `telegram-cli -Z json-backup.py`

The output is one file per dialog (can be either user or group chat) with newline separated JSON objects representing messages/events.
See the message and peer attribute descriptions in [the telegram-cli Python readme](https://github.com/vysheng/tg/blob/master/README-PY.md) for more information about the properties.

Because the message backlogs are received in chunks from newest to oldest, the arrival of new messages while the backup is running may break index consistency and therefore cause duplicate or missing messages in the resulting dump. I recommend running this at a time when it's unlikely that anyone will send a message to your backup target(s). You could even schedule the backup in the middle of the night with `at` or `crontab`.

## Limitations

The script supports an unlimited backlog size and number of chats, but throttling is necessary to dump large (3000+ messages) backlogs. Unfortunately, the limit is not exactly known and exceeding it will just cause the callback to never arrive, effectively halting the backup operation without notice ([tg#717](https://github.com/vysheng/tg/issues/717)). So if the script suddenly stops making progress this is probably the cause; restart the script after adjusting the parameters.

## Dependencies

* Python 3 (make sure `libpython3` is installed as well as the runtime before building tg)
* [telegram-cli](https://github.com/vysheng/tg) built with Python support
