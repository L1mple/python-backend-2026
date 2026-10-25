from .scenarios import SCENARIOS

for title, run, _, note in SCENARIOS:
    observed = run()
    print(f"{title:50} -> {'ДА' if observed else 'нет'}" + (f"   ({note})" if note else ""))
