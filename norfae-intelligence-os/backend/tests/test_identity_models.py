import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import Business, BusinessMembership, MembershipRole, User


@pytest.fixture
def db_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def add_user(session: Session, email: str = "owner@example.com") -> User:
    user = User(email=email, password_hash="test-hash")
    session.add(user)
    session.flush()
    return user


def add_business(session: Session, owner: User, name: str = "Norfae") -> Business:
    business = Business(name=name, owner=owner)
    session.add(business)
    session.flush()
    return business


def test_user_normalizes_email_and_enforces_case_insensitive_uniqueness(db_session):
    user = add_user(db_session, "  Owner@Example.COM ")
    assert user.email == "owner@example.com"

    db_session.add(User(email="OWNER@example.com", password_hash="another-hash"))
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_business_owner_foreign_key_is_enforced(db_session):
    db_session.add(Business(name="Invalid owner", owner_id=9999))
    with pytest.raises(IntegrityError):
        db_session.commit()


@pytest.mark.parametrize("missing_parent", ["user", "business"])
def test_membership_foreign_keys_are_enforced(db_session, missing_parent):
    user = add_user(db_session)
    business = add_business(db_session, user)
    membership = BusinessMembership(
        user_id=9999 if missing_parent == "user" else user.id,
        business_id=9999 if missing_parent == "business" else business.id,
        role=MembershipRole.VIEWER,
    )
    db_session.add(membership)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_duplicate_membership_is_rejected(db_session):
    user = add_user(db_session)
    business = add_business(db_session, user)
    db_session.add_all(
        [
            BusinessMembership(user=user, business=business, role="owner"),
            BusinessMembership(user=user, business=business, role="admin"),
        ]
    )

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_membership_role_validation_accepts_supported_roles_and_rejects_others():
    for role in MembershipRole:
        membership = BusinessMembership(role=role)
        assert membership.role == role.value

    with pytest.raises(ValueError, match="Unsupported membership role"):
        BusinessMembership(role="superuser")


def test_user_can_own_multiple_businesses_and_business_can_have_multiple_members(
    db_session,
):
    owner = add_user(db_session, "owner@example.com")
    member = add_user(db_session, "member@example.com")
    first = add_business(db_session, owner, "First business")
    second = add_business(db_session, owner, "Second business")
    first.memberships.extend(
        [
            BusinessMembership(user=owner, role=MembershipRole.OWNER),
            BusinessMembership(user=member, role=MembershipRole.ANALYST),
        ]
    )
    second.memberships.append(
        BusinessMembership(user=owner, role=MembershipRole.OWNER)
    )
    db_session.flush()

    assert {business.name for business in owner.owned_businesses} == {
        "First business",
        "Second business",
    }
    assert {membership.user.email for membership in first.memberships} == {
        "owner@example.com",
        "member@example.com",
    }
    assert {membership.business.name for membership in owner.memberships} == {
        "First business",
        "Second business",
    }
    assert second.owner is owner
