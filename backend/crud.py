from sqlalchemy.orm import Session
from . import models, schemas

def create_user(db: Session, user: schemas.UserCreate):
    db_user = models.User(name=user.name, email=user.email, password=user.password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def get_users(db: Session):
    return db.query(models.User).all()

def create_family_member(db: Session, member: schemas.FamilyMemberCreate, user_id: int):
    db_member = models.FamilyMember(**member.dict(), owner_id=user_id)
    db.add(db_member)
    db.commit()
    db.refresh(db_member)
    return db_member

def get_family_members(db: Session, user_id: int):
    return db.query(models.FamilyMember).filter(models.FamilyMember.owner_id == user_id).all()
