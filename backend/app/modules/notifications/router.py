"""Notifications: list, mark-read, WebSocket subscribe."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError
from app.core.security import decode_token, get_token_payload
from app.db.models import Notification
from app.db.session import AsyncSessionLocal, get_db
from app.modules.notifications.broker import broker

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    auth=Depends(get_token_payload),
    unread: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
):
    user_id = UUID(auth["sub"])
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread is not None:
        stmt = stmt.where(Notification.is_read == (not unread))
    total = int(
        (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    )
    res = await db.execute(
        stmt.order_by(desc(Notification.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "data": n.data,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in res.scalars().all()
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.patch("/{notif_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_read(
    notif_id: UUID,
    db: AsyncSession = Depends(get_db),
    auth=Depends(get_token_payload),
):
    n = await db.get(Notification, notif_id)
    if not n or n.user_id != UUID(auth["sub"]):
        raise NotFoundError("Notification not found")
    n.is_read = True
    n.read_at = datetime.now(UTC)
    await db.commit()


@router.post("/mark-all-read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_all_read(
    db: AsyncSession = Depends(get_db), auth=Depends(get_token_payload)
):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == UUID(auth["sub"]), Notification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(UTC))
    )
    await db.commit()


@router.websocket("/ws")
async def ws_notifications(websocket: WebSocket, token: str | None = Query(None)):
    """Authenticated WebSocket — subscribes the user to:
    - `user:<id>`     — personal notifications
    - `ops`           — operator-wide events (only if role is operator/admin)
    """
    if not token:
        await websocket.close(code=4401)
        return
    try:
        payload = decode_token(token)
    except Exception:  # noqa: BLE001
        await websocket.close(code=4401)
        return

    if payload.get("type") != "access":
        await websocket.close(code=4401)
        return

    user_channel = f"user:{payload['sub']}"
    role = payload.get("role")

    await websocket.accept()
    await broker.subscribe(user_channel, websocket)
    if role in ("operator", "admin"):
        await broker.subscribe("ops", websocket)
    if role == "taskforce":
        await broker.subscribe("taskforce", websocket)

    try:
        while True:
            # Heartbeat / wait for client message (close detection)
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        await broker.unsubscribe(user_channel, websocket)
        await broker.unsubscribe("ops", websocket)
        await broker.unsubscribe("taskforce", websocket)


async def create_notification(
    db: AsyncSession,
    *,
    user_id: UUID,
    type: str,
    title: str,
    body: str | None = None,
    data: dict | None = None,
) -> Notification:
    n = Notification(user_id=user_id, type=type, title=title, body=body, data=data)
    db.add(n)
    await db.commit()
    await db.refresh(n)
    await broker.publish(
        channel=f"user:{user_id}",
        event="notification.created",
        data={
            "id": str(n.id),
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "data": n.data,
        },
    )
    return n
