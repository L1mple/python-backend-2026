"""Все сценарии подряд: python -m isolation"""

from isolation import dirty_read, non_repeatable_read, phantom_read, write_skew
from isolation.common import main

main([dirty_read.DEMO, non_repeatable_read.DEMO, phantom_read.DEMO, write_skew.DEMO])
