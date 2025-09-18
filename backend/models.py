from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True)
    password = Column(String, nullable=False)

    family_members = relationship("FamilyMember", back_populates="owner")


class FamilyMember(Base):
    __tablename__ = "family_members"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    dob = Column(Date)
    gender = Column(String)
    blood_type = Column(String)
    height = Column(Float)
    weight = Column(Float)
    relationship = Column(String)
    allergies = Column(Text)
    chronic_conditions = Column(Text)
    owner_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="family_members")
    reports = relationship("Report", back_populates="member")
    medications = relationship("Medication", back_populates="member")


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    report_date = Column(Date)
    report_type = Column(String)
    hospital_name = Column(String)
    doctor = Column(String)
    file_path = Column(String, nullable=True)

    member_id = Column(Integer, ForeignKey("family_members.id"))
    member = relationship("FamilyMember", back_populates="reports")


class Medication(Base):
    __tablename__ = "medications"
    id = Column(Integer, primary_key=True, index=True)
    condition = Column(String)
    medicine_name = Column(String)
    dosage = Column(String)
    frequency = Column(String)
    start_date = Column(Date)
    end_date = Column(Date)
    status = Column(String)
    doctor = Column(String)

    member_id = Column(Integer, ForeignKey("family_members.id"))
    member = relationship("FamilyMember", back_populates="medications")
