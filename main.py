import asyncio
import sys

from agent.core import ask

DEFAULT_QUESTION = "What's the current weather in Chicago?"


async def main() -> None:
    question = " ".join(sys.argv[1:]) or DEFAULT_QUESTION
    answer = await ask(question)
    print("\nFINAL ANSWER:\n", answer)


if __name__ == "__main__":
    asyncio.run(main())
