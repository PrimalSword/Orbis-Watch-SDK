import asyncio
import os

from orbis_watch import Watch


ADDRESS = os.environ.get("ORBIS_WATCH_ADDRESS", "41:42:99:10:58:57")


async def main() -> None:
    async with Watch(ADDRESS) as watch:
        print(f"Connected: {watch.is_connected}")
        print(f"Battery: {await watch.get_battery_level()}%")
        print(await watch.get_device_info())


if __name__ == "__main__":
    asyncio.run(main())
