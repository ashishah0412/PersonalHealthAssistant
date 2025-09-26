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

import pytesseract
from PIL import Image
import requests
import json

 # Your Gemini API key. Replace 'YOUR_API_KEY' with your actual key.
# This key allows your program to communicate with the Gemini API.
API_KEY = ""

# The URL for the Gemini API. We are using the gemini-2.5-flash-preview-05-20 model.
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={API_KEY}"

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
    extracted_text = Column(Text, nullable=True)  # raw OCR text
    report_json = Column(Text, nullable=True)     # structured data from LLM

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
    class Config:
        orm_mode = True



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
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")

    if file:
        filename = f"{uuid.uuid4().hex}_{file.filename}"
        file_path = os.path.abspath(os.path.join(UPLOAD_DIR, filename))
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        # 2. Run OCR
        print("Starting OCR...")
        extracted_text = extract_text_from_file(file_path)
        print(f"OCR Extracted Text: {extracted_text[:100]}...")  # Print first 100 chars
        print("OCR done. Starting LLM...")

        # 3. Run LLM parsing
        parsed_json = None
        if extracted_text and not extracted_text.startswith("Error"):
            parsed_json = generate_report_json(extracted_text)    
        new_report = Report(
        member_id=member_id,
        date=report_date,
        type=report_type,
        lab=lab_name,
        doctor=doctor,
        file_path=file_path,
        extracted_text=extracted_text,  # <-- Save OCR result here
        report_json=json.dumps(parsed_json) if parsed_json else None
        )
        #new_report.file_path = file_path

    db.add(new_report)
    db.commit()
    db.refresh(new_report)
    return ReportOut(
        id=new_report.id,
        member_id=new_report.member_id,
        date=new_report.date,
        type=new_report.type,
        lab=new_report.lab,
        doctor=new_report.doctor,
        parsed=json.loads(new_report.report_json) if new_report.report_json else None,
        notes=new_report.notes,
        file_path=new_report.file_path
    )
    #return new_report

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




def extract_text_from_file(file_path: str) -> str:
# do OCR (pytesseract, textract, AWS Textract, etc.)        
    """
    Extracts text from an image file using the Tesseract OCR engine.

    Args:
        image_path (str): The path to the image file.

    Returns:
        str: The extracted text, or an error message if the operation fails.
    """
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Update this path if necessary
    

    if not os.path.exists(file_path):
        return f"Error: Image file not found at '{file_path}'."

    try:
        # Open the image using Pillow (PIL)
        image = Image.open(file_path)

        # Use pytesseract to perform OCR on the image.
        # The image_to_string() function will return the recognized text.
        text = pytesseract.image_to_string(image)

        return text.strip()  # .strip() removes leading/trailing whitespace

    except pytesseract.TesseractNotFoundError:
        return "Error: Tesseract is not installed or not in your PATH. Please install it."
    except Exception as e:
        return f"An unexpected error occurred: {e}"



def generate_report_json(report_text: str) -> dict:   

    """
    Sends the lab report text to the Gemini API for parsing and JSON generation.
    The API is instructed to create the JSON structure itself.

    Args:
        report_text (str): The raw text of the lab report.

    Returns:
        dict: A dictionary representing the parsed JSON data, or None on failure.
    """
    
    # The system instruction now contains a detailed description of the JSON structure.
    # This is how we guide the model to produce the desired output without a schema.
    system_instruction = {
        "parts": [{
            "text": """
            You are an expert at parsing medical lab reports and formatting the data into JSON.
            Your task is to extract all the key information from the provided lab report text and format it into a single JSON object.
            
            Strictly follow these rules:
            1. The final output MUST be a single JSON object.
            2. The JSON object MUST have the following top-level keys:
            - "reportDetails": An object containing details like "regNo", "registeredOn", "collectedOn", "receivedOn", and "reportedOn".
            - "patientDetails": An object with "name", "age" (as a number), and "sex".
            - "labDetails": An object with "labName", "labIncharge" (an object with name and qualification), and "pathologist" (an object with name and qualification).
            - "testResults": An array of objects. Each object in this array must contain "testName", "value", "unit", and "referenceRange".
            - "clinicalNotes": A string containing the clinical notes.
            - "abnormalParametersNotes": A string for notes on abnormal parameters.
            3. Extract all fields and populate the JSON object.
            4. For test results, parse each line in the "HAEMATOLOGY" section into a separate object within the "testResults" array.
            5. Clean the data. For example, remove extra words like "Lo" and "H_" from the value field and place them in the test name, if necessary.
            """
        }]
    }

    # The payload for the API request. Note the absence of the 'responseSchema'.
    payload = {
        "contents": [{"parts": [{"text": report_text}]}],
        "systemInstruction": system_instruction,
        "generationConfig": {
            "responseMimeType": "application/json",
        }
    }

    try:
        # Make the API request
        response = requests.post(API_URL, json=payload, timeout=30)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Parse the JSON response and return the content
        response_data = response.json()
        raw_json_string = response_data['candidates'][0]['content']['parts'][0]['text']
        return json.loads(raw_json_string)
    except requests.exceptions.RequestException as e:
        print(f"API request failed: {e}")
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"Error parsing API response: {e}")
        print("Raw response:", response.text)
    
    return None

