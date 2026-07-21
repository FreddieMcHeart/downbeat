# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/FreddieMcHeart/downbeat/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                           |    Stmts |     Miss |   Cover |   Missing |
|----------------------------------------------- | -------: | -------: | ------: | --------: |
| src/downbeat/\_\_init\_\_.py                   |        1 |        0 |    100% |           |
| src/downbeat/cli/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/downbeat/cli/\_\_main\_\_.py               |      109 |        1 |     99% |       219 |
| src/downbeat/cli/commands/\_\_init\_\_.py      |        0 |        0 |    100% |           |
| src/downbeat/cli/commands/init\_cmd.py         |      293 |       17 |     94% |98, 115-120, 176-177, 252, 264, 268-269, 310-311, 330, 341 |
| src/downbeat/cli/commands/relay\_cmds.py       |      205 |       59 |     71% |56-58, 95-97, 103-111, 118-119, 138-139, 148-165, 172-177, 180, 212, 214, 218, 224-231, 268-270, 274-277, 281-282 |
| src/downbeat/core/\_\_init\_\_.py              |        0 |        0 |    100% |           |
| src/downbeat/core/errors.py                    |        8 |        0 |    100% |           |
| src/downbeat/core/groups.py                    |       22 |        0 |    100% |           |
| src/downbeat/core/logging.py                   |       27 |        0 |    100% |           |
| src/downbeat/core/models.py                    |       84 |        0 |    100% |           |
| src/downbeat/core/notify.py                    |       17 |        0 |    100% |           |
| src/downbeat/core/paths.py                     |       17 |        0 |    100% |           |
| src/downbeat/core/provenance.py                |       61 |        5 |     92% |93-94, 136-138 |
| src/downbeat/core/session.py                   |       82 |       30 |     63% |26-27, 77, 94-103, 109-110, 115-116, 131-145, 152 |
| src/downbeat/core/state.py                     |       57 |        8 |     86% |49, 56, 60-65, 81 |
| src/downbeat/core/store.py                     |      537 |       54 |     90% |36-38, 53-54, 172, 228, 247, 262, 266-267, 285, 289, 297, 336-337, 374, 383-384, 424-426, 458-460, 487, 546, 553-554, 570, 573, 577-578, 580, 583-584, 650, 653, 657-658, 668, 681, 760-761, 777-778, 809-813, 871, 874, 880-881 |
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
| src/downbeat/tui/widgets/add\_peer\_modal.py   |       56 |        9 |     84% |66, 72-74, 81-84, 88 |
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
| src/downbeat/tui/widgets/peer\_tabs.py         |       54 |        2 |     96% |    41, 89 |
| src/downbeat/tui/widgets/rebind\_modal.py      |       33 |       33 |      0% |      2-52 |
| src/downbeat/tui/widgets/switch\_acting\_as.py |       33 |        6 |     82% | 39-43, 46 |
| **TOTAL**                                      | **3062** |  **763** | **75%** |           |


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