# telegram-json-backup

Python script for telegram-cli that creates [JSON Lines](http://jsonlines.org) compliant dumps of Telegram message backlogs.

## Changelog
September 5th, 2015:

* Fix bug that produced duplicate JSON objects for the first chunk of messages in a dialog
* Conform to JSON Lines recommendation of saving files as `.jsonl`

September 4th, 2015:

* Prevent tgl crash when fetching dialog list containing chats with deleted user accounts
* Prevent tgl crash when backing up group chat with messages from deleted user accounts

## Usage

1. Edit the script configuration at the top of [json-backup.py](json-backup.py)
2. Run telegram-cli with the script: `telegram-cli -Z json-backup.py`

The output is one file per dialog (can be either user or group chat) with newline separated JSON objects representing messages/events.
See the message and peer attribute descriptions in [the telegram-cli Python readme](https://github.com/vysheng/tg/blob/master/README-PY.md) for more information about the properties.

## Limitations

The script supports an unlimited backlog size and number of chats, but throttling is necessary to dump large (3000+ messages) backlogs. Unfortunately, the limit is not exactly known and exceeding it will just cause the callback to never arrive, effectively halting the backup operation without notice ([tg#717](https://github.com/vysheng/tg/issues/717)). So if the script suddenly stops making progress this is probably the cause; restart the script after adjusting the parameters.

Media files are not downloaded. Such a feature may be added in a future version.

## Dependencies

* Python 3 (make sure `libpython3` is installed as well as the runtime before building tg)
* [telegram-cli](https://github.com/vysheng/tg)
