import asyncio

from orbis_watch import Watch


ADDRESS = "41:42:99:10:58:57"


async def main() -> None:
    async with Watch(ADDRESS) as watch:
        features = await watch.get_features()
        print(f"Connected: {watch.is_connected}")
        print(f"Feature ACK: {features.acknowledged}")
        print(f"Bitmap: {features.hex}")
        print(f"Enabled bits: {features.enabled_bits}")


if __name__ == "__main__":
    asyncio.run(main())
