from sqlmodel import Session, select

from app.models import (
    EventConsumerReceipt,
    ModuleDesiredState,
    ModuleRegistry,
    OutboxEvent,
    OutboxEventStatus,
    Tenant,
)
from app.modules.outbox import (
    EVENT_HANDLERS,
    dispatch_pending_events,
    enqueue_event,
    register_event_handler,
)


def test_outbox_dispatch_is_idempotent_and_retries_failures(db: Session) -> None:
    delivered_payloads: list[dict[str, object]] = []

    def successful_handler(
        _session: Session, _event: OutboxEvent, payload: dict[str, object]
    ) -> None:
        delivered_payloads.append(payload)

    event_type = "test.outbox.delivered.v1"
    register_event_handler(event_type, "test-success", successful_handler)
    event = enqueue_event(
        session=db,
        module_code="platform",
        event_type=event_type,
        tenant_id=None,
        aggregate_id="aggregate-1",
        payload={"value": "expected"},
    )
    db.commit()

    delivered, failed = dispatch_pending_events(session=db)
    assert delivered >= 1
    assert failed == 0
    db.commit()
    db.refresh(event)
    assert event.status == OutboxEventStatus.PUBLISHED
    assert delivered_payloads == [{"value": "expected"}]
    assert db.get(EventConsumerReceipt, ("test-success", event.id)) is not None

    assert dispatch_pending_events(session=db) == (0, 0)
    db.commit()
    assert delivered_payloads == [{"value": "expected"}]

    def failing_handler(
        _session: Session, _event: OutboxEvent, _payload: dict[str, object]
    ) -> None:
        raise RuntimeError("expected handler failure")

    failed_event_type = "test.outbox.failed.v1"
    register_event_handler(failed_event_type, "test-failure", failing_handler)
    failed_event = enqueue_event(
        session=db,
        module_code="platform",
        event_type=failed_event_type,
        tenant_id=None,
        aggregate_id="aggregate-2",
        payload={},
    )
    db.commit()

    assert dispatch_pending_events(session=db) == (0, 1)
    db.commit()
    db.refresh(failed_event)
    assert failed_event.status == OutboxEventStatus.PENDING
    assert failed_event.attempts == 1
    assert failed_event.last_error == "expected handler failure"
    EVENT_HANDLERS.pop(event_type, None)
    EVENT_HANDLERS.pop(failed_event_type, None)


def test_disabled_module_events_are_retained_for_later_recovery(db: Session) -> None:
    tenant = db.exec(select(Tenant).where(Tenant.code == "default")).one()
    registry = db.get(ModuleRegistry, "items")
    assert registry is not None
    previous_state = registry.desired_state
    event = enqueue_event(
        session=db,
        module_code="items",
        event_type="items.test.pending.v1",
        tenant_id=tenant.id,
        aggregate_id="item-1",
        payload={},
    )
    registry.desired_state = ModuleDesiredState.DISABLED
    db.add(registry)
    db.commit()
    try:
        assert dispatch_pending_events(session=db) == (0, 0)
        db.commit()
        db.refresh(event)
        assert event.status == OutboxEventStatus.PENDING
    finally:
        registry.desired_state = previous_state
        db.add(registry)
        db.delete(event)
        db.commit()
