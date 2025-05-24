from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse
import zipfile
import io
import os
import random
from typing import Dict, Any, List
from utils import extract_text_from_docx, extract_text_from_pdf, load_prompt_template
import google.generativeai as genai
from dotenv import load_dotenv
import json
import logging
import asyncio

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

@app.on_event("startup")
async def startup_event():
    """Initialize the application on startup"""
    try:
        # Test API connection
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')  # Using flash model
        response = model.generate_content("Test connection")
        logger.info("Successfully connected to Gemini API")
        
    except Exception as e:
        logger.error(f"Failed to initialize Gemini API: {str(e)}")
        raise

async def analyze_invoice_with_gemini(policy_text: str, invoice_text: str, invoice_filename: str) -> Dict[str, Any]:
    """Analyze a single invoice against the policy using Gemini"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt_template = load_prompt_template()
            formatted_prompt = prompt_template.format(
                policy_text=policy_text,
                invoice_text=invoice_text
            )
            
            # Request revalidation in the prompt
            formatted_prompt += "\nPlease double-check your analysis before responding."
            
            response = model.generate_content(formatted_prompt)
            response_text = response.text.strip()
            
            # Clean and validate response
            try:
                if response_text.startswith('```json'):
                    response_text = response_text.replace('```json', '').replace('```', '').strip()
                elif response_text.startswith('```'):
                    response_text = response_text.replace('```', '').strip()
                    
                result = json.loads(response_text)
                
                # Validate required fields and format
                validated_result = {
                    "invoice_id": invoice_filename,
                    "reimbursement_status": result.get("reimbursement_status", "Declined"),
                    "reimbursable_amount": int(result.get("reimbursable_amount", 0)),
                    "reason": result.get("reason", "No reason provided")
                }
                
                # Validate status values
                valid_statuses = ["Fully Reimbursed", "Partially Reimbursed", "Declined"]
                if validated_result["reimbursement_status"] not in valid_statuses:
                    raise ValueError(f"Invalid status: {validated_result['reimbursement_status']}")
                
                # Ensure reasonable amount
                if validated_result["reimbursable_amount"] < 0:
                    raise ValueError("Negative reimbursement amount")
                
                # Verify reason includes policy reference
                if "clause" not in validated_result["reason"].lower():
                    validated_result["reason"] += " (Based on policy analysis)"
                
                logger.info(f"Successfully analyzed {invoice_filename}")
                return validated_result
                
            except (json.JSONDecodeError, ValueError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Validation failed, retrying: {str(e)}")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    return {
                        "invoice_id": invoice_filename,
                        "reimbursement_status": "Declined",
                        "reimbursable_amount": 0,
                        "reason": f"Analysis validation failed: {str(e)}"
                    }
                    
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"Analysis attempt {attempt + 1} failed: {str(e)}")
                await asyncio.sleep(retry_delay)
            else:
                raise

    return {
        "invoice_id": invoice_filename,
        "reimbursement_status": "Declined",
        "reimbursable_amount": 0,
        "reason": "Maximum analysis attempts exceeded"
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

@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint with basic information"""
    return """
    <html>
        <head>
            <title>Invoice Reimbursement Analysis API</title>
        </head>
        <body>
            <h1>Invoice Reimbursement Analysis API</h1>
            <p>Available endpoints:</p>
            <ul>
                <li><a href="/docs">API Documentation</a></li>
                <li><a href="/upload-form">Upload Form</a></li>
            </ul>
        </body>
    </html>
    """

@app.get("/upload-form", response_class=HTMLResponse)
async def upload_form():
    """Simple HTML form for file upload with modern design"""
    return """
    <html>
        <head>
            <title>Upload Files for Analysis</title>
            <style>
                body {
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 2rem;
                    background-color: #f5f5f7;
                    color: #1d1d1f;
                }
                
                .container {
                    background: white;
                    padding: 2rem;
                    border-radius: 12px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
                }
                
                h1 {
                    font-size: 1.8rem;
                    font-weight: 500;
                    margin-bottom: 2rem;
                    color: #1d1d1f;
                    text-align: center;
                }
                
                .upload-section {
                    margin-bottom: 1.5rem;
                }
                
                label {
                    display: block;
                    margin-bottom: 0.5rem;
                    font-weight: 500;
                    color: #484848;
                }
                
                input[type="file"] {
                    width: 100%;
                    padding: 0.5rem;
                    margin-bottom: 1rem;
                    border: 2px dashed #e0e0e0;
                    border-radius: 8px;
                    background: #fafafa;
                }
                
                input[type="file"]:hover {
                    border-color: #0071e3;
                }
                
                button {
                    background-color: #0071e3;
                    color: white;
                    padding: 0.8rem 2rem;
                    border: none;
                    border-radius: 8px;
                    font-size: 1rem;
                    cursor: pointer;
                    width: 100%;
                    transition: background-color 0.2s;
                }
                
                button:hover {
                    background-color: #0077ed;
                }
                
                .file-requirements {
                    font-size: 0.9rem;
                    color: #666;
                    margin-top: 0.5rem;
                }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Invoice Analysis</h1>
                <form action="/analyze-invoices" method="post" enctype="multipart/form-data">
                    <div class="upload-section">
                        <label>Policy Document</label>
                        <input type="file" name="policy_file" accept=".docx" required>
                        <div class="file-requirements">Accepted format: .docx</div>
                    </div>
                    
                    <div class="upload-section">
                        <label>Invoice Files</label>
                        <input type="file" name="invoice_zip" accept=".zip" required>
                        <div class="file-requirements">Upload a ZIP file containing PDF invoices</div>
                    </div>
                    
                    <button type="submit">Analyze Invoices</button>
                </form>
            </div>
        </body>
    </html>
    """

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="127.0.0.1",  # Changed from 0.0.0.0 to localhost
        port=8000,
        reload=True,
        log_level="info"
    )