from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, declarative_base, sessionmaker, with_loader_criteria

from app.core.config import settings


engine = create_engine(settings.DATABASE_URL, echo=False)
Base = declarative_base()


class TenantSession(Session):
    """Session that refuses tenant-owned ORM access without an authorized scope."""


class TenantContextRequired(RuntimeError):
    """Raised when tenant-owned data is accessed without business context."""


def _tenant_model_classes():
    # Import lazily to avoid a Base -> model -> Base import cycle.
    from app.models import (
        Analytics,
        AssistantConversation,
        AssistantMessage,
        AuditLog,
        Category,
        Creative,
        Expense,
        InventoryProduct,
        MetaDailyStats,
        Order,
        OrderItem,
        Product,
        ProductMatchMemory,
        Report,
        SettingsModel,
    )

    return (
        Analytics,
        AssistantConversation,
        AssistantMessage,
        AuditLog,
        Category,
        Creative,
        Expense,
        InventoryProduct,
        MetaDailyStats,
        Order,
        OrderItem,
        Product,
        ProductMatchMemory,
        Report,
        SettingsModel,
    )


@event.listens_for(TenantSession, "do_orm_execute")
def _scope_tenant_orm_operations(execute_state):
    tenant_models = _tenant_model_classes()
    mapped_classes = {mapper.class_ for mapper in execute_state.all_mappers}
    targets = mapped_classes.intersection(tenant_models)
    if not targets:
        return

    from app.core.tenant_context import get_current_business_id

    business_id = get_current_business_id()
    if business_id is None:
        raise TenantContextRequired(
            "Tenant-owned ORM queries require an authorized business context."
        )

    if execute_state.is_select:
        options = [
            with_loader_criteria(
                model,
                lambda entity: entity.business_id == business_id,
                include_aliases=True,
            )
            for model in targets
        ]
        execute_state.statement = execute_state.statement.options(*options)
    elif execute_state.is_update or execute_state.is_delete:
        for model in targets:
            execute_state.statement = execute_state.statement.where(
                model.business_id == business_id
            )


@event.listens_for(TenantSession, "before_flush")
def _assign_and_validate_tenant_on_flush(session, _flush_context, _instances):
    tenant_models = _tenant_model_classes()
    from app.core.tenant_context import get_current_business_id

    business_id = get_current_business_id()
    for instance in session.new.union(session.dirty).union(session.deleted):
        if not isinstance(instance, tenant_models):
            continue
        if business_id is None:
            raise TenantContextRequired(
                "Tenant-owned ORM writes require an authorized business context."
            )
        existing_business_id = getattr(instance, "business_id", None)
        if existing_business_id is None and instance in session.new:
            instance.business_id = business_id
        elif existing_business_id != business_id:
            raise TenantContextRequired(
                "A tenant-owned record cannot be written in another business context."
            )


SessionLocal = sessionmaker(
    autoflush=False,
    autocommit=False,
    bind=engine,
    class_=TenantSession,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
