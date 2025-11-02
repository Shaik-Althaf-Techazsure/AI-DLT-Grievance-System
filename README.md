**RTGS V2.0: The Trust Ledger (AI & DLT Grievance System)**

**Ending Fake Government Closures**

This project is a comprehensive, multi-modal, multi-lingual grievance redressal system built for the Andhra Pradesh government (RTGS) to address the critical lack of transparency and trust caused by fraudulent resolution claims.

We leverage Gemini AI for intelligent intake and use Distributed Ledger Technology (DLT) to provide publicly auditable proof that a complaint has been physically and correctly resolved.

**Key Feature  -  Outcome  -  Status**

Zero-Fraud Verification  -  Officer resolution photos are validated on-site via Geo-tagging and backend Computer Vision (CV).  -  Implemented

DLT Immutability  -  Cryptographic hash of the resolution proof is logged, making it auditable by any citizen.  -  Implemented

Multi-Modal Intake  -  Processing of audio, images (OCR), and multi-lingual text (Telugu/English).  -  Implemented

Archive/Restore System  -  Officers can soft-delete records, and citizens can view the archive, ensuring data integrity.  -  Implemented

**1. Problem Statement**

The traditional system is plagued by slow manual processing and the rampant issue of "Fake Closures"—officers marking an issue resolved without remediation. This leads to massive resource waste, zero accountability, and a severe erosion of citizen trust.

**2. Technology Stack**

**Component  -  Technology  -  Role**

I. **AI Agent**  -  Google Gemini API (Gemini 2.5 Flash)  -  Handles NLP (classification, translation/professionalizing raw text) and Computer Vision (CV) for resolution photo validation.

II. **Backend/API**  -  Python (Flask)  -  REST API server, business logic, session management, and DLT hash generation.

III. **Database**  -  MariaDB (SQLAlchemy)  -  Persistent storage for user profiles, grievance records, and immutable DLT Proofs.

IV. **Frontend**  -  HTML, Tailwind CSS, JavaScript  -  Two dashboards (Citizen & Officer) and a public Audit Portal.


**3. System Architecture (End to End Flow)**

<img width="1417" height="823" alt="Citizen_login" src="https://github.com/user-attachments/assets/7d3f9264-8a11-4665-92b5-929e364cacfd" />

It is the login where the citizen will login

<img width="1400" height="881" alt="Citizen_1" src="https://github.com/user-attachments/assets/4bb1e929-eba4-471c-bc5f-72c857d996c2" />

<img width="1382" height="631" alt="Citizen_2" src="https://github.com/user-attachments/assets/80f14ee4-c3cc-4a4c-a5f0-169a4fb0ec97" />

1. Citizen Submission: Citizen uses dashboard.html to submit a grievance (raw text + photo/video).

<img width="1370" height="685" alt="Citizen_3" src="https://github.com/user-attachments/assets/84710b10-f36f-4f84-86e6-4c244baf344c" />


2. AI Triage (Classification): The Flask backend calls the Gemini API. Gemini classifies the complaint (e.g., Road Maintenance), refines the text into a professional summary, and assigns the appropriate Officer ID (e.g., ENG_001).

![Uploading officer_5.png…]()


3. Visual Fraud Check: Gemini CV validates the citizen's initial photo to ensure it matches the complaint type (e.g., prevents submitting a photo of a cat for a pothole).

<img width="801" height="880" alt="Officer_3" src="https://github.com/user-attachments/assets/785a293e-38ae-4a68-964d-f2c677eee6e4" />

<img width="1427" height="745" alt="Officer_1" src="https://github.com/user-attachments/assets/5f8da85b-b2b4-4a92-830d-369514a1dfcb" />

4. Officer Resolution: The assigned officer logs into officer_dashboard.html, views the task, and submits the "After" photo via the mobile process.

<img width="1920" height="1080" alt="officer_6" src="https://github.com/user-attachments/assets/57e15a22-f5d7-48bf-963f-ef29ac363600" />

5. DLT Verification: The backend runs a final Gemini CV Audit on the officer's photo (checking for geo-fencing match and actual resolution).

<img width="1506" height="963" alt="Citizen_4" src="https://github.com/user-attachments/assets/221029ba-42a6-49c4-b21c-8ec8ba682de2" />


6. Ledger Commit: The system calculates a secure SHA-256 Hash from the proof data, commits it to the ResolutionProof table, and logs the image path in the Attachment table with the tag 'resolution_photo'.

<img width="986" height="852" alt="citizen_5" src="https://github.com/user-attachments/assets/46a0691c-c179-4d21-bc62-bbf603f47612" />


7. Public Audit: Any citizen can enter the Complaint ID into audit.html to view the officer's photo, the verification score, and the immutable DLT Hash, ensuring full transparency.

**4. Quick Start (Local Setup)**
