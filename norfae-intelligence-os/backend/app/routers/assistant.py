from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.agents.context import AgentContext
from app.agents.errors import AgentError
from app.agents.intelligence_registry import intelligence_agents
from app.core.authorization import Permission, require_permission
from app.core.dependencies import get_current_user, get_db
from app.core.tenant_context import reset_current_business_id, set_current_business_id
from app.llm.openrouter_client import get_openrouter_client
from app.models.assistant_conversation_model import AssistantConversation, AssistantMessage
from app.models.business_membership_model import BusinessMembership, MembershipRole
from app.models.business_model import Business
from app.models.user_model import User
from app.schemas.assistant_schema import (
    AssistantChatRequest, AssistantChatResponse, AssistantConversationDetail, AssistantConversationSummary,
    AssistantDeleteResponse,
)
from app.services.business_assistant_service import (
    AssistantNotFound, AssistantProviderFailure, BusinessAssistantService,
)

router = APIRouter(prefix="/assistant", tags=["Business Assistant"])
assistant_agent = intelligence_agents.get_agent("business_assistant")
assistant_service = BusinessAssistantService(get_openrouter_client())


async def assistant_business_context(
    x_business_id: int = Header(..., alias="X-Business-ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AsyncIterator[BusinessMembership]:
    membership = (
        db.query(BusinessMembership)
        .join(Business, Business.id == BusinessMembership.business_id)
        .filter(
            BusinessMembership.business_id == x_business_id,
            BusinessMembership.user_id == current_user.id,
            BusinessMembership.is_active.is_(True),
            Business.is_active.is_(True),
        ).first()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Business not found.")
    if (membership.business.owner_id == current_user.id) != (MembershipRole(membership.role) == MembershipRole.OWNER):
        raise HTTPException(status_code=403, detail="Business ownership membership is inconsistent.")
    require_permission(membership, Permission.ANALYTICS_READ)
    token = set_current_business_id(x_business_id)
    try:
        yield membership
    finally:
        reset_current_business_id(token)


def _context(membership, db):
    return AgentContext(
        user_id=str(membership.user_id),
        business_id=str(membership.business_id),
        permissions=frozenset({Permission.ANALYTICS_READ.value}),
        dependencies={
            "db": db,
            "business_assistant_service": assistant_service,
            "anomaly_detection_service": assistant_service.anomaly_service,
        },
    )


@router.post("/chat", response_model=AssistantChatResponse)
async def chat(
    payload: AssistantChatRequest,
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(assistant_business_context),
):
    try:
        return await assistant_agent.execute(payload, context=_context(membership, db))
    except AssistantNotFound:
        raise HTTPException(status_code=404, detail="Conversation not found.") from None
    except AssistantProviderFailure:
        raise HTTPException(status_code=503, detail="The business assistant is temporarily unavailable.") from None
    except AgentError:
        raise HTTPException(status_code=503, detail="The business assistant could not complete this request.") from None


@router.get("/conversations", response_model=list[AssistantConversationSummary])
def list_conversations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(assistant_business_context),
):
    return db.query(AssistantConversation).filter(
        AssistantConversation.business_id == membership.business_id,
        AssistantConversation.user_id == membership.user_id,
    ).order_by(AssistantConversation.updated_at.desc(), AssistantConversation.id.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()


@router.get("/conversations/{conversation_id}", response_model=AssistantConversationDetail)
def get_conversation(
    conversation_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(assistant_business_context),
):
    conversation = db.query(AssistantConversation).filter(
        AssistantConversation.id == conversation_id,
        AssistantConversation.business_id == membership.business_id,
        AssistantConversation.user_id == membership.user_id,
    ).first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    messages = db.query(AssistantMessage).filter(
        AssistantMessage.business_id == membership.business_id,
        AssistantMessage.conversation_id == conversation.id,
    ).order_by(AssistantMessage.id).offset((page - 1) * page_size).limit(page_size).all()
    return {"id": conversation.id, "title": conversation.title,
            "created_at": conversation.created_at, "updated_at": conversation.updated_at,
            "messages": messages}


@router.delete("/conversations/{conversation_id}", response_model=AssistantDeleteResponse)
def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    membership: BusinessMembership = Depends(assistant_business_context),
):
    require_permission(membership, Permission.BUSINESS_UPDATE)
    conversation = db.query(AssistantConversation).filter(
        AssistantConversation.id == conversation_id,
        AssistantConversation.business_id == membership.business_id,
        AssistantConversation.user_id == membership.user_id,
    ).first()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    db.delete(conversation)
    db.commit()
    return {"deleted": True}
