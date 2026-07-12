# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/FreddieMcHeart/downbeat/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                           |    Stmts |     Miss |   Cover |   Missing |
|----------------------------------------------- | -------: | -------: | ------: | --------: |
| src/downbeat/\_\_init\_\_.py                   |        1 |        0 |    100% |           |
| src/downbeat/cli/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/downbeat/cli/\_\_main\_\_.py               |      118 |        3 |     97% |33-34, 228 |
| src/downbeat/cli/commands/\_\_init\_\_.py      |        0 |        0 |    100% |           |
| src/downbeat/cli/commands/init\_cmd.py         |      293 |       17 |     94% |98, 115-120, 176-177, 252, 264, 268-269, 310-311, 330, 341 |
| src/downbeat/cli/commands/relay\_cmds.py       |      231 |       60 |     74% |20-22, 54-56, 93-95, 101-109, 116-117, 136-137, 146-163, 170-175, 178, 203-210, 247-249, 286, 297, 313-316, 320-321 |
| src/downbeat/core/\_\_init\_\_.py              |        0 |        0 |    100% |           |
| src/downbeat/core/errors.py                    |        7 |        0 |    100% |           |
| src/downbeat/core/groups.py                    |       22 |        0 |    100% |           |
| src/downbeat/core/logging.py                   |       24 |        0 |    100% |           |
| src/downbeat/core/models.py                    |       84 |        0 |    100% |           |
| src/downbeat/core/paths.py                     |       17 |        0 |    100% |           |
| src/downbeat/core/session.py                   |       82 |       30 |     63% |26-27, 77, 94-103, 109-110, 115-116, 131-145, 152 |
| src/downbeat/core/state.py                     |       42 |        9 |     79% |49, 56, 60-65, 69-70 |
| src/downbeat/core/store.py                     |      486 |       51 |     90% |35-37, 52-53, 168, 175, 179, 187, 212-213, 250, 259-260, 286-287, 300-302, 327-329, 356, 412, 419-420, 436, 439, 443-444, 446, 449-450, 516, 519, 523-524, 534, 547, 626-627, 643-644, 675-679, 737, 740, 746-747 |
| src/downbeat/core/watcher.py                   |       87 |       14 |     84% |37, 41-42, 52-53, 89, 93-94, 118-120, 131, 134-136 |
| src/downbeat/skill/\_\_init\_\_.py             |        0 |        0 |    100% |           |
| src/downbeat/tui/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/downbeat/tui/app.py                        |       60 |       22 |     63% |34-38, 44-53, 67-78, 81-82 |
| src/downbeat/tui/messages.py                   |        4 |        0 |    100% |           |
| src/downbeat/tui/screens/\_\_init\_\_.py       |        0 |        0 |    100% |           |
| src/downbeat/tui/screens/broadcast\_status.py  |       20 |       20 |      0% |      2-30 |
| src/downbeat/tui/screens/chat.py               |      204 |       69 |     66% |105, 127-128, 137-138, 141-142, 155, 166-176, 179-181, 191-194, 197-214, 217-220, 223-228, 257, 260-261, 265, 274, 284-294, 301 |
| src/downbeat/tui/screens/help.py               |       12 |        0 |    100% |           |
| src/downbeat/tui/screens/main.py               |      152 |      152 |      0% |     2-216 |
| src/downbeat/tui/screens/message\_detail.py    |      113 |       62 |     45% |46-53, 56, 61-67, 88, 90, 92, 94-95, 101-114, 117-121, 127-132, 137-142, 147-148, 151-152, 155-161, 167-171 |
| src/downbeat/tui/screens/peers.py              |       84 |       32 |     62% |65-66, 78-85, 88, 99-108, 113, 117-126 |
| src/downbeat/tui/screens/quarantine.py         |       73 |       73 |      0% |     2-115 |
| src/downbeat/tui/widgets/\_\_init\_\_.py       |        0 |        0 |    100% |           |
| src/downbeat/tui/widgets/add\_peer\_modal.py   |       56 |        9 |     84% |66, 72-74, 81-84, 88 |
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
| src/downbeat/tui/widgets/peer\_list.py         |       84 |       84 |      0% |     2-115 |
| src/downbeat/tui/widgets/peer\_tabs.py         |       52 |        2 |     96% |    41, 89 |
| src/downbeat/tui/widgets/rebind\_modal.py      |       33 |       33 |      0% |      2-52 |
| src/downbeat/tui/widgets/switch\_acting\_as.py |       33 |        6 |     82% | 39-43, 46 |
| **TOTAL**                                      | **3124** | **1068** | **66%** |           |


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