import json
import logging
from collections.abc import Callable
from datetime import timedelta
from typing import Any

from sqlmodel import Session, col, select

from app.models import (
    EventConsumerReceipt,
    OutboxEvent,
    OutboxEventStatus,
    get_datetime_utc,
)
from app.modules.access import evaluate_module_access

logger = logging.getLogger(__name__)

EventHandler = Callable[[Session, OutboxEvent, dict[str, Any]], None]
EVENT_HANDLERS: dict[str, list[tuple[str, EventHandler]]] = {}


def register_event_handler(
    event_type: str, consumer_name: str, handler: EventHandler
) -> None:
    EVENT_HANDLERS.setdefault(event_type, []).append((consumer_name, handler))


def enqueue_event(
    *,
    session: Session,
    module_code: str,
    event_type: str,
    tenant_id,
    aggregate_id: str,
    payload: dict[str, Any],
    event_version: int = 1,
    trace_id: str | None = None,
) -> OutboxEvent:
    now = get_datetime_utc()
    event = OutboxEvent(
        module_code=module_code,
        event_type=event_type,
        event_version=event_version,
        tenant_id=tenant_id,
        aggregate_id=aggregate_id,
        payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        trace_id=trace_id,
        occurred_at=now,
        available_at=now,
    )
    session.add(event)
    return event


def dispatch_pending_events(
    *, session: Session, max_events: int = 100, max_attempts: int = 8
) -> tuple[int, int]:
    """Deliver pending events at least once and record per-consumer idempotency."""
    now = get_datetime_utc()
    events = session.exec(
        select(OutboxEvent)
        .where(
            OutboxEvent.status == OutboxEventStatus.PENDING,
            OutboxEvent.available_at <= now,
        )
        .order_by(col(OutboxEvent.available_at), col(OutboxEvent.occurred_at))
        .limit(max_events)
        .with_for_update(skip_locked=True)
    ).all()
    delivered = 0
    failed = 0
    for event in events:
        if event.module_code != "platform" and event.tenant_id is not None:
            decision = evaluate_module_access(
                session=session,
                tenant_id=event.tenant_id,
                module_code=event.module_code,
            )
            if not decision.allowed:
                # A disabled module retains work for an explicit later recovery.
                continue
        try:
            payload = json.loads(event.payload)
            if not isinstance(payload, dict):
                raise ValueError("Outbox payload must be an object")
            for consumer_name, handler in EVENT_HANDLERS.get(event.event_type, []):
                receipt = session.get(EventConsumerReceipt, (consumer_name, event.id))
                if receipt is not None:
                    continue
                handler(session, event, payload)
                session.add(
                    EventConsumerReceipt(
                        consumer_name=consumer_name,
                        event_id=event.id,
                        processed_at=get_datetime_utc(),
                    )
                )
            event.status = OutboxEventStatus.PUBLISHED
            event.published_at = get_datetime_utc()
            event.last_error = None
            session.add(event)
            delivered += 1
        except Exception as exc:  # Event handlers must not terminate the worker loop.
            event.attempts += 1
            event.last_error = str(exc)[:2000]
            if event.attempts >= max_attempts:
                event.status = OutboxEventStatus.DEAD_LETTER
                event.dead_lettered_at = get_datetime_utc()
                logger.exception("Outbox event %s moved to dead letter", event.id)
            else:
                event.available_at = get_datetime_utc() + timedelta(
                    seconds=min(300, 2**event.attempts)
                )
                logger.exception("Outbox event %s delivery failed", event.id)
            session.add(event)
            failed += 1
    return delivered, failed


def requeue_dead_letter(*, session: Session, event: OutboxEvent) -> None:
    event.status = OutboxEventStatus.PENDING
    event.available_at = get_datetime_utc()
    event.attempts = 0
    event.last_error = None
    event.dead_lettered_at = None
    session.add(event)
