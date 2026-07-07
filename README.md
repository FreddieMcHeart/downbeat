# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/FreddieMcHeart/downbeat/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                           |    Stmts |     Miss |   Cover |   Missing |
|----------------------------------------------- | -------: | -------: | ------: | --------: |
| src/downbeat/\_\_init\_\_.py                   |        1 |        0 |    100% |           |
| src/downbeat/cli/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/downbeat/cli/\_\_main\_\_.py               |      112 |        3 |     97% |33-34, 211 |
| src/downbeat/cli/commands/\_\_init\_\_.py      |        0 |        0 |    100% |           |
| src/downbeat/cli/commands/init\_cmd.py         |      228 |       15 |     93% |96, 113-118, 196, 200-201, 220, 238-239, 258, 269 |
| src/downbeat/cli/commands/relay\_cmds.py       |      215 |       59 |     73% |20-22, 54-56, 66, 87-89, 95-103, 110-111, 122-123, 131-148, 155-160, 163, 188-195, 232-234, 271, 282, 298-299, 303-304 |
| src/downbeat/core/\_\_init\_\_.py              |        0 |        0 |    100% |           |
| src/downbeat/core/errors.py                    |        5 |        0 |    100% |           |
| src/downbeat/core/groups.py                    |       22 |        0 |    100% |           |
| src/downbeat/core/logging.py                   |       24 |        0 |    100% |           |
| src/downbeat/core/models.py                    |       83 |        0 |    100% |           |
| src/downbeat/core/paths.py                     |       17 |        0 |    100% |           |
| src/downbeat/core/session.py                   |       82 |       41 |     50% |19-31, 77, 94-103, 109-110, 115-116, 131-145, 150-153 |
| src/downbeat/core/state.py                     |       42 |        9 |     79% |49, 56, 60-65, 69-70 |
| src/downbeat/core/store.py                     |      457 |       51 |     89% |28-30, 45-46, 102, 109, 113, 121, 146-147, 184, 193-194, 220-221, 234-236, 261-263, 290, 346, 353-354, 370, 373, 377-378, 380, 383-384, 450, 453, 457-458, 468, 481, 560-561, 577-578, 609-613, 671, 674, 680-681 |
| src/downbeat/core/watcher.py                   |       87 |       12 |     86% |37, 41-42, 52-53, 89, 93-94, 131, 134-136 |
| src/downbeat/skill/\_\_init\_\_.py             |        0 |        0 |    100% |           |
| src/downbeat/tui/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/downbeat/tui/app.py                        |       60 |       22 |     63% |34-38, 44-53, 67-78, 81-82 |
| src/downbeat/tui/messages.py                   |        4 |        0 |    100% |           |
| src/downbeat/tui/screens/\_\_init\_\_.py       |        0 |        0 |    100% |           |
| src/downbeat/tui/screens/broadcast\_status.py  |       20 |       20 |      0% |      2-30 |
| src/downbeat/tui/screens/chat.py               |      213 |       69 |     68% |111, 133-134, 143-144, 147-148, 161, 172-182, 185-187, 197-200, 203-220, 223-226, 229-234, 263, 266-267, 271, 280, 290-300, 307 |
| src/downbeat/tui/screens/help.py               |       12 |        0 |    100% |           |
| src/downbeat/tui/screens/main.py               |      151 |      151 |      0% |     2-215 |
| src/downbeat/tui/screens/message\_detail.py    |      113 |       62 |     45% |46-53, 56, 61-67, 88, 90, 92, 94-95, 101-114, 117-121, 127-132, 137-142, 147-148, 151-152, 155-161, 167-171 |
| src/downbeat/tui/screens/peers.py              |       84 |       32 |     62% |64-65, 77-84, 87, 98-107, 112, 116-125 |
| src/downbeat/tui/screens/quarantine.py         |       73 |       73 |      0% |     2-115 |
| src/downbeat/tui/widgets/\_\_init\_\_.py       |        0 |        0 |    100% |           |
| src/downbeat/tui/widgets/add\_peer\_modal.py   |       41 |        5 |     88% |43, 49-51, 59 |
| src/downbeat/tui/widgets/chat\_composer.py     |       64 |       31 |     52% |54-57, 59-62, 68, 73-77, 80-101 |
| src/downbeat/tui/widgets/chat\_stream.py       |      180 |       26 |     86% |26-27, 70-71, 116, 146, 169, 176, 242, 248, 272, 278, 286, 289, 294-295, 298-299, 303, 306, 309-311, 316-317, 324 |
| src/downbeat/tui/widgets/clipboard.py          |       25 |       20 |     20% |     17-41 |
| src/downbeat/tui/widgets/composer.py           |       64 |       64 |      0% |      2-87 |
| src/downbeat/tui/widgets/confirm.py            |       20 |        1 |     95% |        35 |
| src/downbeat/tui/widgets/edit\_modal.py        |       34 |       20 |     41% |22-25, 28-35, 38-46, 49 |
| src/downbeat/tui/widgets/find\_message.py      |       39 |       39 |      0% |      2-57 |
| src/downbeat/tui/widgets/inbox\_list.py        |       47 |       47 |      0% |      2-61 |
| src/downbeat/tui/widgets/log\_viewer.py        |       48 |       14 |     71% |     47-61 |
| src/downbeat/tui/widgets/message\_view.py      |       46 |       46 |      0% |      2-62 |
| src/downbeat/tui/widgets/peer\_admin.py        |       83 |       12 |     86% |38, 69-75, 80-81, 91-92, 111 |
| src/downbeat/tui/widgets/peer\_list.py         |       93 |       93 |      0% |     2-130 |
| src/downbeat/tui/widgets/peer\_tabs.py         |       51 |        2 |     96% |    39, 84 |
| src/downbeat/tui/widgets/rebind\_modal.py      |       33 |       33 |      0% |      2-52 |
| src/downbeat/tui/widgets/switch\_acting\_as.py |       33 |        6 |     82% | 39-43, 46 |
| **TOTAL**                                      | **3006** | **1078** | **64%** |           |


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