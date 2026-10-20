# Learned rules

The creator's corrections that should hold for every later reel. Everything in this folder except this README is
gitignored: the files live only on Marina's Mac and the developer never commits them (a pull would overwrite hers).

| File | Holds rules for |
|---|---|
| `learned/general.md` | every reel |
| `learned/brands/<brand>.md` | one brand, e.g. `learned/brands/yocase.md` |
| `learned/formats/<format>.md` | one format, e.g. `learned/formats/talking-head.md` |

One entry per line, appended at the end of the file:

```
- 2026-10-21 (reel yocase_261021_podarunok_podruzi) «субтитри завжди вище за підборіддя» → keep subtitle blocks above the chin line on talking heads
```

Her words stay in Ukrainian inside «»; the rule after the arrow is concrete and in English (what to do, where).

How rules flow:
1. During a reel Marina corrects something that sounds general. Claude asks «Запам'ятати це для всіх рілсів
   YOCASE?» and, on «так», appends the entry to the brand's file (or the format's, or `general.md`).
2. Before writing a script, the `reel` skill reads `learned/general.md` and the files of the reel's brand and
   format, if they exist, and follows them.
3. The developer gets them from `output/developer_report.txt` (`pipeline/doctor.py --report` copies every learned
   file there) or on a visit. He promotes a rule by hand into the tracked `brands/<brand>/` or `formats/<format>/`
   files and then deletes the entry here, so it is not read twice.
