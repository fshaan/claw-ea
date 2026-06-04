"""EventKit 授权状态闸(headless 防污染)单元测试。

验证 _ensure_access 行为：
- 已授权(3/4) → 直接放行，不触发 request。
- notDetermined(0) + allow_prompt=False(默认/headless) → 报错且【不】调 request(不污染 TCC 缓存为 deny)。
- notDetermined(0) + allow_prompt=True(GUI grant) → 调 request。
- denied(2) → 报错。
- 弹窗被拒 → 报错。
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def _make_client(status):
    """构造 EventKitClient，authorizationStatusForEntityType_ 返回指定 status。"""
    patcher = patch("claw_ea.eventkit_utils.EKEventStore")
    MockStore = patcher.start()
    MockStore.alloc.return_value.init.return_value = MagicMock()
    MockStore.authorizationStatusForEntityType_.return_value = status
    from claw_ea.eventkit_utils import EventKitClient
    client = EventKitClient()
    client._request_access = AsyncMock(return_value=(True, None))
    return client, patcher


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [3, 4])
async def test_authorized_returns_without_request(status):
    client, patcher = _make_client(status)
    try:
        await client.ensure_reminder_access()
        client._request_access.assert_not_called()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_notdetermined_headless_raises_without_request():
    """关键：headless(默认 allow_prompt=False) 下 notDetermined 报错且不 request，避免污染缓存。"""
    client, patcher = _make_client(0)
    try:
        with pytest.raises(PermissionError):
            await client.ensure_reminder_access()
        client._request_access.assert_not_called()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_notdetermined_allow_prompt_requests():
    client, patcher = _make_client(0)
    try:
        await client.ensure_reminder_access(allow_prompt=True)
        client._request_access.assert_awaited_once()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_denied_raises_without_request():
    client, patcher = _make_client(2)
    try:
        with pytest.raises(PermissionError):
            await client.ensure_calendar_access()
        client._request_access.assert_not_called()
    finally:
        patcher.stop()


@pytest.mark.asyncio
async def test_prompt_denied_raises():
    client, patcher = _make_client(0)
    client._request_access = AsyncMock(return_value=(False, "user denied"))
    try:
        with pytest.raises(PermissionError):
            await client.ensure_reminder_access(allow_prompt=True)
    finally:
        patcher.stop()
