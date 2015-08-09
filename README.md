# telegram-json-backup

Python script for telegram-cli that creates JSON dumps of Telegram message backlogs.

## Usage

1. Edit the script configuration at the top of [json-backup.py](json-backup.py)
2. Run telegram-cli with the script: `telegram-cli -k path/to/server.pub -Z json-backup.py`

The output is one file per dialog (can be either user or group chat) with newline separated JSON objects representing messages/events.
See the message and peer attribute descriptions in [the telegram-cli Python readme](https://github.com/vysheng/tg/blob/master/README-PY.md) for more information about the properties.

## Dependencies

* Python 3
* [telegram-cli](https://github.com/vysheng/tg)
