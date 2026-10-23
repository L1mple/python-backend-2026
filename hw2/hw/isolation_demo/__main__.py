from . import dirty_read, non_repeatable_read, phantom_read
from .common import run


async def main():
    await dirty_read.main()
    await non_repeatable_read.main()
    await phantom_read.main()


if __name__ == "__main__":
    run(main)
