from flask import Flask, request, jsonify, session, render_template, send_from_directory, redirect, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import create_engine
from db_connector import get_db_connection_string
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from secrets import token_hex 
import os
import json
import requests
import base64
import hashlib 
import random
import pymysql
from math import radians, sin, cos, sqrt, atan2
import time

DATABASE_URL = get_db_connection_string()

def get_db_connection_string():
    """
    Constructs the SQLAlchemy connection string by reading environment variables.
    
    This is essential for secure cloud deployment (e.g., on Render), 
    as it avoids hardcoding sensitive credentials.
    """
    # Reads environment variables provided by the deployment platform
    # The default values are fallbacks, but should be set explicitly on Render/Cloud.
    DB_USER = os.environ.get("DB_USER", "default_user")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "default_password")
    DB_HOST = os.environ.get("DB_HOST", "localhost") 
    DB_NAME = os.environ.get("DB_NAME", "default_db")

    # Format the URL string for SQLAlchemy using the PyMySQL connector
    # This string looks like: protocol://user:password@host/database
    return f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}/{DB_NAME}"

try:
    engine = create_engine(
        DATABASE_URL, 
        pool_pre_ping=True
    )
    # This line attempts to connect immediately to verify credentials
    with engine.connect() as connection:
        print("Database connection verified successfully!")
except Exception as e:
    # Log a failure, but often the app continues to start
    print(f"FATAL: Database connection failed. Error: {e}")
    engine = None 

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://127.0.0.1:5000", "http://localhost:5000", os.getenv("RENDER_EXTERNAL_URL", "http://localhost")])
app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

UPLOAD_FOLDER = 'uploads/profile'
COMPLAINT_UPLOAD_FOLDER = 'uploads/complaints'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['COMPLAINT_UPLOAD_FOLDER'] = COMPLAINT_UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024 
app.secret_key = os.getenv('FLASK_SECRET_KEY', '18/07/2003ShAiKaLtHaF143@')

db = SQLAlchemy(app)

class Grievance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), db.ForeignKey('user.user_id'), nullable=False) 
    complaint_id = db.Column(db.String(255), unique=True, nullable=False) 
    raw_text = db.Column(db.Text, nullable=False)
    raw_text_processed = db.Column(db.Text)
    professional_text = db.Column(db.Text)
    grievance_type = db.Column(db.String(100))
    location_tag = db.Column(db.String(255))
    status = db.Column(db.String(50), default='PENDING') 
    assigned_officer_id = db.Column(db.String(50), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())
    proofs = db.relationship('ResolutionProof', backref='grievance', lazy=True)
    attachments = db.relationship('Attachment', backref='grievance', lazy=True)

    def __repr__(self):
        return f'<Grievance {self.complaint_id}: {self.grievance_type} - {self.status}>'

class ResolutionProof(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grievance_id = db.Column(db.Integer, db.ForeignKey('grievance.id'), nullable=False)
    officer_id = db.Column(db.String(50), nullable=False)
    cv_score = db.Column(db.Float) 
    is_fraudulent = db.Column(db.Boolean, default=False)
    proof_hash = db.Column(db.String(64), unique=True, nullable=False) 
    verified_at = db.Column(db.DateTime, default=db.func.now())
    
    def __repr__(self):
        return f'<Proof {self.id}: Hash {self.proof_hash[:10]}...>'

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), unique=True, nullable=False) 
    name = db.Column(db.String(100), nullable=False)
    mobile_number = db.Column(db.String(15), unique=True, nullable=False)
    email_id = db.Column(db.String(100), unique=True)
    password_hash = db.Column(db.String(255), nullable=False) 
    pincode = db.Column(db.String(10))
    landmark = db.Column(db.String(100))
    address = db.Column(db.Text)
    aadhar_number = db.Column(db.String(12), unique=True, nullable=False)
    profile_path = db.Column(db.String(255)) 
    
    def __repr__(self):
        return f'<User {self.user_id}: {self.name}>'

class Attachment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    grievance_id = db.Column(db.Integer, db.ForeignKey('grievance.id'), nullable=False)
    file_path = db.Column(db.String(255), nullable=False) 
    file_type = db.Column(db.String(50))

class Draft(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(255), db.ForeignKey('user.user_id'), nullable=False, unique=True)
    raw_text = db.Column(db.Text)
    location = db.Column(db.String(255))
    saved_at = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __repr__(self):
        return f'<Draft {self.user_id}>'

class Officer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    officer_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email_id = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False) 
    department = db.Column(db.String(100))
    pending_count = db.Column(db.Integer, default=0)
    resolved_count = db.Column(db.Integer, default=0)
    performance_score = db.Column(db.Float, default=95.0)

    def __repr__(self):
        return f'<Officer {self.officer_id}: {self.name}>'


def wait_for_db(max_retries=10, delay=6):
    print("Attempting to connect to database...")
    for i in range(max_retries):
        try:
            # Attempt to execute a simple operation (like getting engine info)
            with app.app_context():
                db.engine.connect()
            print("Database connected successfully!")
            return True
        except Exception as e:
            print(f"Database connection failed (Attempt {i+1}/{max_retries}): {e}")
            if i < max_retries - 1:
                time.sleep(delay)
    print("FATAL: Database connection failed after all retries.")
    return False

def init_db():
    with app.app_context():
        db.create_all()
        db.session.commit()
        Officer_Model = globals().get('Officer')
        if Officer_Model and Officer_Model.query.count() == 0:
            mock_officers = [
                Officer_Model(
                    officer_id='ENG_001', 
                    name='Smith', 
                    email_id='smith@rtgs.gov', 
                    password='password', 
                    department='Engineering'
                ),
                Officer_Model(
                    officer_id='HIN_002', 
                    name='Jane', 
                    email_id='jane@rtgs.gov', 
                    password='password', 
                    department='Health Inspection'
                )
            ]
            db.session.add_all(mock_officers)
            db.session.commit()
            print("MariaDB database tables created and mock officers populated!")
        else:
            print("✅ Database check complete. Tables exist and officers are present.")

def generate_user_id(aadhar, name):
    date_str = datetime.now().strftime("%Y%m%d")
    name_initials = "".join(n[0] for n in name.split()).upper()[:5] 
    return f"USER{aadhar[-4:]}{name_initials}{date_str}"

def generate_complaint_id(aadhar, complaint_count):
    date_str = datetime.now().strftime("%Y%m%d")
    count_str = str(complaint_count + 1).zfill(3) 
    return f"COMPLAINT{aadhar[-4:]}{date_str}{count_str}"

def image_to_base64(file):
    file.seek(0)
    return base64.b64encode(file.read()).decode('utf-8')

def calculate_dlt_hash(grievance_id, officer_id, cv_score, timestamp):
    data_string = f"{grievance_id}-{officer_id}-{cv_score}-{timestamp}"
    return hashlib.sha256(data_string.encode('utf-8')).hexdigest()

def call_gemini_ai(raw_text, location_tag):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return {
            'classification': "Error: API Key Missing",
            'professional_text': "Gemini API key is not set in environment variables.",
            'department_id': "ADM_003"
        }

    # 2. Define the System Instruction for the Model's Persona
    system_instruction = (
        "You are a highly efficient, multilingual Grievance Triage Agent for the AP Government's "
        "RTGS system. Your task is to analyze raw citizen complaints (which may include Telugu "
        "written in English script or code-switching), provide a specific classification, "
        "translate/transliterate the raw text for clarity, and output a professional, "
        "actionable summary for the concerned department head in a precise JSON format. "
        "The classification must be one of: 'Road Maintenance (Pothole)', 'Water Supply & Leakage', "
        "'Stray Dog Menace', 'Electrical (Streetlight Outage)', or 'General Municipal Service'. "
        "Assign the Department ID based on the classification: ENG_001 (Engineering/Roads/Electric), "
        "WTR_002 (Water), HIN_002 (Health/Nuisance), or ADM_003 (General/Admin)."
    )

    user_prompt = (
        f"Analyze the following citizen complaint submitted for the location: '{location_tag}'. "
        f"Original Complaint: '{raw_text}'. "
        "Please provide the output strictly in the requested JSON structure."
    )
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "classification": {"type": "STRING", "description": "The specific category of the grievance."},
            "department_id": {"type": "STRING", "description": "The target department ID based on the classification."},
            "raw_text_processed": {"type": "STRING", "description": "The original citizen text translated/cleaned for clarity (e.g., Telugu transliteration into English or clean Telugu script)."},
            "professional_text": {"type": "STRING", "description": "A formal, concise summary of the issue ready for the officer's report."}
        },
        "required": ["classification", "department_id", "raw_text_processed", "professional_text"]
    }
    payload = {
        "contents": [{"parts": [{"text": user_prompt}]}],
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        },
    }
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"
    
    try:
        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        response.raise_for_status()
        result = response.json()
        json_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '{}')
        try:
            parsed_json = json.loads(json_text)
            if 'classification' not in parsed_json:
                 raise ValueError("JSON structure missing expected key.")
                 
            return parsed_json
            
        except json.JSONDecodeError:
            print("Gemini Response Parsing Error: Output was not valid JSON.")
            return {
                'classification': "General Municipal Service",
                'professional_text': f"AI Parsing Failed. Raw text submitted: {raw_text[:100]}...",
                'department_id': "ADM_003"
            }


    except requests.exceptions.RequestException as e:
        print(f"Gemini API Request Failed: {e}")
        return {
            'classification': "Error: API Request Failed",
            'professional_text': f"Could not reach API service. Error: {e}",
            'department_id': "ADM_003"
        }
    except Exception as e:
        print(f"Unexpected Error in call_gemini_ai: {e}")
        return {
            'classification': "Error: Unexpected Failure",
            'professional_text': "An unhandled server exception occurred during AI processing.",
            'department_id': "ADM_003"
        }
    
# app.py (New Vision Validation Function)

def gemini_vision_validation(grievance_type, image_base64):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return 0.0, "API Key Missing for Vision Validation."
    system_instruction = (
        "You are a quick Image Validator for citizen complaints. "
        "Your task is to determine if the visual content of the provided image "
        "is directly related to the reported issue type. Score the image content's relevance. "
        "For example, if the reported issue is 'Road Maintenance (Pothole)', the image should clearly show a road issue, not a cat or a birthday cake. "
        "Provide a single confidence score (0.0 to 1.0) and a brief message in strict JSON format."
    )
    audit_prompt = (
        f"The reported grievance classification is: '{grievance_type}'. "
        "Analyze the provided image and rate its visual relevance to this classification. "
        "Score: 1.0 = Highly relevant; 0.0 = Not relevant/Unrelated photo."
    )
    contents = [
        {"parts": [
            {"text": audit_prompt},
            {"inlineData": {"mimeType": "image/jpeg", "data": image_base64}}
        ]}
    ]
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "score": {"type": "number", "description": "Visual relevance score (0.0 to 1.0)."},
            "message": {"type": "string", "description": "Concise validation message."}
        },
        "required": ["score", "message"]
    }
    
    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        },
    }

    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"
    
    try:
        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        response.raise_for_status() 
        
        result = response.json()
        json_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '{}')
        parsed_json = json.loads(json_text)
        
        return parsed_json.get('score', 0.0), parsed_json.get('message', 'Validation successful but response was generic.')

    except Exception as e:
        print(f"FATAL GEMINI VISION VALIDATION ERROR: {e}")
        return 0.0, f"Vision validation failed due to server error: {e}"

def gemini_cv_audit(grievance_type, after_image_base64, mock_gps, officer_id, before_image_path=None):
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        return 0.0, "API Key Missing for CV Audit."
    system_instruction = (
        "You are a Computer Vision Auditor for the AP Government's DLT Resolution System. "
        "Your task is to analyze the 'After' image provided by the officer and the original context "
        "(and 'Before' image, if provided). Verify if the grievance type appears RESOLVED in the 'After' image. "
        "Provide a single resolution score (0.0 to 1.0) and a concise audit message in strict JSON format. "
    )
    audit_prompt = (
        f"Grievance Type is: '{grievance_type}'. Officer ID: {officer_id}. "
        f"The officer claims the issue is resolved at {mock_gps}. "
        "Analyze the provided image and give a score and audit message. "
        "Score: 1.0 = Perfectly resolved; 0.0 = Clearly unresolved/unrelated photo."
    )
    contents = [
        {"parts": [
            {"text": audit_prompt},
            {"inlineData": {"mimeType": "image/jpeg", "data": after_image_base64}}
        ]}
    ]
    response_schema = {
        "type": "OBJECT",
        "properties": {
            "score": {"type": "number", "description": "Confidence score of resolution (0.0 to 1.0)."},
            "message": {"type": "string", "description": "Concise CV audit verification status."}
        },
        "required": ["score", "message"]
    }
    
    payload = {
        "contents": contents,
        "systemInstruction": {"parts": [{"text": system_instruction}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": response_schema
        },
    }
    api_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-05-20:generateContent?key={api_key}"
    
    try:
        response = requests.post(api_url, headers={'Content-Type': 'application/json'}, data=json.dumps(payload))
        response.raise_for_status() 
        
        result = response.json()
        json_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '{}')
        parsed_json = json.loads(json_text)
        
        return parsed_json.get('score', 0.0), parsed_json.get('message', 'CV analysis successful but response was generic.')

    except Exception as e:
        print(f"FATAL GEMINI CV AUDIT ERROR: {e}")
        return 0.0, f"Real-time CV Audit failed due to server error: {e}"

@app.route('/')
def home():
    return redirect(url_for('serve_login'))

@app.route('/login.html')
def serve_login():
    if session.get('logged_in'):
        return render_template('dashboard.html')
    return render_template('login.html')

@app.route('/dashboard.html')
def serve_dashboard():
    if not session.get('logged_in'):
        return render_template('login.html')
    return render_template('dashboard.html')

@app.route('/register.html')
def serve_register():
    return render_template('register.html')

@app.route('/officer_dashboard.html')
def serve_officer_dashboard():
    return render_template('officer_dashboard.html')

@app.route('/officer_login.html')
def officer_login_page():
    return render_template('officer_login.html')

@app.route('/audit.html')
def audit_page():
    return render_template('audit.html')

@app.route('/api/register', methods=['POST'])
def register_user():
    if 'profile' not in request.files:
         return jsonify({"message": "Profile picture is required."}), 400
    
    file = request.files['profile']
    data = request.form

    required_fields = ['name', 'mobile_number', 'email_id', 'password', 'confirm_password', 'aadhar_number']
    if any(field not in data for field in required_fields) or data['password'] != data['confirm_password']:
         return jsonify({"message": "Missing required fields or passwords do not match."}), 400
         
    user_id = generate_user_id(data['aadhar_number'], data['name'])
    aadhar_folder = data['aadhar_number']
    
    filename = secure_filename(file.filename)
    user_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'profile', aadhar_folder) 
    os.makedirs(user_dir, exist_ok=True) 
    profile_path = os.path.join(user_dir, filename)
    file.save(profile_path)
    
    hashed_password = generate_password_hash(data['password'])
    
    try:
        new_user = User(
            user_id=user_id,
            name=data['name'],
            mobile_number=data['mobile_number'],
            email_id=data['email_id'],
            password_hash=hashed_password,
            pincode=data.get('pincode'),
            landmark=data.get('landmark'),
            address=data.get('address'),
            aadhar_number=data['aadhar_number'],
            profile_path=profile_path
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({
            "message": "User registered successfully!",
            "user_id": user_id,
            "profile_stored_at": profile_path
        }), 201

    except Exception as e:
        db.session.rollback()
        if os.path.exists(profile_path): os.remove(profile_path)
        error_msg = str(e)
        if 'Duplicate entry' in error_msg:
             return jsonify({"message": "Registration failed: Mobile, Email, or Aadhar number already exists."}), 409
        return jsonify({"message": f"An unexpected database error occurred: {error_msg}"}), 500


@app.route('/api/login', methods=['POST'])
def login_user():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email and password are required."}), 400

    user = User.query.filter_by(email_id=email).first()

    if user and check_password_hash(user.password_hash, password):
        session['logged_in'] = True
        session['user_id'] = user.user_id 
        session['name'] = user.name
        
        return jsonify({
            "message": f"Successfully logged in! Welcome {user.name}",
            "success": True,
            "name": user.name,
            "user_id": user.user_id
        }), 200
    else:
        return jsonify({"message": "Invalid email or password.", "success": False}), 401 
    
@app.route('/api/officer/login', methods=['POST'])
def officer_login():
    """Authenticates the officer and sets the session."""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"message": "Email and password are required."}), 400

    officer = None
    
    try:
        with app.app_context():
            Officer_Model = globals().get('Officer')
            if Officer_Model:
                officer = Officer_Model.query.filter_by(email_id=email).first()
            else:
                raise Exception("Officer Model class not found in globals.")

    except Exception as e:
        print(f"FATAL DATABASE ERROR DURING OFFICER LOGIN: {e}")
        return jsonify({"message": "Server configuration error: Database Query Failed."}), 500

    if officer and officer.password == password: 

        session['logged_in_officer'] = True
        session['officer_id'] = officer.officer_id 
        session['officer_name'] = officer.name
        try:
             globals().get('Grievance') 
             globals().get('ResolutionProof') 
        except:
             print("WARNING: Failed to load secondary model classes globally.")

        return jsonify({
            "message": f"Welcome Officer {officer.name}",
            "success": True,
            "name": officer.name,
            "officer_id": officer.officer_id
        }), 200
    else:
        return jsonify({
            "message": "Invalid officer credentials.", 
            "success": False
        }), 401 

@app.route('/api/dashboard/kpi', methods=['GET'])
def get_user_kpis():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"message": "Access Denied. Please login."}), 401
    current_user_id = session['user_id']
    user = User.query.filter_by(user_id=current_user_id).first()
    if not user:
        return jsonify({"message": "User not found."}), 404
    total_count = Grievance.query.filter_by(user_id=current_user_id).count()
    resolved_count = Grievance.query.filter_by(user_id=current_user_id, status='RESOLVED').count()
    pending_count = Grievance.query.filter_by(user_id=current_user_id, status='PENDING').count()
    fake_count = Grievance.query.filter_by(user_id=current_user_id, status='FRAUD').count() 
    total_complaints = total_count
    reward_points = (resolved_count * 10) - (fake_count * 5)
    if reward_points < 0: reward_points = 0
    resolution_rate = f"{round((resolved_count / total_complaints) * 100)}%" if total_complaints > 0 else "0%"
    
    return jsonify({
        "user_name": user.name,
        "total_complaints": total_complaints,
        "resolved_complaints": resolved_count,
        "pending_complaints": pending_count,
        "fake_complaints": fake_count, 
        "reward_points": reward_points, 
        "resolution_rate": resolution_rate,
        "avg_resolution_days": 3,
        "customer_score": "92%", 
        "rag_status": "GREEN"
    }), 200


@app.route('/api/grievances/submit', methods=['POST'])
def submit_grievance():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"message": "Access Denied. Please login to submit a grievance."}), 401
    
    current_user_id = session['user_id']
    user = User.query.filter_by(user_id=current_user_id).first()
    raw_text = request.form.get('raw_text')
    location_tag = request.form.get('location')
    files = request.files.getlist('proof_photos')

    if not raw_text or not location_tag:
        return jsonify({"message": "Complaint details and location are required."}), 400
    ai_results = call_gemini_ai(raw_text, location_tag)
    
    if 'Error' in ai_results['classification']:
        return jsonify(ai_results), 500
    
    classification = ai_results['classification']
    if files and files[0].filename:
        main_proof_file = files[0]
        try:
            image_base64_data = image_to_base64(main_proof_file)
            main_proof_file.seek(0)
        except Exception:
            return jsonify({"message": "File processing error during Base64 conversion."}), 500
        vision_score, vision_message = gemini_vision_validation(classification, image_base64_data)
        if vision_score < 0.5:
            return jsonify({
                "message": "Fraud Detection: Visual evidence mismatch. Score below 50%.",
                "reason": f"Image validation failed ({vision_message}). Content is unrelated to '{classification}'.",
                "classification": "FRAUD_REJECTED"
            }), 400
    complaint_count = Grievance.query.count() + 1 
    complaint_id = f"COMPLAINT{user.aadhar_number[-4:]}{datetime.now().strftime('%Y%m%d%H%M%S')}{complaint_count}"
    try:
        new_grievance = Grievance(
            user_id=current_user_id, 
            complaint_id=complaint_id,
            raw_text=raw_text,
            raw_text_processed=ai_results['raw_text_processed'],
            professional_text=ai_results['professional_text'],
            grievance_type=classification,
            location_tag=location_tag,
            assigned_officer_id=ai_results['department_id'], 
            status='PENDING' 
        )
        db.session.add(new_grievance)
        db.session.flush() 
        grievance_db_id = new_grievance.id 
        if files and files[0].filename:
            upload_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'grievance', complaint_id)
            os.makedirs(upload_dir, exist_ok=True)
            
            for file in files:
                if file.filename:
                    file.seek(0) 
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(upload_dir, filename)
                    file.save(file_path)
                    
                    new_attachment = Attachment(
                        grievance_id=new_grievance.id, 
                        file_path=file_path,
                        file_type=file.content_type
                    )
                    db.session.add(new_attachment)
        db.session.commit()
        return jsonify({
            "message": "Grievance submitted and AI classified successfully!",
            "grievance_id": complaint_id,
            "status": new_grievance.status,
            "classification": new_grievance.grievance_type
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"DATABASE SUBMISSION FAILED: {str(e)}")
        return jsonify({"message": "Submission Failed: Database Error. Please check Flask console."}), 500

@app.route('/api/grievances/me', methods=['GET'])
def get_user_grievances():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"message": "Access Denied. Please login to view grievances."}), 401
    
    current_user_id = session['user_id']
    category_filter = request.args.get('category')
    status_filter = request.args.get('status')
    query = Grievance.query.filter_by(user_id=current_user_id)
    
    if category_filter and category_filter != 'All Categories':
        query = query.filter_by(grievance_type=category_filter)
    
    if status_filter and status_filter != 'All':
        query = query.filter_by(status=status_filter.upper())
    grievances = query.order_by(Grievance.created_at.desc()).all()
    grievance_list = []
    for g in grievances:
        attachments_info = [
            {'id': a.id, 'file_path': a.file_path, 'file_type': a.file_type}
            for a in g.attachments
        ]
        
        grievance_list.append({
            'id': g.id,
            'complaint_id': g.complaint_id,
            'type': g.grievance_type,
            'raw_text': g.raw_text,
            'professional_text': g.professional_text,
            'location': g.location_tag,
            'status': g.status,
            'created_at': g.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            'attachments': attachments_info
        })
            
    return jsonify(grievance_list), 200

@app.route('/api/preview_ai', methods=['POST'])
def preview_ai_classification():
    raw_text = request.form.get('raw_text')
    location_tag = request.form.get('location')

    if not raw_text:
        return jsonify({"message": "Text input is required for AI preview."}), 400
    ai_results = call_gemini_ai(raw_text, location_tag)
    if 'Error' in ai_results['classification']:
        return jsonify(ai_results), 500
    return jsonify({
        "classification": ai_results['classification'],
        "professional_text": ai_results['professional_text'],
        "message": "AI analysis complete."
    }), 200

@app.route('/api/draft/save', methods=['POST'])
def save_draft():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"message": "Unauthorized"}), 401
    
    current_user_id = session['user_id']
    data = request.get_json()
    draft = Draft.query.filter_by(user_id=current_user_id).first()
    
    try:
        if draft:
            draft.raw_text = data.get('raw_text', '')
            draft.location = data.get('location', '')
        else:
            draft = Draft(
                user_id=current_user_id,
                raw_text=data.get('raw_text', ''),
                location=data.get('location', '')
            )
            db.session.add(draft)
            
        db.session.commit()
        return jsonify({"message": "Draft saved automatically", "saved_at": draft.saved_at.strftime("%H:%M:%S")}), 200

    except Exception as e:
        db.session.rollback()
        print(f"DRAFT SAVE FAILED: {str(e)}")
        return jsonify({"message": "Draft save failed internally."}), 500


@app.route('/api/draft/load', methods=['GET'])
def load_draft():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"message": "Unauthorized"}), 401
    
    current_user_id = session['user_id']
    draft = Draft.query.filter_by(user_id=current_user_id).first()
    
    if draft:
        return jsonify({
            "raw_text": draft.raw_text,
            "location": draft.location,
            "saved_at": draft.saved_at.strftime("%H:%M:%S")
        }), 200
    else:
        return jsonify({"message": "No draft found."}), 404


@app.route('/api/draft/delete', methods=['POST'])
def delete_draft():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({"message": "Unauthorized"}), 401
    
    current_user_id = session['user_id']
    draft = Draft.query.filter_by(user_id=current_user_id).first()
    
    try:
        if draft:
            db.session.delete(draft)
            db.session.commit()
            return jsonify({"message": "Draft deleted."}), 200
        else:
            return jsonify({"message": "No draft to delete."}), 404
            
    except Exception as e:
        db.session.rollback()
        print(f"DRAFT DELETE FAILED: {str(e)}")
        return jsonify({"message": "Draft delete failed."}), 500
@app.route('/api/resolution/submit/<int:grievance_id>', methods=['POST'])
def submit_resolution(grievance_id):
    if 'logged_in_officer' not in session or not session['logged_in_officer']:
        return jsonify({"message": "Unauthorized access. Officer login required."}), 401

    try:
        grievance = Grievance.query.get(grievance_id)
        if not grievance or grievance.status != 'PENDING':
            return jsonify({"message": "Grievance not found or already resolved."}), 404

        officer_id = session['officer_id']
        file = request.files.get('resolution_proof')
        mock_gps = request.form.get('mock_gps', '17.72, 83.30')
        
        if not file:
            return jsonify({"message": "Resolution proof file is required."}), 400
        file_bytes = file.read()
        file_hash = hashlib.sha256(file_bytes + mock_gps.encode('utf-8') + officer_id.encode('utf-8')).hexdigest()
        
        after_image_base64 = image_to_base64(file)
        cv_score, cv_analysis_message = gemini_cv_audit(
            grievance.grievance_type, 
            after_image_base64, 
            mock_gps, 
            officer_id
        )
        file.seek(0) 
        file_bytes = file.read()
        file_hash = hashlib.sha256(file_bytes + mock_gps.encode('utf-8') + officer_id.encode('utf-8')).hexdigest()
        is_fraudulent = False
        fraud_reason = None
        if '1.0, 1.0' in mock_gps:
            is_fraudulent = True
            fraud_reason = "Geo-fencing breach detected."
            cv_score = 0.01 
        if cv_score < 0.30 and not is_fraudulent:
             is_fraudulent = True
             fraud_reason = f"Low CV Confidence Score ({cv_score*100:.0f}%) detected: {cv_analysis_message}"

        if is_fraudulent:
            grievance.status = 'FRAUD'
            grievance.fake_flag_reason = fraud_reason
            db.session.commit()
            return jsonify({
                "message": f"Resolution flagged as potential fraud: {fraud_reason}", 
                "reason": fraud_reason
            }), 409 
        new_proof = ResolutionProof(
            grievance_id=grievance.id,
            officer_id=officer_id,
            cv_score=cv_score,
            is_fraudulent=is_fraudulent,
            proof_hash=file_hash
        )
        db.session.add(new_proof)
        grievance.status = 'RESOLVED'
        officer = Officer.query.filter_by(officer_id=officer_id).first()
        if officer:
             officer.resolved_count = (officer.resolved_count or 0) + 1
             officer.performance_score = min(100, 95 + (officer.resolved_count * 1))

        db.session.commit()

        return jsonify({
            "message": "Resolution successfully committed to DLT Ledger.",
            "proof_hash": file_hash,
            "status": "RESOLVED"
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"RESOLUTION SUBMISSION FAILED: {str(e)}")
        return jsonify({"message": "An internal server error occurred during resolution."}), 500
    
    
@app.route('/api/officer/logout', methods=['POST'])
def officer_logout():
    """Logs out the officer by clearing session variables."""
    session.pop('logged_in_officer', None)
    session.pop('officer_id', None)
    session.pop('officer_name', None)
    return jsonify({"message": "Successfully logged out."}), 200

@app.route('/api/officer/dashboard', methods=['GET'])
def officer_dashboard():
    if 'logged_in_officer' not in session or not session['logged_in_officer']:
        return jsonify({"message": "Unauthorized access."}), 401
    
    officer_id = session['officer_id']
    sort_by = request.args.get('sort_by', 'newest')
    filter_seriousness = request.args.get('seriousness', 'ALL')

    try:
        Officer_Model = globals().get('Officer')
        Grievance_Model = globals().get('Grievance')
        Attachment_Model = globals().get('Attachment')
            
        officer = Officer_Model.query.filter_by(officer_id=officer_id).first()
        if not officer:
            return jsonify({"message": "Officer account not found."}), 404
        base_query = Grievance_Model.query.filter_by(assigned_officer_id=officer_id)
        total_assigned_count = base_query.count()
        pending_count = base_query.filter(Grievance_Model.status.in_(['PENDING', 'REOPENED'])).count()
        resolved_count = base_query.filter_by(status='RESOLVED').count()
        fraud_count = base_query.filter_by(status='FRAUD').count()
        filtered_query = Grievance_Model.query.filter_by(assigned_officer_id=officer_id)
        if filter_seriousness == 'IMMEDIATE':
            filtered_query = filtered_query.filter(Grievance_Model.raw_text.ilike('%pothole%') | Grievance_Model.raw_text.ilike('%leakage%'))
        elif filter_seriousness == 'STANDARD':
            filtered_query = filtered_query.filter(~(Grievance_Model.raw_text.ilike('%pothole%') | Grievance_Model.raw_text.ilike('%leakage%')))
        if sort_by == 'oldest':
            filtered_query = filtered_query.order_by(Grievance_Model.created_at.asc())
        else:
            filtered_query = filtered_query.order_by(Grievance_Model.created_at.desc())
        grievances_to_display = filtered_query.all()
        grievance_list = []
        for g in grievances_to_display:
            attachments = Attachment_Model.query.filter_by(grievance_id=g.id).all()
            attachments_info = [
                {'id': a.id, 'file_path': a.file_path, 'file_type': a.file_type}
                for a in attachments
            ]
            
            grievance_list.append({
                'id': g.id,
                'complaint_id': g.complaint_id,
                'grievance_type': g.grievance_type, 
                'location_tag': g.location_tag,
                'raw_text': g.raw_text,
                'professional_text': g.professional_text,
                'status': g.status,
                'created_at': g.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'attachment_path': attachments[0].file_path if attachments else None
            })

        return jsonify({
            "officer_name": officer.name,
            "officer_id": officer.officer_id,
            "department": officer.department,
            "kpis": {
                "total_assigned": total_assigned_count, 
                "pending": pending_count, 
                "resolved": resolved_count, 
                "fraud_count": fraud_count, 
                "performance_score": officer.performance_score
            },
            "grievances": grievance_list
        }), 200

    except Exception as e:
        print(f"ERROR FETCHING OFFICER DASHBOARD: {e}")
        return jsonify({"message": f"Internal server error while fetching dashboard data: {e}"}), 500

@app.route('/uploads/<path:filename>')
def serve_uploads(filename):
    if filename.startswith('complaints/'):
        base_dir = os.path.abspath(os.path.join(app.config['COMPLAINT_UPLOAD_FOLDER'], '..'))
        filename_to_serve = os.path.join('complaints', filename.split('complaints/', 1)[1])
        
    elif filename.startswith('profile/'):
        base_dir = os.path.abspath(os.path.join(app.config['UPLOAD_FOLDER'], '..', 'profile')) 
        filename_to_serve = os.path.join('profile', filename.split('profile/', 1)[1])
        
    else:
        base_dir = os.path.abspath(app.root_path)
        filename_to_serve = filename
        
    try:
        return send_from_directory(
            os.path.join(app.root_path, 'uploads'), 
            as_attachment=False
        )
    except FileNotFoundError:
        print(f"File not found: {filename}")
        return jsonify({"message": "Image file not found on server."}), 404
    except Exception as e:
        print(f"Error serving file {filename}: {e}")
        return jsonify({"message": "Server error while accessing file."}), 500

@app.route('/api/public/audit/<string:complaint_id>', methods=['GET'])
def public_dlt_audit(complaint_id):
    Grievance_Model = globals().get('Grievance')
    ResolutionProof_Model = globals().get('ResolutionProof')
    Attachment_Model = globals().get('Attachment')
    Officer_Model = globals().get('Officer') 
    
    grievance = Grievance_Model.query.filter_by(complaint_id=complaint_id).first()
    
    if not grievance:
        return jsonify({"message": f"Complaint ID {complaint_id} not found."}), 404
    seriousness_tag = "IMMEDIATE" if "pothole" in grievance.raw_text.lower() or "leakage" in grievance.raw_text.lower() else "STANDARD"
    proof = ResolutionProof_Model.query.filter_by(grievance_id=grievance.id).first()
    audit_data = {
        "complaint_id": grievance.complaint_id,
        "status": grievance.status,
        "grievance_type": grievance.grievance_type,
        "professional_summary": grievance.professional_text,
        "seriousness": seriousness_tag
    }

    if grievance.status == 'RESOLVED' or grievance.status == 'FRAUD':
        if not proof:
             return jsonify({"message": "Resolution status logged, but DLT proof record is missing."}), 500
             
        officer = Officer_Model.query.filter_by(officer_id=proof.officer_id).first()
        officer_name = officer.name if officer else proof.officer_id 
        attachments = Attachment_Model.query.filter_by(grievance_id=grievance.id).all()
        resolution_proofs = []
        citizen_proofs = []
        
        for a in attachments:
            attachment_info = {'file_path': a.file_path, 'file_type': a.file_type}
            if a.file_type == 'resolution_photo':
                resolution_proofs.append(attachment_info)
            else:
                citizen_proofs.append(attachment_info)

        audit_data['dlt_proof'] = {
            "proof_hash": proof.proof_hash,
            "verified_at": proof.verified_at.strftime("%Y-%m-%d %H:%M:%S"),
            "officer_id": proof.officer_id,
            "officer_name": officer_name, 
            "cv_score": proof.cv_score,
            "is_fraudulent": proof.is_fraudulent,
        }
        
        audit_data['resolution_attachments'] = resolution_proofs 
        audit_data['citizen_attachments'] = citizen_proofs     

    return jsonify(audit_data), 200

@app.route('/api/complaint/<int:grievance_id>', methods=['GET'])
def get_complaint_details(grievance_id):
    if 'logged_in_officer' not in session and 'logged_in' not in session:
        return jsonify({"message": "Unauthorized access. Please log in."}), 401

    with app.app_context():
        Grievance_Model = globals().get('Grievance')
        User_Model = globals().get('User')
        
        grievance = Grievance_Model.query.get(grievance_id)
        if not grievance:
            return jsonify({"message": "Grievance not found."}), 404

        user = User_Model.query.filter_by(user_id=grievance.user_id).first()

        citizen_details = {
            'name': user.name,
            'mobile': user.mobile_number,
            'email': user.email_id,
            'address': f"{user.address}, {user.landmark}, {user.pincode}",
            'aadhar_last_4': user.aadhar_number[-4:] if user.aadhar_number else 'N/A'
        }
        attachments_info = [
            {'file_path': a.file_path, 'file_type': a.file_type}
            for a in grievance.attachments
        ]
        seriousness_tag = "IMMEDIATE" if "pothole" in grievance.raw_text.lower() or "leakage" in grievance.raw_text.lower() else "STANDARD"

        return jsonify({
            'grievance': {
                'id': grievance.complaint_id,
                'grievance_type': grievance.grievance_type,
                'raw_text': grievance.raw_text,
                'professional_text': grievance.professional_text, 
                'location_tag': grievance.location_tag,
                'filed_at': grievance.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                'seriousness': seriousness_tag, 
                'attachments': attachments_info
            },
            'citizen': citizen_details
        }), 200

@app.route('/api/officer/resolve_grievance', methods=['POST'])
def resolve_grievance():
    if 'logged_in_officer' not in session or not session['logged_in_officer']:
        return jsonify({"message": "Access Denied. Officer login required."}), 401
    
    officer_id = session['officer_id']
    complaint_id = request.form.get('complaint_id')
    mock_gps = request.form.get('mock_gps', '17.3850,78.4867') 
    
    if 'after_photo' not in request.files:
        return jsonify({"message": "Resolution 'After' photo is required."}), 400
    
    after_file = request.files['after_photo']
    Grievance_Model = globals().get('Grievance')
    Officer_Model = globals().get('Officer')
    
    grievance = Grievance_Model.query.filter_by(complaint_id=complaint_id).first()
    if not grievance:
        return jsonify({"message": "Grievance not found."}), 404
    
    if grievance.status == 'RESOLVED':
        return jsonify({"message": "Grievance is already marked resolved."}), 400
    if grievance.assigned_officer_id != officer_id:
        return jsonify({"message": "Unauthorized: Grievance not assigned to this officer."}), 403
    try:
        after_file_base64 = image_to_base64(after_file)
        after_file.seek(0)
    except Exception as e:
        print(f"Base64 Conversion Error: {e}")
        return jsonify({"message": "File processing error during Base64 conversion."}), 500

    cv_score, cv_message = gemini_cv_audit(
        grievance.grievance_type, 
        after_file_base64, 
        mock_gps, 
        officer_id
    )
    
    is_fraudulent = cv_score < 0.7 
    status_update = 'FRAUD' if is_fraudulent else 'RESOLVED'
    
    try:
        COMPLAINT_UPLOAD_FOLDER = 'uploads/complaints'
        upload_dir = os.path.join(COMPLAINT_UPLOAD_FOLDER, complaint_id, 'resolution_proofs')
        os.makedirs(upload_dir, exist_ok=True)
        after_filename = secure_filename(after_file.filename)
        after_file_path = os.path.join(upload_dir, after_filename)
        after_file.save(after_file_path)
        current_time = datetime.now()
        proof_hash = calculate_dlt_hash(grievance.complaint_id, officer_id, cv_score, current_time.isoformat())
        ResolutionProof_Model = globals().get('ResolutionProof')
        new_proof = ResolutionProof_Model(
            grievance_id=grievance.id,
            officer_id=officer_id,
            cv_score=cv_score,
            is_fraudulent=is_fraudulent,
            proof_hash=proof_hash,
            verified_at=current_time
        )
        db.session.add(new_proof)

        ResolutionProof_Model = globals().get('ResolutionProof')
        Attachment_Model = globals().get('Attachment') 
        
        new_resolution_attachment = Attachment_Model(
            grievance_id=grievance.id,
            file_path=after_file_path,
            file_type='resolution_photo'
        )
        db.session.add(new_resolution_attachment)
        grievance.status = status_update
        grievance.resolved_at = current_time 
        officer = Officer_Model.query.filter_by(officer_id=officer_id).first()
        if officer:
            if status_update == 'RESOLVED':
                officer.resolved_count += 1
                officer.pending_count = max(0, officer.pending_count - 1)
            else: 
                officer.performance_score = max(0, officer.performance_score - 5) 

        db.session.commit()

        return jsonify({
            "message": f"Resolution logged and verified. Status: {status_update}",
            "dlt_hash": proof_hash,
            "cv_score": cv_score,
            "cv_message": cv_message,
            "is_fraudulent": is_fraudulent
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error resolving grievance and creating proof: {e}")
        return jsonify({"message": f"Server error during resolution logging: {str(e)}"}), 500

@app.route('/api/grievance/delete/<int:grievance_id>', methods=['POST'])
def soft_delete_grievance(grievance_id):
    if 'logged_in_officer' not in session:
        return jsonify({"message": "Unauthorized access."}), 401
    
    grievance = Grievance.query.get(grievance_id)
    if not grievance:
        return jsonify({"message": "Grievance not found."}), 404
    if grievance.status not in ['RESOLVED', 'FRAUD']:
        return jsonify({"message": f"Cannot delete; status is {grievance.status}."}), 400
        
    try:
        grievance.status = 'DELETED'
        db.session.commit()
        return jsonify({"message": f"Grievance {grievance_id} soft-deleted successfully."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Server error during deletion: {str(e)}"}), 500

@app.route('/api/restore/deleted', methods=['GET'])
def fetch_deleted_grievances():
    if 'logged_in_officer' not in session:
        return jsonify({"message": "Unauthorized access."}), 401
        
    try:
        deleted_grievances = Grievance.query.filter_by(status='DELETED').order_by(Grievance.resolved_at.desc()).all()
        
        grievance_list = []
        for g in deleted_grievances:
            grievance_list.append({
                "id": g.id,
                "complaint_id": g.complaint_id,
                "grievance_type": g.grievance_type,
                "professional_text": g.professional_text,
                "resolved_at": g.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if g.resolved_at else "N/A"
            })
            
        return jsonify({"deleted_grievances": grievance_list}), 200
    except Exception as e:
        return jsonify({"message": f"Error fetching deleted list: {str(e)}"}), 500

@app.route('/api/grievance/restore/<int:grievance_id>', methods=['POST'])
def restore_grievance(grievance_id):
    if 'logged_in_officer' not in session:
        return jsonify({"message": "Unauthorized access."}), 401
    
    grievance = Grievance.query.get(grievance_id)
    if not grievance or grievance.status != 'DELETED':
        return jsonify({"message": "Grievance not found or not marked as deleted."}), 404
        
    try:
        proof = ResolutionProof.query.filter_by(grievance_id=grievance.id).first()
        
        if proof and proof.is_fraudulent:
            grievance.status = 'FRAUD'
        else:
            grievance.status = 'RESOLVED'
            
        db.session.commit()
        return jsonify({"message": f"Grievance {grievance_id} restored to {grievance.status} successfully."}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"message": f"Server error during restoration: {str(e)}"}), 500

@app.route('/restore_dashboard.html')
def serve_restore_dashboard():
    return render_template('restore_dashboard.html')

@app.route('/api/logout', methods=['POST'])
def logout_user():
    if 'user_id' in session:
        session.pop('user_id', None)
    if 'name' in session:
        session.pop('name', None)
    session.pop('logged_in', None)
    return jsonify({"message": "Logged out successfully."}), 200

@app.route('/health')
def health_check():
    # Example route to check if the DB is actually working
    if engine is not None:
        try:
            with engine.connect():
                return {"status": "ok", "db_status": "connected"}
        except:
            return {"status": "ok", "db_status": "connection_error"}
    return {"status": "ok", "db_status": "not_configured"}

def initialize_database():
    """Initializes directories and ensures database tables are created."""
    global UPLOAD_FOLDER, COMPLAINT_UPLOAD_FOLDER
    
    # 1. Create upload directories
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(COMPLAINT_UPLOAD_FOLDER, exist_ok=True)
    
    # 2. Wait for DB and call init_db()
    if wait_for_db():
        init_db()
    else:
        # If DB connection fails after retries, log a severe error
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("FATAL ERROR: APPLICATION IS STARTING WITHOUT DATABASE CONNECTION.")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

# CRITICAL FOR GUNICORN/RENDER DEPLOYMENT: 
# The function is called here (outside of the __main__ guard) 
# to ensure the wait loop and DB initialization run before Gunicorn boots workers.
initialize_database()

if __name__ == '__main__':
    app.run(debug=True)




