# The report to Marina

Written from `output/<name>.report.json` only (the build writes it next to the MP4; never grep a log for it) plus
your own judgement calls. Ukrainian, plain words, gender-neutral about her, no paths or English terms. Numbers with
a decimal comma and one decimal (28,8 с); over a minute as хв:сс (1:12). Leave out a line that has nothing to say.

```
**<ІДЕЯ з брифу> — чернетка**            (фінал: «— фінал»)
- Файл: <name>.mp4 — відкрила в QuickTime.
- Тривалість: сирий запис <raw_s> → рілс <out_s>.
- Прибрано: <removed.pauses.n> пауз (<s> с), <removed.retakes.n> невдалих дублів (<s> с), <removed.dead_air.s> с тиші між дублями; склейок: <edits>.
- Бренд · формат: <brand.names.brand> · <формат>.
- Хук: «<text.hook.text>» (<t0>–<t1> с).
- Заклик: «<text.cta[].text>» (<t0>–<t1> с, з дзвіночком).
- Вставки: <file> на словах «<at>» (<t0>–<t1> с, <картка | на весь екран>, <зі звуком | без звуку>); …
- Не вставлено: <file> — <why>.
- Музика: «<music.title>» (на запит «<music.asked>»), тихо під голосом, голосніше там, де ти мовчиш.
- Цензура: <слово> ×<n>; … · Латиницею: <слово> ×<n>; …
- Не знайшлося: <missing>, ролик зроблено без нього.
- Сумнівні рішення (скажи, якщо інакше): …
- Далі: подивись і напиши правки словами; коли все добре — «фінал».   (фінал: «коли опублікуєш — напиши «готово».»)
```

Where each line comes from (report.json keys):
- **Тривалість**: `raw_s`, `out_s`. `speed` ≠ 1: add «, пришвидшено ×<speed>».
- **Прибрано**: `removed.{pauses,retakes,dead_air}.{n,s}` and `edits`; only the non-zero parts. All zero after a
  trim that refused (constant bed): «Паузи не вирізано: під голосом постійний фон (музика або шум).»
- **Бренд · формат**: `brand.names.brand`; the format in her words: talking-head «говорюча голова», subtitles-only
  «лише субтитри», skit-hoche-a «скетч», product-lineup «лінійка».
- **Хук**: `text.hook` (`text`, `t0`, `t1`). **Заклик**: each of `text.cta` (`text`, `t0`, `t1`; «з дзвіночком»
  when `chime`).
- **Вставки**: `inserts.shown` (`file`, `at`, `t0`, `t1`; `mode` "full" = «на весь екран»; `sfx` null = «без
  звуку»; `crop` set = «обрізано до …», also under «Сумнівні рішення»). **Не вставлено**: `inserts.left_out` (the
  phrase was not heard: «не прозвучало «<at>»»), `inserts.refused` (`why` is already Ukrainian), and the files you
  chose not to place, with your reason.
- **Музика**: `music.title`, `music.asked`; «голосніше там, де ти мовчиш» only when `music.ducked_gaps` > 0;
  `music.short_by_s`: «трек закінчується за <n> с до кінця»; `music` null: «без музики».
- **Цензура / Латиницею**: `text.censored` and `text.latin` (word -> count).
- **Не знайшлося**: `missing` (`kind` sfx = «звук», music = «музика»; `name`).
- **Сумнівні рішення**: each call she might not want: the format you chose (subtitles-only for baked graphics), a
  hook you wrote, an earlier take kept, a speed capped, a crop, a size step-down (`checks.warn` «size … ->»), each
  `no free spot` block in `checks.warn` after looking at its review tile («текст «<слова>» частково на тобі, <t> с»),
  a track picked among several.
- `checks.fail` never reaches a report: a draft with a FAIL is not shown to her.

**For DaVinci** (after `export_fcpxml.py`), one more line: «Проєкт для DaVinci — папка <name>_project (показала у
Finder). Музика там уже приглушена під голосом, як у ролику; поруч лежить вимкнена доріжка без обробки.»
