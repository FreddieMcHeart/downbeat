# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/FreddieMcHeart/downbeat/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                           |    Stmts |     Miss |   Cover |   Missing |
|----------------------------------------------- | -------: | -------: | ------: | --------: |
| src/downbeat/\_\_init\_\_.py                   |        1 |        0 |    100% |           |
| src/downbeat/cli/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/downbeat/cli/\_\_main\_\_.py               |      115 |        1 |     99% |       233 |
| src/downbeat/cli/commands/\_\_init\_\_.py      |        0 |        0 |    100% |           |
| src/downbeat/cli/commands/init\_cmd.py         |      293 |       17 |     94% |98, 115-120, 176-177, 252, 264, 268-269, 310-311, 330, 341 |
| src/downbeat/cli/commands/relay\_cmds.py       |      235 |       56 |     76% |102-104, 142-144, 150-158, 165-166, 194-195, 205-222, 229-234, 237, 269, 271, 275, 287, 308, 347-349, 353-356, 360-361 |
| src/downbeat/core/\_\_init\_\_.py              |        0 |        0 |    100% |           |
| src/downbeat/core/errors.py                    |       12 |        0 |    100% |           |
| src/downbeat/core/groups.py                    |       22 |        0 |    100% |           |
| src/downbeat/core/logging.py                   |       27 |        0 |    100% |           |
| src/downbeat/core/models.py                    |      108 |        1 |     99% |        75 |
| src/downbeat/core/notify.py                    |       17 |        0 |    100% |           |
| src/downbeat/core/paths.py                     |       17 |        0 |    100% |           |
| src/downbeat/core/provenance.py                |       61 |        5 |     92% |93-94, 136-138 |
| src/downbeat/core/session.py                   |       83 |       30 |     64% |26-27, 93, 110-119, 125-126, 131-132, 147-161, 168 |
| src/downbeat/core/state.py                     |       57 |        8 |     86% |49, 56, 60-65, 81 |
| src/downbeat/core/store.py                     |      769 |       71 |     91% |52-54, 82-83, 287, 290, 292-293, 388, 444, 485-486, 537-539, 542, 569, 572, 640, 644-645, 663, 667, 675, 779-780, 792-793, 833-835, 867-869, 896, 955, 962-963, 1005, 1008, 1012-1013, 1015, 1018-1019, 1035, 1111, 1116-1118, 1120-1121, 1177, 1180, 1184-1185, 1195, 1208, 1302-1303, 1319-1320, 1351-1355, 1428, 1431, 1437-1438 |
| src/downbeat/core/watcher.py                   |       87 |       12 |     86% |37, 41-42, 52-53, 89, 93-94, 131, 134-136 |
| src/downbeat/skill/\_\_init\_\_.py             |        0 |        0 |    100% |           |
| src/downbeat/tui/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/downbeat/tui/app.py                        |      101 |       27 |     73% |69-73, 79-88, 99-100, 117, 124-135, 138-139, 149-150 |
| src/downbeat/tui/messages.py                   |        4 |        0 |    100% |           |
| src/downbeat/tui/screens/\_\_init\_\_.py       |        0 |        0 |    100% |           |
| src/downbeat/tui/screens/broadcast\_status.py  |       20 |       20 |      0% |      2-30 |
| src/downbeat/tui/screens/chat.py               |      206 |       49 |     76% |137-138, 147-148, 151-152, 165, 176-186, 201-204, 210, 226-229, 232-237, 266, 269-270, 274, 283, 293-303, 310 |
| src/downbeat/tui/screens/help.py               |       12 |        0 |    100% |           |
| src/downbeat/tui/screens/message\_detail.py    |      111 |       44 |     60% |61-67, 90, 92, 94-95, 101-114, 117-121, 127-132, 137-142, 147-148, 151-152, 161, 170 |
| src/downbeat/tui/screens/peers.py              |       85 |       32 |     62% |74-75, 90-97, 100, 111-120, 125, 129-138 |
| src/downbeat/tui/screens/quarantine.py         |       73 |       73 |      0% |     2-115 |
| src/downbeat/tui/widgets/\_\_init\_\_.py       |        0 |        0 |    100% |           |
| src/downbeat/tui/widgets/add\_peer\_modal.py   |       56 |        9 |     84% |66, 72-74, 81-85, 89 |
| src/downbeat/tui/widgets/chat\_composer.py     |       64 |       31 |     52% |54-57, 59-62, 68, 73-77, 80-101 |
| src/downbeat/tui/widgets/chat\_stream.py       |      179 |       24 |     87% |26-27, 79-80, 177, 184, 250, 261, 285, 291, 299, 302, 307-308, 311-312, 316, 319, 322-324, 329-330, 337 |
| src/downbeat/tui/widgets/clipboard.py          |       25 |       20 |     20% |     17-41 |
| src/downbeat/tui/widgets/composer.py           |       64 |       64 |      0% |      2-87 |
| src/downbeat/tui/widgets/confirm.py            |       20 |        1 |     95% |        35 |
| src/downbeat/tui/widgets/edit\_modal.py        |       34 |       20 |     41% |22-25, 28-35, 38-46, 49 |
| src/downbeat/tui/widgets/find\_message.py      |       52 |        3 |     94% | 77-78, 83 |
| src/downbeat/tui/widgets/inbox\_list.py        |       47 |       47 |      0% |      2-61 |
| src/downbeat/tui/widgets/log\_viewer.py        |       48 |       14 |     71% |     47-61 |
| src/downbeat/tui/widgets/message\_view.py      |       46 |       46 |      0% |      2-62 |
| src/downbeat/tui/widgets/peer\_admin.py        |       88 |       12 |     86% |50, 81-87, 92-93, 103-104, 123 |
| src/downbeat/tui/widgets/peer\_tabs.py         |       54 |        2 |     96% |    41, 85 |
| src/downbeat/tui/widgets/rebind\_modal.py      |       33 |       33 |      0% |      2-52 |
| src/downbeat/tui/widgets/switch\_acting\_as.py |       70 |        6 |     91% | 92-96, 99 |
| **TOTAL**                                      | **3396** |  **778** | **77%** |           |


## Setup coverage badge

Below are examples of the badges you can use in your main branch `README` file.

### Direct image

[![Coverage badge](https://raw.githubusercontent.com/FreddieMcHeart/downbeat/python-coverage-comment-action-data/badge.svg)](https://htmlpreview.github.io/?https://github.com/FreddieMcHeart/downbeat/blob/python-coverage-comment-action-data/htmlcov/index.html)

This is the one to use if your repository is private or if you don't want to customize anything.

### [Shields.io](https://shields.io) Json Endpoint

[![Coverage badge](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/FreddieMcHeart/downbeat/python-coverage-comment-action-data/endpoint.json)](https://htmlpreview.github.io/?https://github.com/FreddieMcHeart/downbeat/blob/python-coverage-comment-action-data/htmlcov/index.html)

Using this one will allow you to [customize](https://shields.io/endpoint) the look of your badge.
It won't work with private repositories. It won't be refreshed more than once per five minutes.

### [Shields.io](https://shields.io) Dynamic Badge

[![Coverage badge](https://img.shields.io/badge/dynamic/json?color=brightgreen&label=coverage&query=%24.message&url=https%3A%2F%2Fraw.githubusercontent.com%2FFreddieMcHeart%2Fdownbeat%2Fpython-coverage-comment-action-data%2Fendpoint.json)](https://htmlpreview.github.io/?https://github.com/FreddieMcHeart/downbeat/blob/python-coverage-comment-action-data/htmlcov/index.html)

This one will always be the same color. It won't work for private repos. I'm not even sure why we included it.

## What is that?

This branch is part of the
[python-coverage-comment-action](https://github.com/marketplace/actions/python-coverage-comment)
GitHub Action. All the files in this branch are automatically generated and may be
overwritten at any moment.