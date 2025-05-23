from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import zipfile
import io
import os
import random
from typing import List, Dict, Any
from utils import extract_text_from_docx, extract_text_from_pdf, load_prompt_template
import google.generativeai as genai
from dotenv import load_dotenv
import json
import logging

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Invoice Reimbursement Analysis API",
    description="Analyze invoice reimbursements against company policy using Google Gemini",
    version="1.0.0"
)

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup"""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.error("GEMINI_API_KEY not found in environment variables")
            logger.info("Please ensure you have set GEMINI_API_KEY in your .env file")
            raise ValueError("GEMINI_API_KEY is required")
        
        # Test Gemini connection
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            test_response = model.generate_content("Hello, this is a test.")
            logger.info("Gemini API connection successful")
        except Exception as gemini_error:
            logger.error(f"Failed to connect to Gemini API: {str(gemini_error)}")
            logger.info("Please check your GEMINI_API_KEY and internet connection")
            
        logger.info("FastAPI application started successfully")
        logger.info("Random sampling enabled: Will process max 5 invoices per request")
        
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")
        raise

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "invoice-reimbursement-api"}

@app.get("/")
async def root():
    """Root endpoint with helpful information"""
    return {
        "message": "Invoice Reimbursement Analysis API",
        "status": "running",
        "version": "1.0.0",
        "endpoints": {
            "POST /analyze-invoices": "Main analysis endpoint - upload policy (.docx) and invoices (.zip)",
            "GET /upload-form": "Simple HTML form for testing uploads",
            "GET /test-analysis": "Information about expected request/response format",
            "GET /docs": "Interactive API documentation (Swagger UI)",
            "GET /health": "Health check endpoint"
        },
        "features": [
            "Randomly selects 5 invoices from ZIP file for analysis",
            "Uses Google Gemini for intelligent policy comparison",
            "Supports .docx policy documents and PDF invoices",
            "Returns detailed reimbursement decisions with reasoning"
        ],
        "next_steps": [
            "1. Visit /upload-form for a simple upload interface",
            "2. Or POST to /analyze-invoices with policy_file and invoice_zip",
            "3. Check /docs for interactive API documentation"
        ]
    }

@app.get("/test-analysis")
async def test_analysis():
    """Test endpoint to demonstrate the analysis functionality with sample data"""
    return {
        "message": "Upload files to /analyze-invoices endpoint",
        "instructions": {
            "1": "POST to /analyze-invoices",
            "2": "Upload policy_file (Policy-Nov2024.pdf.docx)",
            "3": "Upload invoice_zip (Cab Bills.zip, Meal Invoice.zip, or Travel Bill.zip)",
            "4": "System will randomly select 5 invoices for analysis"
        },
        "expected_response": {
            "policy_file": "Policy-Nov2024.pdf.docx",
            "invoice_zip": "Cab Bills.zip",
            "total_invoices_processed": 5,
            "randomly_selected": True,
            "detailed_analysis": [
                {
                    "invoice": "cab_receipt_001.pdf",
                    "status": "Fully Reimbursed",
                    "amount": 250,
                    "reason": "Approved under Section 3.2 Transportation Policy. Invoice amount of $250 falls within daily cab limit of $300 for local business travel. All documentation requirements met per Section 2.1."
                },
                {
                    "invoice": "cab_receipt_002.pdf", 
                    "status": "Partially Reimbursed",
                    "amount": 500,
                    "reason": "Invoice total $650 exceeds daily transportation limit of $500 per Section 3.2.1. Reimbursing maximum allowed amount. Receipt format complies with Section 2.1 documentation standards."
                },
                {
                    "invoice": "meal_receipt_001.pdf",
                    "status": "Declined", 
                    "amount": 0,
                    "reason": "Violates Section 4.1 Meal Policy: Alcohol expenses of $75 are non-reimbursable per Section 4.1.3. Location not eligible for meal reimbursement per Section 4.1.1."
                }
            ],
            "executive_summary": {
                "fully_reimbursed": 1,
                "partially_reimbursed": 1, 
                "declined": 1,
                "total_reimbursable_amount": 750
            }
        }
    }

@app.get("/upload-form")
async def upload_form():
    """Simple HTML form for testing file uploads"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Invoice Analysis - File Upload</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .container { max-width: 600px; margin: 0 auto; }
            .form-group { margin: 20px 0; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input[type="file"] { width: 100%; padding: 10px; border: 2px solid #ddd; }
            button { background-color: #007bff; color: white; padding: 15px 30px; border: none; cursor: pointer; }
            button:hover { background-color: #0056b3; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Invoice Reimbursement Analysis</h1>
            <p>Upload your policy document (.docx) and invoice ZIP file for analysis.</p>
            
            <form action="/analyze-invoices" method="post" enctype="multipart/form-data">
                <div class="form-group">
                    <label for="policy_file">Policy Document (.docx):</label>
                    <input type="file" id="policy_file" name="policy_file" accept=".docx" required>
                </div>
                
                <div class="form-group">
                    <label for="invoice_zip">Invoice ZIP File:</label>
                    <input type="file" id="invoice_zip" name="invoice_zip" accept=".zip" required>
                </div>
                
                <button type="submit">Analyze Invoices</button>
            </form>
            
            <p><strong>Note:</strong> The system will randomly select up to 5 invoices from your ZIP file for analysis.</p>
        </div>
    </body>
    </html>
    """
    
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content, status_code=200)

async def analyze_invoice_with_gemini(policy_text: str, invoice_text: str, invoice_filename: str) -> Dict[str, Any]:
    """Analyze a single invoice against the policy using Gemini"""
    try:
        prompt_template = load_prompt_template()
        formatted_prompt = prompt_template.format(
            policy_text=policy_text,
            invoice_text=invoice_text
        )
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(formatted_prompt)
        response_text = response.text.strip()
        
        # Clean response
        if response_text.startswith('```json'):
            response_text = response_text.replace('```json', '').replace('```', '').strip()
        elif response_text.startswith('```'):
            response_text = response_text.replace('```', '').strip()
            
        try:
            result = json.loads(response_text)
            
            # Return in expected format
            validated_result = {
                "invoice_id": invoice_filename,
                "reimbursement_status": result.get("reimbursement_status", "Declined"),
                "reimbursable_amount": int(result.get("reimbursable_amount", 0)),
                "reason": result.get("reason", "No reason provided")
            }
            
            # Validate status values
            valid_statuses = ["Fully Reimbursed", "Partially Reimbursed", "Declined"]
            if validated_result["reimbursement_status"] not in valid_statuses:
                validated_result["reimbursement_status"] = "Declined"
                validated_result["reason"] = f"Invalid status returned: {validated_result['reimbursement_status']}"
            
            # Ensure non-negative amount
            if validated_result["reimbursable_amount"] < 0:
                validated_result["reimbursable_amount"] = 0
            
            logger.info(f"Successfully analyzed {invoice_filename}")
            return validated_result
            
        except json.JSONDecodeError:
            return {
                "invoice_id": invoice_filename,
                "reimbursement_status": "Declined",
                "reimbursable_amount": 0,
                "reason": "Error parsing analysis response"
            }
            
    except Exception as e:
        return {
            "invoice_id": invoice_filename,
            "reimbursement_status": "Declined",
            "reimbursable_amount": 0,
            "reason": f"Analysis error: {str(e)}"
        }

async def process_zip_file(zip_content: bytes, max_files: int = None) -> List[Dict[str, Any]]:
    """
    Extract and process all PDF files from a zip archive
    
    Args:
        zip_content: Bytes content of the ZIP file
        max_files: Optional maximum number of files to process (None = process all)
    """
    pdf_files = []
    
    try:
        with zipfile.ZipFile(io.BytesIO(zip_content), 'r') as zip_ref:
            # Get all PDF files
            all_pdf_files = [
                f for f in zip_ref.filelist 
                if f.filename.lower().endswith('.pdf') and 
                not f.filename.startswith('__MACOSX')
            ]
            
            logger.info(f"Found {len(all_pdf_files)} PDF files in ZIP")
            
            if not all_pdf_files:
                return pdf_files
            
            # Process all files (or up to max_files if specified)
            files_to_process = all_pdf_files
            if max_files:
                files_to_process = files_to_process[:max_files]
                
            # Process files
            for file_info in files_to_process:
                try:
                    pdf_content = zip_ref.read(file_info.filename)
                    pdf_text = extract_text_from_pdf(pdf_content)
                    pdf_files.append({
                        "filename": file_info.filename,
                        "text": pdf_text
                    })
                    logger.info(f"Extracted text from PDF: {file_info.filename}")
                except Exception as file_error:
                    logger.error(f"Error processing PDF {file_info.filename}: {str(file_error)}")
                    continue
                    
    except Exception as e:
        logger.error(f"Error processing zip file: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error processing zip file: {str(e)}")
    
    return pdf_files

@app.post("/analyze-invoices")
async def analyze_invoices(
    policy_file: UploadFile = File(...),
    invoice_zip: UploadFile = File(...)
):
    """
    Analyze all invoices against company policy
    """
    # Validate file types
    if not policy_file.filename.lower().endswith('.docx'):
        raise HTTPException(status_code=400, detail="Policy file must be a .docx file")
    
    if not invoice_zip.filename.lower().endswith('.zip'):
        raise HTTPException(status_code=400, detail="Invoice file must be a .zip file")
    
    try:
        # Read and extract policy text
        logger.info(f"Processing policy file: {policy_file.filename}")
        policy_content = await policy_file.read()
        policy_text = extract_text_from_docx(policy_content)
        
        if not policy_text.strip():
            raise HTTPException(status_code=400, detail="Policy document appears to be empty")
        
        # Read and process zip file
        logger.info(f"Processing invoice zip file: {invoice_zip.filename}")
        zip_content = await invoice_zip.read()
        pdf_files = await process_zip_file(zip_content, max_files=None)
        
        if not pdf_files:
            raise HTTPException(status_code=400, detail="No PDF files found in the zip archive")
        
        # Analyze each invoice
        analysis_results = []
        for pdf_file in pdf_files:
            logger.info(f"Analyzing invoice: {pdf_file['filename']}")
            
            if not pdf_file['text'].strip():
                result = {
                    "invoice_id": pdf_file['filename'],
                    "reimbursement_status": "Declined",
                    "reimbursable_amount": 0,
                    "reason": "Could not extract text from PDF"
                }
            else:
                result = await analyze_invoice_with_gemini(
                    policy_text=policy_text,
                    invoice_text=pdf_file['text'],
                    invoice_filename=pdf_file['filename']
                )
            
            analysis_results.append(result)
        
        # Return simplified response matching expected format
        response_data = {
            "analysis": analysis_results
        }
        
        return JSONResponse(content=response_data)
        
    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)