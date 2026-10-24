import asyncio

from transactions import dirty_read, non_repeatable_read, phantom_read, serialization_anomaly


async def main() -> None:
    for module in (dirty_read, non_repeatable_read, phantom_read, serialization_anomaly):
        await module.main()


if __name__ == '__main__':
    asyncio.run(main())
