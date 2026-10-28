# Learned rules

Corrections from real reels that should hold for every later reel. These files are tracked: whoever makes a
correction on either Mac commits it, and the other Mac gets it with the next pull.

| File | Holds rules for |
|---|---|
| `learned/general.md` | every reel |
| `learned/brands/<brand>.md` | one brand, e.g. `learned/brands/yocase.md` |
| `learned/formats/<format>.md` | one format, e.g. `learned/formats/talking-head.md` |

One entry per line, appended at the end of the file:

```
- 2026-10-21 (reel yocase_261021_podarunok_podruzi) «субтитри завжди вище за підборіддя» → keep subtitle blocks above the chin line on talking heads
```

The words of the correction stay in their language inside «»; the rule after the arrow is concrete and in English
(what to do, where). The repository is public: write the rule only, never unreleased product names, prices, client
feedback or anything under NDA.

How rules flow:
1. During a reel someone corrects something that sounds general. Claude asks whether to remember it for every reel
   of the brand (to Marina: «Запам'ятати це для всіх рілсів YOCASE?») and, on yes, appends the entry to the brand's
   file (or the format's, or `general.md`) and commits it.
2. Before writing a script, the `reel` skill reads `learned/general.md` and the files of the reel's brand and
   format, if they exist, and follows them.
3. A rule that has held for a while can be folded into the tracked `brands/<brand>/` or `formats/<format>/` files
   (or into code); then delete its entry here, so it is not read twice.
