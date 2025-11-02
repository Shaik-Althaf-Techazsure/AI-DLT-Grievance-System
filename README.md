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
