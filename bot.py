import asyncio

from core.bot import bot, load_skills
from core.config import TOKEN


async def main():
    async with bot:
        await load_skills()
        await bot.start(TOKEN)


if __name__ == "__main__":
    if not TOKEN:
        print("[FATAL ERROR] Token not found! Check your .env file")
    else:
        asyncio.run(main())