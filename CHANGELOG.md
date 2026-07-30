# CHANGELOG

<!-- version list -->

## v0.14.8 (2026-07-30)

### Bug Fixes

- Stop treating a history hit as licence to take a peer's identity
  ([#91](https://github.com/FreddieMcHeart/downbeat/pull/91),
  [`5656fae`](https://github.com/FreddieMcHeart/downbeat/commit/5656fae0b10438cf3b40902ddf53ef4a955ddca0))


## v0.14.7 (2026-07-30)

### Bug Fixes

- Restore changelog generation, silently dead since v0.3.0
  ([#87](https://github.com/FreddieMcHeart/downbeat/pull/87),
  [`582fd36`](https://github.com/FreddieMcHeart/downbeat/commit/582fd36e67f209095bea282b9b498ba3ee1b8024))

### Documentation

- Put the missing CLI message reader on the map
  ([#86](https://github.com/FreddieMcHeart/downbeat/pull/86),
  [`77bc160`](https://github.com/FreddieMcHeart/downbeat/commit/77bc1607df272af1a819cfe1510ad031f874ff0b))

- Refresh the roadmap for v0.14.6 ([#83](https://github.com/FreddieMcHeart/downbeat/pull/83),
  [`88acdcf`](https://github.com/FreddieMcHeart/downbeat/commit/88acdcfd2b7bb0fa2b7eecb02533404435ba5b37))


## v0.14.6 (2026-07-29)

### Bug Fixes

- Say at resume that a relay identity is stale, not at first send
  ([#82](https://github.com/FreddieMcHeart/downbeat/pull/82),
  [`7b760c9`](https://github.com/FreddieMcHeart/downbeat/commit/7b760c9bf5ca748bb19a8eb4f55f80e11bb7538f))

## v0.14.5 (2026-07-29)

### Bug Fixes

- Identify a background session, whose comm is a title not a path
  ([#81](https://github.com/FreddieMcHeart/downbeat/pull/81),
  [`7814aea`](https://github.com/FreddieMcHeart/downbeat/commit/7814aeaf4231a8487ef723d350866535b27e97cf))

### Documentation

- Refresh the roadmap for v0.14.4 ([#80](https://github.com/FreddieMcHeart/downbeat/pull/80),
  [`b7aba12`](https://github.com/FreddieMcHeart/downbeat/commit/b7aba122e81c3c7d82382d3f77c946a07785da37))

## v0.14.4 (2026-07-29)

### Bug Fixes

- Self-heal peer identity when session lineage is provable
  ([#77](https://github.com/FreddieMcHeart/downbeat/pull/77),
  [`cd33b2e`](https://github.com/FreddieMcHeart/downbeat/commit/cd33b2ee08751ef669b25e892456a480ead84d7f))

## v0.14.3 (2026-07-29)

### Bug Fixes

- Make last_seen a liveness signal, and lock the write it made hot
  ([#74](https://github.com/FreddieMcHeart/downbeat/pull/74),
  [`38a17e0`](https://github.com/FreddieMcHeart/downbeat/commit/38a17e0531f469efc36153f1d2b9319d0da2fd74))

## v0.14.2 (2026-07-29)

### Bug Fixes

- Refuse to silently re-home a peer on a name collision
  ([#76](https://github.com/FreddieMcHeart/downbeat/pull/76),
  [`e410d8c`](https://github.com/FreddieMcHeart/downbeat/commit/e410d8cfa975cec6220fdea98f66216276aae025))

### Documentation

- Correct what kind-aware reconcile covers
  ([#67](https://github.com/FreddieMcHeart/downbeat/pull/67),
  [`f061f2b`](https://github.com/FreddieMcHeart/downbeat/commit/f061f2b37c0c50a4f877734b77a7212fdc663ee3))

- Refresh the roadmap for v0.14.1 ([#69](https://github.com/FreddieMcHeart/downbeat/pull/69),
  [`54df1d8`](https://github.com/FreddieMcHeart/downbeat/commit/54df1d80091e51f23197b1408307368f86b85929))

- The idle-peer badge understates as well as overstates
  ([#68](https://github.com/FreddieMcHeart/downbeat/pull/68),
  [`ee53857`](https://github.com/FreddieMcHeart/downbeat/commit/ee5385748bda44d83098f60e81571269f2a9dfd2))

## v0.14.1 (2026-07-27)

### Bug Fixes

- Say what migrate's identity counter actually counts
  ([#66](https://github.com/FreddieMcHeart/downbeat/pull/66),
  [`40c7d21`](https://github.com/FreddieMcHeart/downbeat/commit/40c7d21d7a8d60cd56862aee4a7613b996c0568d))

## v0.14.0 (2026-07-27)

### Bug Fixes

- Keep migrate_store's id lookup type-safe
  ([#65](https://github.com/FreddieMcHeart/downbeat/pull/65),
  [`e9bf2c8`](https://github.com/FreddieMcHeart/downbeat/commit/e9bf2c86f6aa278b86600a1a9395ebd43f70c37a))

### Features

- Give peers a stable identity separate from their display name
  ([#65](https://github.com/FreddieMcHeart/downbeat/pull/65),
  [`e9bf2c8`](https://github.com/FreddieMcHeart/downbeat/commit/e9bf2c86f6aa278b86600a1a9395ebd43f70c37a))

- Stable peer identity, separate from display name (#40, Option A)
  ([#65](https://github.com/FreddieMcHeart/downbeat/pull/65),
  [`e9bf2c8`](https://github.com/FreddieMcHeart/downbeat/commit/e9bf2c86f6aa278b86600a1a9395ebd43f70c37a))

## v0.13.0 (2026-07-27)

### Features

- Version the message wire format and add a migration ladder (#42)
  ([#64](https://github.com/FreddieMcHeart/downbeat/pull/64),
  [`7c0e30c`](https://github.com/FreddieMcHeart/downbeat/commit/7c0e30c0aaf11fdaa8d326ad0b271e6a406b73c0))

## v0.12.0 (2026-07-27)

### Documentation

- Expand roadmap with kind-aware reconcile, idle-peer inbox controls, and schema-migration notes
  ([#58](https://github.com/FreddieMcHeart/downbeat/pull/58),
  [`6df2011`](https://github.com/FreddieMcHeart/downbeat/commit/6df2011e1ea0781a2ab2ca9f3edd927762ffe31d))

- Refresh ROADMAP "Recently shipped" through v0.11.1
  ([#57](https://github.com/FreddieMcHeart/downbeat/pull/57),
  [`51b04dd`](https://github.com/FreddieMcHeart/downbeat/commit/51b04dd9a8f3bc0935498b3ca5684b2815317466))

- Roadmap — cross-branch TUI send, forward verb, flat-routing principle
  ([#59](https://github.com/FreddieMcHeart/downbeat/pull/59),
  [`29d9798`](https://github.com/FreddieMcHeart/downbeat/commit/29d9798c03681af33f12c36dd1af421140e351bd))

### Features

- Teach reconcile which messages are terminal (#47)
  ([#63](https://github.com/FreddieMcHeart/downbeat/pull/63),
  [`7b803a7`](https://github.com/FreddieMcHeart/downbeat/commit/7b803a755993295b597acf2b694ffe1a97507fa2))

## v0.11.1 (2026-07-21)

### Bug Fixes

- Harden peer rename against edge cases found in review
  ([#55](https://github.com/FreddieMcHeart/downbeat/pull/55),
  [`15bb87b`](https://github.com/FreddieMcHeart/downbeat/commit/15bb87bd995e915fa0f1baf2694b867a5eff49aa))

## v0.11.0 (2026-07-21)

### Features

- Add `downbeat peers rename` for atomic peer rename (#40)
  ([#54](https://github.com/FreddieMcHeart/downbeat/pull/54),
  [`8376c85`](https://github.com/FreddieMcHeart/downbeat/commit/8376c85a3ce3c2203c553899f01e3fa837129e5b))

## v0.10.8 (2026-07-21)

### Bug Fixes

- Give background sessions honest relay-CLI feedback
  ([#52](https://github.com/FreddieMcHeart/downbeat/pull/52),
  [`962c471`](https://github.com/FreddieMcHeart/downbeat/commit/962c471e17e0b99fdf981b04fd0c34b029f2eb80))

## v0.10.7 (2026-07-21)

### Bug Fixes

- Standardize relay commands and skill on the `downbeat` CLI
  ([#51](https://github.com/FreddieMcHeart/downbeat/pull/51),
  [`be64e03`](https://github.com/FreddieMcHeart/downbeat/commit/be64e03e624fc2f504eb9c65abfb144ac1bf55e1))

## v0.10.6 (2026-07-20)

### Bug Fixes

- Raise the Textual floor to 8.0 and guard floors in CI
  ([#49](https://github.com/FreddieMcHeart/downbeat/pull/49),
  [`2754a87`](https://github.com/FreddieMcHeart/downbeat/commit/2754a8738583704d5662c59600c14376f2f29815))

### Documentation

- Add kind-aware reconcile and TUI-copy directions to the roadmap
  ([#50](https://github.com/FreddieMcHeart/downbeat/pull/50),
  [`4eaf61d`](https://github.com/FreddieMcHeart/downbeat/commit/4eaf61dc2b8b30c6f9a84fce1ceb49cd4e6ecccb))

## v0.10.5 (2026-07-20)

### Bug Fixes

- Make TUI copy land in the system clipboard everywhere
  ([#45](https://github.com/FreddieMcHeart/downbeat/pull/45),
  [`675cd99`](https://github.com/FreddieMcHeart/downbeat/commit/675cd997b114a5321c236890ccc9420f48d2ea7e))

### Continuous Integration

- Skip the test matrix for ROADMAP/CHANGELOG/LICENSE changes
  ([#39](https://github.com/FreddieMcHeart/downbeat/pull/39),
  [`c459e49`](https://github.com/FreddieMcHeart/downbeat/commit/c459e49dc34f01b959c3919d87214906be6c3180))

### Documentation

- Add design specs for the Next/Later roadmap items
  ([#44](https://github.com/FreddieMcHeart/downbeat/pull/44),
  [`c951f6f`](https://github.com/FreddieMcHeart/downbeat/commit/c951f6fb624e95b7de08a88c55b17f4dcbf4b562))

- Mark #30/#31 shipped in v0.10.4, clear the Now horizon
  ([#38](https://github.com/FreddieMcHeart/downbeat/pull/38),
  [`ba2fa0f`](https://github.com/FreddieMcHeart/downbeat/commit/ba2fa0f82e2f03f2da4d40957d599d9d23b766cd))

## v0.10.4 (2026-07-19)

### Bug Fixes

- Hand keyboard focus from find-message search box to results
  ([#37](https://github.com/FreddieMcHeart/downbeat/pull/37),
  [`c2a8e3b`](https://github.com/FreddieMcHeart/downbeat/commit/c2a8e3b8823653cbfbcbfb0ef9f9492fdffe29e3))

- Honest UTC log timestamps and find-message keyboard focus
  ([#37](https://github.com/FreddieMcHeart/downbeat/pull/37),
  [`c2a8e3b`](https://github.com/FreddieMcHeart/downbeat/commit/c2a8e3b8823653cbfbcbfb0ef9f9492fdffe29e3))

- Log timestamps in UTC so the trailing Z is honest
  ([#37](https://github.com/FreddieMcHeart/downbeat/pull/37),
  [`c2a8e3b`](https://github.com/FreddieMcHeart/downbeat/commit/c2a8e3b8823653cbfbcbfb0ef9f9492fdffe29e3))

### Documentation

- Add contributor guidance on duplicate-checking and test quality
  ([#29](https://github.com/FreddieMcHeart/downbeat/pull/29),
  [`c009912`](https://github.com/FreddieMcHeart/downbeat/commit/c009912fa458bba43e54bf2ed2a885ec77afd85f))

- Add project roadmap ([#35](https://github.com/FreddieMcHeart/downbeat/pull/35),
  [`166e561`](https://github.com/FreddieMcHeart/downbeat/commit/166e561932acd25e5e2f1dd8c7800a6b0b5c4262))

- Wire up roadmap and add per-peer autonomy item
  ([#36](https://github.com/FreddieMcHeart/downbeat/pull/36),
  [`d560fd5`](https://github.com/FreddieMcHeart/downbeat/commit/d560fd53faa7f20e97495ce21ed9c1edb2fb81e0))

## v0.10.3 (2026-07-16)

### Bug Fixes

- Anchor a head-inserted bubble on DOM index 0, not the _bubbles dict
  ([#27](https://github.com/FreddieMcHeart/downbeat/pull/27),
  [`bad347c`](https://github.com/FreddieMcHeart/downbeat/commit/bad347cb3ef8b8f2b8f33d85de45bfe7910cd55b))

- Track rendered bubbles synchronously instead of reading self.children
  ([#27](https://github.com/FreddieMcHeart/downbeat/pull/27),
  [`bad347c`](https://github.com/FreddieMcHeart/downbeat/commit/bad347cb3ef8b8f2b8f33d85de45bfe7910cd55b))

## v0.10.2 (2026-07-16)

### Bug Fixes

- Heal a corrupt sessions.json on removal instead of forwarding damage
  ([#28](https://github.com/FreddieMcHeart/downbeat/pull/28),
  [`752b043`](https://github.com/FreddieMcHeart/downbeat/commit/752b0433ede210ab4e539009a9911a7146d0e877))

- Promote a removed peer's children to its parent instead of orphaning
  ([#28](https://github.com/FreddieMcHeart/downbeat/pull/28),
  [`752b043`](https://github.com/FreddieMcHeart/downbeat/commit/752b0433ede210ab4e539009a9911a7146d0e877))

## v0.10.1 (2026-07-16)

### Bug Fixes

- Write before unlinking when archiving or replying
  ([#26](https://github.com/FreddieMcHeart/downbeat/pull/26),
  [`9c19f00`](https://github.com/FreddieMcHeart/downbeat/commit/9c19f00b951e450d7f263fb84db50410fb9b488f))

## v0.10.0 (2026-07-16)

### Bug Fixes

- The hook's read was unbounded in time, and its own comment lied
  ([#25](https://github.com/FreddieMcHeart/downbeat/pull/25),
  [`b8a9ce3`](https://github.com/FreddieMcHeart/downbeat/commit/b8a9ce311a5af91ba764713677391001a1ca5641))

- The staleness hook could never fire, and could eat 18GB
  ([#25](https://github.com/FreddieMcHeart/downbeat/pull/25),
  [`b8a9ce3`](https://github.com/FreddieMcHeart/downbeat/commit/b8a9ce311a5af91ba764713677391001a1ca5641))

### Documentation

- Name the invariant _MAX_OUTPUT is actually protecting
  ([#25](https://github.com/FreddieMcHeart/downbeat/pull/25),
  [`b8a9ce3`](https://github.com/FreddieMcHeart/downbeat/commit/b8a9ce311a5af91ba764713677391001a1ca5641))

### Features

- One command to update downbeat, and a check that catches drift
  ([#25](https://github.com/FreddieMcHeart/downbeat/pull/25),
  [`b8a9ce3`](https://github.com/FreddieMcHeart/downbeat/commit/b8a9ce311a5af91ba764713677391001a1ca5641))

### Testing

- Force colour instead of hoping for it, and cover the CLI that ignores NO_COLOR
  ([#25](https://github.com/FreddieMcHeart/downbeat/pull/25),
  [`b8a9ce3`](https://github.com/FreddieMcHeart/downbeat/commit/b8a9ce311a5af91ba764713677391001a1ca5641))

## v0.9.2 (2026-07-15)

### Bug Fixes

- Launch on the tab the tab bar says it is on
  ([#24](https://github.com/FreddieMcHeart/downbeat/pull/24),
  [`c04599a`](https://github.com/FreddieMcHeart/downbeat/commit/c04599a0941a9fc6bd6488d59582e73912a96ed8))

## v0.9.1 (2026-07-15)

### Bug Fixes

- Ctrl+R no longer empties the thread on a peer tab
  ([#23](https://github.com/FreddieMcHeart/downbeat/pull/23),
  [`817d8f6`](https://github.com/FreddieMcHeart/downbeat/commit/817d8f63fc4f2e66746ca71be21d1c27a7700063))

### Chores

- **ci**: Bump dorny/paths-filter from 3 to 4
  ([#14](https://github.com/FreddieMcHeart/downbeat/pull/14),
  [`31602a4`](https://github.com/FreddieMcHeart/downbeat/commit/31602a446bebe1db3215e5996819324db81f78f8))

## v0.9.0 (2026-07-15)

### Bug Fixes

- Peers screen indent keys off candidate_names, matching its own grouping
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

- Preserve a role=parent interior node's parent on re-register
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

### Documentation

- Design spec for general peer tree (decouple role from structure)
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

- Expand Task 4 scope — drift-check found 3 more dead PeerList-referencing test files
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

- Fix Task 2's find_message test to drive dismiss directly, not keyboard focus routing
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

- Implementation plan for general peer tree
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

- Pre-flight fix — replace vacuous find_message test with one that drives the real modal
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

- Retire the last two-tier claims from Peer.parent and set-parent help
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

### Features

- Decouple role from tree structure, add cycle prevention
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

- General peer tree (decouple role from structure)
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

- Peers screen groups interior tree nodes as their own header
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

- TUI acting-as pickers recognize interior tree nodes
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

### Refactoring

- Delete dead MainScreen/PeerList and their dead test coverage (superseded by ChatScreen)
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

### Testing

- Scope idempotency check to setup()'s own RotatingFileHandler
  ([#18](https://github.com/FreddieMcHeart/downbeat/pull/18),
  [`81628d2`](https://github.com/FreddieMcHeart/downbeat/commit/81628d2472cce5f9f9364f361824403baa38c24b))

## v0.8.0 (2026-07-14)

### Bug Fixes

- Correct is_recipient_stale missing-timestamp contract and make _write_tui_state atomic
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

- Separate TUI-liveness threshold from recipient-staleness threshold
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

### Documentation

- Address Minor findings from final whole-branch review
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

- Correct spec — hooks can't import the downbeat package, must self-contain
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

- Design spec for TUI-hosted relay staleness notify
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

- Implementation plan for TUI-hosted relay staleness notify
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

- Replace downbeat-watch docs with automatic staleness-notify docs
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

- Spec self-review — fix cooldown-duration and reply-recipient-parsing gaps
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

### Features

- Add core/notify.py native OS notification helper
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

- Add store.is_recipient_stale() for the idle-recipient notify check
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

- Add TUI heartbeat and per-recipient notify cooldown to tui_state.json
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

- Automatic staleness notify, remove standalone downbeat watch
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

- Remove standalone downbeat-watch CLI, replace with automatic staleness notify
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

- Staleness notify in relay-poll-offer hook for headless sessions
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

- Wire staleness notify into the TUI's resident FsWatcher
  ([#17](https://github.com/FreddieMcHeart/downbeat/pull/17),
  [`bb226e3`](https://github.com/FreddieMcHeart/downbeat/commit/bb226e37e3dcbab115be6dd6fa1c22805a0cf28d))

## v0.7.2 (2026-07-13)

### Bug Fixes

- Relay-reply bare-check should use downbeat inbox, not raw ls of inbox/ only
  ([#15](https://github.com/FreddieMcHeart/downbeat/pull/15),
  [`f4d1d80`](https://github.com/FreddieMcHeart/downbeat/commit/f4d1d80e96197306ed0a7999086c1593062a9108))

## v0.7.1 (2026-07-12)

### Bug Fixes

- Ctrl+c always quits the chat screen, even with a text widget focused
  ([#13](https://github.com/FreddieMcHeart/downbeat/pull/13),
  [`ef8f430`](https://github.com/FreddieMcHeart/downbeat/commit/ef8f4306c8e544737c68233b706da1d11eedd002))

- Sanitize spaces (and other chars) in peer names for Textual tab ids
  ([#13](https://github.com/FreddieMcHeart/downbeat/pull/13),
  [`ef8f430`](https://github.com/FreddieMcHeart/downbeat/commit/ef8f4306c8e544737c68233b706da1d11eedd002))

- Sanitize spaces in peer names for Textual tab ids
  ([#13](https://github.com/FreddieMcHeart/downbeat/pull/13),
  [`ef8f430`](https://github.com/FreddieMcHeart/downbeat/commit/ef8f4306c8e544737c68233b706da1d11eedd002))

## v0.7.0 (2026-07-11)

### Features

- Explicit parent-child pairing replaces name-prefix inference
  ([#12](https://github.com/FreddieMcHeart/downbeat/pull/12),
  [`3289c44`](https://github.com/FreddieMcHeart/downbeat/commit/3289c44bb6169479250271f66ac0925d05796db2))

## v0.6.0 (2026-07-10)

### Documentation

- **plugin**: Make install instructions copy-paste-exact
  ([#11](https://github.com/FreddieMcHeart/downbeat/pull/11),
  [`fa9d034`](https://github.com/FreddieMcHeart/downbeat/commit/fa9d0348ecba4bbc5aaa036982119eb4cad0aeab))

### Features

- **plugin**: Ship a marketplace.json for one-command plugin install
  ([#11](https://github.com/FreddieMcHeart/downbeat/pull/11),
  [`fa9d034`](https://github.com/FreddieMcHeart/downbeat/commit/fa9d0348ecba4bbc5aaa036982119eb4cad0aeab))

## v0.5.0 (2026-07-08)

### Continuous Integration

- Fan-in ci-required job instead of per-matrix required checks
  ([`a2d4aa4`](https://github.com/FreddieMcHeart/downbeat/commit/a2d4aa45d8ee5add31bbc4a993f70d08f80163e6))

- Fix paths-filter negation being a silent no-op
  ([`9a5ff08`](https://github.com/FreddieMcHeart/downbeat/commit/9a5ff081e712736080a5753a0e052396fcb74959))

- Skip test/typecheck/coverage/pre-commit on docs-only diffs
  ([`a2d4aa4`](https://github.com/FreddieMcHeart/downbeat/commit/a2d4aa45d8ee5add31bbc4a993f70d08f80163e6))

- Skip test/typecheck/coverage/pre-commit on docs-only diffs via fan-in required check
  ([`a2d4aa4`](https://github.com/FreddieMcHeart/downbeat/commit/a2d4aa45d8ee5add31bbc4a993f70d08f80163e6))

### Documentation

- Add --migrate-to-plugin design draft (reviewed by claude-core peer)
  ([#8](https://github.com/FreddieMcHeart/downbeat/pull/8),
  [`b8ded11`](https://github.com/FreddieMcHeart/downbeat/commit/b8ded119e90bc72c31d63caa5da5774e44f7472e))

- Fix trailing blank line left by the earlier smoke-test commit
  ([`a2d4aa4`](https://github.com/FreddieMcHeart/downbeat/commit/a2d4aa45d8ee5add31bbc4a993f70d08f80163e6))

- Record Phase 2 close-out and the fan-in ci-required pattern
  ([`aabfbb0`](https://github.com/FreddieMcHeart/downbeat/commit/aabfbb0e00b50cf8d183fe426a8dcb2bfd8d2aaf))

- Record predicate-quantifier fix, dependabot conflict, and migrate-to-plugin design status
  ([#9](https://github.com/FreddieMcHeart/downbeat/pull/9),
  [`a4287bc`](https://github.com/FreddieMcHeart/downbeat/commit/a4287bc075724d2bb861466422b18baec9400d83))

- Remove internal maintainer docs from the public site nav
  ([#9](https://github.com/FreddieMcHeart/downbeat/pull/9),
  [`a4287bc`](https://github.com/FreddieMcHeart/downbeat/commit/a4287bc075724d2bb861466422b18baec9400d83))

- Trailing-newline smoke test for ci.yml path-filter empirical check
  ([`a2d4aa4`](https://github.com/FreddieMcHeart/downbeat/commit/a2d4aa45d8ee5add31bbc4a993f70d08f80163e6))

### Features

- **init**: Implement --migrate-to-plugin
  ([#10](https://github.com/FreddieMcHeart/downbeat/pull/10),
  [`e1c1ea0`](https://github.com/FreddieMcHeart/downbeat/commit/e1c1ea0c6519a4a8ad5e47517deb31140f24881b))

### Testing

- Symmetric basename normalization in hooks_manifest parity test
  ([#10](https://github.com/FreddieMcHeart/downbeat/pull/10),
  [`e1c1ea0`](https://github.com/FreddieMcHeart/downbeat/commit/e1c1ea0c6519a4a8ad5e47517deb31140f24881b))

## v0.4.0 (2026-07-07)

### Chores

- **ci**: Bump actions/checkout from 4 to 7
  ([`513a73e`](https://github.com/FreddieMcHeart/downbeat/commit/513a73eeefbde978da8ca0b2279fc9c98f05ea5e))

- **ci**: Bump astral-sh/setup-uv from 5 to 7
  ([`fe39a8c`](https://github.com/FreddieMcHeart/downbeat/commit/fe39a8c0fdda939aa3e4dee54ee229a9cce31455))

- **ci**: Bump python-semantic-release/python-semantic-release from 9 to 10
  ([`6d922dc`](https://github.com/FreddieMcHeart/downbeat/commit/6d922dc32dc125dbb2dd3338b2ea1bc45cfc8024))

### Documentation

- Correct decisions.md's #15 plugin-supersedes-installer claim
  ([`f12da1d`](https://github.com/FreddieMcHeart/downbeat/commit/f12da1d42c1a32868bfdef0c77be491274c3d986))

### Features

- **plugin**: Ship a native Claude Code plugin, optional alongside init
  ([`f12da1d`](https://github.com/FreddieMcHeart/downbeat/commit/f12da1d42c1a32868bfdef0c77be491274c3d986))

## v0.3.0 (2026-07-06)

### Documentation

- Add VHS demo GIF to README
  ([`1c6c610`](https://github.com/FreddieMcHeart/downbeat/commit/1c6c610d942a01785481620662d46e20bc7401cb))

- Upgrade README hook/badges, add parent-child-handoff example
  ([`07b494f`](https://github.com/FreddieMcHeart/downbeat/commit/07b494f46a28680c1b347ab37675752851298465))

### Features

- **cli**: Colorized --help via rich-argparse; CI/quality wiring
  ([`bcb732a`](https://github.com/FreddieMcHeart/downbeat/commit/bcb732a6f49434a601678231b0fe3c376f915afa))

## v0.2.0 (2026-07-06)

### Documentation

- Durable lesson — PSR@v9 lacks $PACKAGE_NAME, build_command swallows errors
  ([`217f30a`](https://github.com/FreddieMcHeart/downbeat/commit/217f30a64568c851ce6fea8f8582170618b20668))

### Features

- **docs**: Add MkDocs Material docs site
  ([`0549e2d`](https://github.com/FreddieMcHeart/downbeat/commit/0549e2df085d5934c78d40a46a59185dc28946c8))

## v0.1.3 (2026-07-03)

### Bug Fixes

- **release**: Hardcode package name in build_command, $PACKAGE_NAME unset on @v9
  ([`a2dc364`](https://github.com/FreddieMcHeart/downbeat/commit/a2dc364a92623731f571caab77604fbaf9fda431))

### Chores

- **ci**: Sync uv.lock with the 0.1.2 version bump
  ([`6cf48b2`](https://github.com/FreddieMcHeart/downbeat/commit/6cf48b29e4094de9586a8667247c869cf7080cc7))

## v0.1.2 (2026-07-03)

### Bug Fixes

- **ci**: Sync uv.lock with the 0.1.1 version bump
  ([`db95371`](https://github.com/FreddieMcHeart/downbeat/commit/db953717311e9b5d5ba28239011c122e43d769d1))

- **release**: Keep uv.lock in sync on every future release
  ([`8cf5384`](https://github.com/FreddieMcHeart/downbeat/commit/8cf5384e4af4735581debafb8800c30628eb08af))

### Documentation

- Mark Phase 1 done — downbeat v0.1.1 live on PyPI
  ([`9a24111`](https://github.com/FreddieMcHeart/downbeat/commit/9a241111ed6fbf8c465cdb72535833e49b134f80))

## v0.1.1 (2026-07-03)

### Bug Fixes

- **release**: Grant contents:read to the publish job
  ([`ef5102c`](https://github.com/FreddieMcHeart/downbeat/commit/ef5102c1c3b0ae780d37e9ccf58c38cea81cc931))

- **release**: Push the version-bump commit via a PAT covered by the bypass
  ([`8adb0de`](https://github.com/FreddieMcHeart/downbeat/commit/8adb0de503ce6b21b7a4b146cfdf9f958965d87a))

## v0.1.0 (2026-07-03)

- Initial Release
