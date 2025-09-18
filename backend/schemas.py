from pydantic import BaseModel
from datetime import date
from typing import Optional, List

class ReportBase(BaseModel):
    report_date: date
    report_type: str
    hospital_name: str
    doctor: Optional[str] = None

class ReportCreate(ReportBase):
    pass

class Report(ReportBase):
    id: int
    class Config:
        orm_mode = True


class MedicationBase(BaseModel):
    condition: str
    medicine_name: str
    dosage: str
    frequency: str
    start_date: date
    end_date: Optional[date]
    status: str
    doctor: Optional[str]

class MedicationCreate(MedicationBase):
    pass

class Medication(MedicationBase):
    id: int
    class Config:
        orm_mode = True


class FamilyMemberBase(BaseModel):
    name: str
    dob: date
    gender: str
    blood_type: Optional[str]
    height: Optional[float]
    weight: Optional[float]
    relationship: str

class FamilyMemberCreate(FamilyMemberBase):
    pass

class FamilyMember(FamilyMemberBase):
    id: int
    reports: List[Report] = []
    medications: List[Medication] = []
    class Config:
        orm_mode = True


class UserBase(BaseModel):
    name: str
    email: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    family_members: List[FamilyMember] = []
    class Config:
        orm_mode = True
