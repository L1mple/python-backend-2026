## Уровни изоляции

dirty_read.py - на read committed видим старые 100 а не 999

non_repeatable.py - на read committed видим 100 потом 500. А на repeatable read оба раза 100

phantom.py - на read committed видим 2 потом 3. На repeatable read и serializable оба раза 2
