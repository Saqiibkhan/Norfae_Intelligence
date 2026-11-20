import asyncio
import sys

from app.llm.errors import OpenRouterError
from app.llm.openrouter_client import get_openrouter_client


async def main() -> int:
    client = get_openrouter_client()
    try:
        answer = await client.chat_completion(
            [{"role": "user", "content": "Reply with: OpenRouter connection verified."}],
            temperature=0,
            max_tokens=24,
        )
        print(answer)
        return 0
    except OpenRouterError as error:
        print(f"OpenRouter smoke test failed: {error}", file=sys.stderr)
        return 1
    finally:
        await client.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
