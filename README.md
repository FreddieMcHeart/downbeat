# Repository Coverage

[Full report](https://htmlpreview.github.io/?https://github.com/FreddieMcHeart/downbeat/blob/python-coverage-comment-action-data/htmlcov/index.html)

| Name                                           |    Stmts |     Miss |   Cover |   Missing |
|----------------------------------------------- | -------: | -------: | ------: | --------: |
| src/downbeat/\_\_init\_\_.py                   |        1 |        0 |    100% |           |
| src/downbeat/cli/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/downbeat/cli/\_\_main\_\_.py               |      111 |        3 |     97% |33-34, 214 |
| src/downbeat/cli/commands/\_\_init\_\_.py      |        0 |        0 |    100% |           |
| src/downbeat/cli/commands/init\_cmd.py         |      293 |       17 |     94% |98, 115-120, 176-177, 252, 264, 268-269, 310-311, 330, 341 |
| src/downbeat/cli/commands/relay\_cmds.py       |      193 |       58 |     70% |17-19, 51-53, 90-92, 98-106, 113-114, 133-134, 143-160, 167-172, 175, 200-207, 244-246, 250-253, 257-258 |
| src/downbeat/core/\_\_init\_\_.py              |        0 |        0 |    100% |           |
| src/downbeat/core/errors.py                    |        8 |        0 |    100% |           |
| src/downbeat/core/groups.py                    |       22 |        0 |    100% |           |
| src/downbeat/core/logging.py                   |       24 |        0 |    100% |           |
| src/downbeat/core/models.py                    |       84 |        0 |    100% |           |
| src/downbeat/core/notify.py                    |       17 |        0 |    100% |           |
| src/downbeat/core/paths.py                     |       17 |        0 |    100% |           |
| src/downbeat/core/session.py                   |       82 |       30 |     63% |26-27, 77, 94-103, 109-110, 115-116, 131-145, 152 |
| src/downbeat/core/state.py                     |       57 |        8 |     86% |49, 56, 60-65, 81 |
| src/downbeat/core/store.py                     |      520 |       55 |     89% |36-38, 53-54, 172, 221, 236, 240-241, 259, 263, 271, 296-297, 334, 343-344, 370-371, 384-386, 411-413, 440, 496, 503-504, 520, 523, 527-528, 530, 533-534, 600, 603, 607-608, 618, 631, 710-711, 727-728, 759-763, 821, 824, 830-831 |
| src/downbeat/core/watcher.py                   |       87 |       12 |     86% |37, 41-42, 52-53, 89, 93-94, 131, 134-136 |
| src/downbeat/skill/\_\_init\_\_.py             |        0 |        0 |    100% |           |
| src/downbeat/tui/\_\_init\_\_.py               |        0 |        0 |    100% |           |
| src/downbeat/tui/app.py                        |       94 |       27 |     71% |37-41, 47-56, 67-68, 85, 92-103, 106-107, 117-118 |
| src/downbeat/tui/messages.py                   |        4 |        0 |    100% |           |
| src/downbeat/tui/screens/\_\_init\_\_.py       |        0 |        0 |    100% |           |
| src/downbeat/tui/screens/broadcast\_status.py  |       20 |       20 |      0% |      2-30 |
| src/downbeat/tui/screens/chat.py               |      203 |       53 |     74% |105, 127-128, 137-138, 141-142, 155, 166-176, 179-181, 191-194, 200, 216-219, 222-227, 256, 259-260, 264, 273, 283-293, 300 |
| src/downbeat/tui/screens/help.py               |       12 |        0 |    100% |           |
| src/downbeat/tui/screens/message\_detail.py    |      113 |       62 |     45% |46-53, 56, 61-67, 88, 90, 92, 94-95, 101-114, 117-121, 127-132, 137-142, 147-148, 151-152, 155-161, 167-171 |
| src/downbeat/tui/screens/peers.py              |       85 |       32 |     62% |74-75, 90-97, 100, 111-120, 125, 129-138 |
| src/downbeat/tui/screens/quarantine.py         |       73 |       73 |      0% |     2-115 |
| src/downbeat/tui/widgets/\_\_init\_\_.py       |        0 |        0 |    100% |           |
| src/downbeat/tui/widgets/add\_peer\_modal.py   |       56 |        9 |     84% |66, 72-74, 81-84, 88 |
| src/downbeat/tui/widgets/chat\_composer.py     |       64 |       31 |     52% |54-57, 59-62, 68, 73-77, 80-101 |
| src/downbeat/tui/widgets/chat\_stream.py       |      180 |       26 |     86% |26-27, 70-71, 116, 146, 169, 176, 242, 248, 272, 278, 286, 289, 294-295, 298-299, 303, 306, 309-311, 316-317, 324 |
| src/downbeat/tui/widgets/clipboard.py          |       25 |       20 |     20% |     17-41 |
| src/downbeat/tui/widgets/composer.py           |       64 |       64 |      0% |      2-87 |
| src/downbeat/tui/widgets/confirm.py            |       20 |        1 |     95% |        35 |
| src/downbeat/tui/widgets/edit\_modal.py        |       34 |       20 |     41% |22-25, 28-35, 38-46, 49 |
| src/downbeat/tui/widgets/find\_message.py      |       39 |        3 |     92% | 51-52, 57 |
| src/downbeat/tui/widgets/inbox\_list.py        |       47 |       47 |      0% |      2-61 |
| src/downbeat/tui/widgets/log\_viewer.py        |       48 |       14 |     71% |     47-61 |
| src/downbeat/tui/widgets/message\_view.py      |       46 |       46 |      0% |      2-62 |
| src/downbeat/tui/widgets/peer\_admin.py        |       83 |       12 |     86% |38, 69-75, 80-81, 91-92, 111 |
| src/downbeat/tui/widgets/peer\_tabs.py         |       52 |        2 |     96% |    41, 89 |
| src/downbeat/tui/widgets/rebind\_modal.py      |       33 |       33 |      0% |      2-52 |
| src/downbeat/tui/widgets/switch\_acting\_as.py |       33 |        6 |     82% | 39-43, 46 |
| **TOTAL**                                      | **2944** |  **784** | **73%** |           |


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