from app.models.operations import OperationalEvent
def record_operational_event(db, category, reason, actor_user_id=None):
    db.add(OperationalEvent(category=category, reason=str(reason)[:500], actor_user_id=actor_user_id)); db.flush()
