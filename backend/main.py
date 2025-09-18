import os
import shutil
import uuid
from datetime import datetime, date
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

# ----------------------------
# Setup
# ----------------------------
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./health.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Health Assistant - Integrated Backend")

origins = ["http://localhost:8501", "http://127.0.0.1:8501"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# Database Models
# ----------------------------
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=False)
    password = Column(String, nullable=False)  # plaintext only for demo

class FamilyMember(Base):
    __tablename__ = "family"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    dob = Column(String, nullable=False)
    gender = Column(String)
    blood_type = Column(String)
    height_cm = Column(Float)
    weight_kg = Column(Float)
    allergies = Column(String)
    chronic_conditions = Column(Text)  # stored as comma-separated

    reports = relationship("Report", back_populates="member")
    medications = relationship("Medication", back_populates="member")

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("family.id"))
    date = Column(String, nullable=False)
    type = Column(String, nullable=False)
    lab = Column(String)
    doctor = Column(String)
    file_path = Column(String)
    parsed = Column(Text)  # store JSON string
    notes = Column(Text)

    member = relationship("FamilyMember", back_populates="reports")

class Medication(Base):
    __tablename__ = "medications"
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("family.id"))
    name = Column(String, nullable=False)
    dosage = Column(String, nullable=False)
    freq = Column(String, nullable=False)
    start = Column(String)
    end = Column(String)
    doctor = Column(String)
    status = Column(String, default="Active")

    member = relationship("FamilyMember", back_populates="medications")

Base.metadata.create_all(bind=engine)

# ----------------------------
# Pydantic Schemas
# ----------------------------
class AuthRequest(BaseModel):
    email: str
    password: str

class AuthResponse(BaseModel):
    token: str
    email: str
    name: str

class FamilyMemberIn(BaseModel):
    name: str
    dob: str
    gender: Optional[str] = None
    blood_type: Optional[str] = None
    height_cm: Optional[float] = None
    weight_kg: Optional[float] = None
    allergies: Optional[str] = None
    chronic_conditions: Optional[List[str]] = []

class FamilyMemberOut(FamilyMemberIn):
    id: int

class MedicationIn(BaseModel):
    member_id: int
    name: str
    dosage: str
    freq: str
    start: Optional[str] = None
    end: Optional[str] = None
    doctor: Optional[str] = None
    status: Optional[str] = "Active"

class MedicationOut(MedicationIn):
    id: int

class ReportOut(BaseModel):
    id: int
    member_id: int
    date: str
    type: str
    lab: Optional[str]
    doctor: Optional[str]
    parsed: Optional[dict]
    notes: Optional[str]
    file_path: Optional[str]

# ----------------------------
# Dependency
# ----------------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------------------
# Auth
# ----------------------------
@app.post("/auth/login", response_model=AuthResponse)
def login(payload: AuthRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or user.password != payload.password:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = f"mock-token-{uuid.uuid4().hex}"
    return {"token": token, "email": user.email, "name": user.name}

# ----------------------------
# Health
# ----------------------------
@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}

# ----------------------------
# Family CRUD
# ----------------------------
@app.get("/family", response_model=List[FamilyMemberOut])
def list_family(db: Session = Depends(get_db)):
    members = db.query(FamilyMember).all()
    out = []
    for m in members:
        out.append({
            "id": m.id,
            "name": m.name,
            "dob": m.dob,
            "gender": m.gender,
            "blood_type": m.blood_type,
            "height_cm": m.height_cm,
            "weight_kg": m.weight_kg,
            "allergies": m.allergies,
            "chronic_conditions": m.chronic_conditions.split(",") if m.chronic_conditions else []
        })
    return out

@app.post("/family", response_model=FamilyMemberOut)
def add_family(member: FamilyMemberIn, db: Session = Depends(get_db)):
    m = FamilyMember(
        name=member.name,
        dob=member.dob,
        gender=member.gender,
        blood_type=member.blood_type,
        height_cm=member.height_cm,
        weight_kg=member.weight_kg,
        allergies=member.allergies,
        chronic_conditions=",".join(member.chronic_conditions) if member.chronic_conditions else ""
    )
    db.add(m)
    db.commit()
    db.refresh(m)
    return {
        **member.dict(),
        "id": m.id
    }

@app.get("/family/{member_id}", response_model=FamilyMemberOut)
def get_family_member(member_id: int, db: Session = Depends(get_db)):
    m = db.query(FamilyMember).filter(FamilyMember.id == member_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    return {
        "id": m.id,
        "name": m.name,
        "dob": m.dob,
        "gender": m.gender,
        "blood_type": m.blood_type,
        "height_cm": m.height_cm,
        "weight_kg": m.weight_kg,
        "allergies": m.allergies,
        "chronic_conditions": m.chronic_conditions.split(",") if m.chronic_conditions else []
    }

# ----------------------------
# Reports
# ----------------------------
@app.post("/reports/upload", response_model=ReportOut)
async def upload_report(
    member_id: int = Form(...),
    report_date: str = Form(...),
    report_type: str = Form(...),
    lab_name: Optional[str] = Form(None),
    doctor: Optional[str] = Form(None),
    file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    new_report = Report(
        member_id=member_id,
        date=report_date,
        type=report_type,
        lab=lab_name,
        doctor=doctor,
        file_path=None
    )
    if file:
        filename = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = os.path.abspath(os.path.join(UPLOAD_DIR, filename))
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        new_report.file_path = file_path
    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return new_report

@app.get("/reports", response_model=List[ReportOut])
def list_reports(member_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Report)
    if member_id:
        q = q.filter(Report.member_id == member_id)
    return q.all()

@app.post("/reports/{report_id}/parse", response_model=ReportOut)
def parse_report(report_id: int, db: Session = Depends(get_db)):
    r = db.query(Report).filter(Report.id == report_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")
    r.parsed = '{"Glucose": 95, "Cholesterol": 180, "TSH": 2.1}'
    r.notes = "AI: Mock parsed values"
    db.commit()
    db.refresh(r)
    return r

# ----------------------------
# Medications
# ----------------------------
@app.get("/medications", response_model=List[MedicationOut])
def list_medications(member_id: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(Medication)
    if member_id:
        q = q.filter(Medication.member_id == member_id)
    return q.all()

@app.post("/medications", response_model=MedicationOut)
def add_medication(med: MedicationIn, db: Session = Depends(get_db)):
    m = Medication(**med.dict())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m

@app.put("/medications/{med_id}", response_model=MedicationOut)
def update_medication(med_id: int, med: MedicationIn, db: Session = Depends(get_db)):
    obj = db.query(Medication).filter(Medication.id == med_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Medication not found")
    for k, v in med.dict().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj

# ----------------------------
# Risk Prediction
# ----------------------------
@app.get("/predict/risk")
def predict_risk(member_id: int, db: Session = Depends(get_db)):
    m = db.query(FamilyMember).filter(FamilyMember.id == member_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Member not found")
    try:
        dob = datetime.strptime(m.dob, "%Y-%m-%d").date()
        age = (date.today() - dob).days // 365
    except Exception:
        age = 40
    score = min(95, 30 + (age // 2))
    return {"member_id": member_id, "risk_score": score, "message": "Mock risk score (0-100)"}
