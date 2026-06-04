"""一次性 GUI 授权入口：仅此处允许触发 TCC 弹窗。必须在图形登录会话运行。

用法（经签名 bundle 的 clawpy 跑，使 disclaim/responsible 生效）：
    ~/.claw-ea/claw-launcher ~/.claw-ea/claw-ea.app/Contents/MacOS/clawpy -m claw_ea.grant
"""
import asyncio

from claw_ea.eventkit_utils import EventKitClient


async def main() -> None:
    client = EventKitClient()
    await client.ensure_reminder_access(allow_prompt=True)
    await client.ensure_calendar_access(allow_prompt=True)
    print("授权完成。之后 Ghostty / GUI-Hermes / cron 均直接可用。")


if __name__ == "__main__":
    asyncio.run(main())
