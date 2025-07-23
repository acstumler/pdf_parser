from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
import tempfile
from semantic_extractor import extract_transactions_from_pdf

router = APIRouter()

@router.post("/parse-pdf/")
async def parse_pdf(file: UploadFile = File(...)):
    try:
        if file.content_type != "application/pdf":
            return JSONResponse(status_code=400, content={"error": "Only PDF files are supported."})

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        result = extract_transactions_from_pdf(tmp_path)
        return JSONResponse(content=result)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
