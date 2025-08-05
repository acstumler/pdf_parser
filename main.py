from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from strategies import STRATEGY_CLASSES
from utils.pdf_utils import extract_text_from_pdf
from parser_engine import detect_and_parse
from routes.classify_route import classify_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/parse-universal/")
async def parse_universal(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        text = extract_text_from_pdf(contents)
        strategy_class = detect_and_parse(text)
        parser = strategy_class(text)
        transactions = parser.extract_transactions()
        return JSONResponse(content={"transactions": transactions})
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Include AI classification route
app.include_router(classify_router)
