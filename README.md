Invoice Reimbursement Analysis API
A FastAPI-based service that analyzes invoice reimbursements against company policies using Google's Gemini LLM.
Features

FastAPI Backend: High-performance async API
Policy Analysis: Compare invoices against company policy documents
Multi-format Support: Process .docx policies and PDF invoices in ZIP archives
AI-powered Analysis: Uses Google Gemini for intelligent invoice assessment
Comprehensive Reporting: Detailed analysis with reimbursement decisions

Quick Start
1. Installation
bash# Clone or create the project directory
mkdir invoice_reimbursement_api
cd invoice_reimbursement_api

# Install dependencies
pip install -r requirements.txt
2. Environment Setup

Get a Google Gemini API key from Google AI Studio
Create a .env file and add your API key:

envGEMINI_API_KEY=your_actual_gemini_api_key_here
3. Running the Application
bash# Start the development server
python main.py

# Or use uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000
The API will be available at http://localhost:8000
API Documentation
Interactive Documentation

Swagger UI: http://localhost:8000/docs
ReDoc: http://localhost:8000/redoc

Endpoints
POST /analyze-invoices
Analyze invoices against company policy.
Request:

policy_file: Company policy document (.docx file)
invoice_zip: ZIP file containing invoice PDFs

Response:
json{
  "policy_file": "Policy-Nov2024.pdf.docx",
  "invoice_zip": "Cab Bills.zip",
  "total_invoices": 3,
  "analysis_results": [
    {
      "invoice": "cab_receipt1.pdf",
      "status": "Fully Reimbursed",
      "amount": 250,
      "reason": "Within policy limits for local transportation"
    },
    {
      "invoice": "cab_receipt2.pdf",
      "status": "Partially Reimbursed",
      "amount": 500,
      "reason": "Exceeds daily cab limit of $500, reimbursing maximum allowed"
    }
  ],
  "summary": {
    "fully_reimbursed": 1,
    "partially_reimbursed": 1,
    "declined": 0,
    "errors": 0,
    "total_reimbursable_amount": 750
  }
}
GET /
Health check endpoint
GET /health
Detailed health status
Usage Examples
Using cURL
bashcurl -X POST "http://localhost:8000/analyze-invoices" \
  -F "policy_file=@Policy-Nov2024.pdf.docx" \
  -F "invoice_zip=@Cab Bills.zip"
Using Python requests
pythonimport requests

url = "http://localhost:8000/analyze-invoices"

with open("Policy-Nov2024.pdf.docx", "rb") as policy_file, \
     open("Cab Bills.zip", "rb") as invoice_zip:
    
    files = {
        "policy_file": policy_file,
        "invoice_zip": invoice_zip
    }
    
    response = requests.post(url, files=files)
    result = response.json()
    print(result)
File Structure
invoice_reimbursement_api/
│
├── main.py                # FastAPI application
├── utils.py               # Text extraction utilities
├── prompt.txt             # Gemini prompt template
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables
├── README.md              # This file
│
└── test_data/             # Sample data (optional)
    ├── Policy-Nov2024.pdf.docx
    ├── Cab Bills.zip
    ├── Meal Invoice.zip
    └── Travel Bill.zip
How It Works

File Upload: Users upload a policy document (.docx) and invoice ZIP file
Text Extraction:

Policy text extracted using python-docx
Invoice PDFs extracted using PyMuPDF (fitz)


AI Analysis: Each invoice is analyzed against the policy using Google Gemini
Decision Making: Gemini determines reimbursement status and amount
Response: Structured JSON response with detailed analysis

Analysis Categories
The system categorizes each invoice as:

Fully Reimbursed: All items comply with policy
Partially Reimbursed: Some items exceed limits but are otherwise valid
Declined: Contains non-reimbursable items or violates policy
Error: Technical issues during processing

Configuration Options
Environment Variables
env# Required
GEMINI_API_KEY=your_key_here

# Optional
DEBUG=True
LOG_LEVEL=INFO
MAX_REQUESTS_PER_MINUTE=60
MAX_POLICY_FILE_SIZE=10
MAX_ZIP_FILE_SIZE=50
Customizing the Prompt
Edit prompt.txt to modify how Gemini analyzes invoices. The template supports:

Policy-specific rules
Custom expense categories
Different approval workflows
Various reimbursement criteria

Error Handling
The API handles various error scenarios:

Invalid file formats
Corrupted files
Missing API keys
Network timeouts
Empty documents
Large file uploads

Performance Considerations

Async Processing: Uses FastAPI's async capabilities
Efficient PDF Processing: PyMuPDF for fast text extraction
Minimal API Calls: One Gemini call per invoice
Memory Management: Streams large files without loading entirely

Security Features

File type validation
Content verification
Size limits
Error sanitization
Environment variable protection

Development
Adding New Features

Custom Extractors: Add new text extraction methods in utils.py
Enhanced Prompts: Modify prompt.txt for better analysis
Additional Endpoints: Extend main.py with new functionality
Validation Rules: Add business logic validation

Testing
bash# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run tests (if test files are added)
pytest
Troubleshooting
Common Issues

"GEMINI_API_KEY not found"

Ensure .env file exists with valid API key
Check API key is active in Google AI Studio


"No PDF files found in zip"

Verify ZIP contains PDF files
Check file permissions and format


"Policy document appears empty"

Ensure .docx file is valid and contains text
Try opening file manually to verify content


Import errors

Run pip install -r requirements.txt
Check Python version compatibility (3.8+)



Logging
Enable detailed logging by setting LOG_LEVEL=DEBUG in .env:
bash# View logs in real-time
tail -f app.log
License
MIT License - feel free to use and modify for your needs.
Contributing

Fork the repository
Create a feature branch
Add tests for new functionality
Submit a pull request

Support
For issues and questions:

Check the troubleshooting section
Review API documentation at /docs
Enable debug logging for detailed error information