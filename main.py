import os
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from database import db
from bson import ObjectId

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        # Check DB connection
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    import os
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# --------- PDF Upload & Chat Endpoints ---------
class ChatRequest(BaseModel):
    document_id: str
    question: str


@app.post("/api/upload_pdf")
async def upload_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    uploads_dir = "/tmp/uploads"
    os.makedirs(uploads_dir, exist_ok=True)

    # Persist file to disk (ephemeral) and store metadata in DB for persistence
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    stored_path = os.path.join(uploads_dir, f"{timestamp}_{safe_name}")

    content = await file.read()
    with open(stored_path, "wb") as f:
        f.write(content)

    doc = {
        "filename": file.filename,
        "stored_path": stored_path,
        "content_type": file.content_type,
        "size": len(content),
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        # In a real app, you might extract text and store it here as well
    }

    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    result = db["document"].insert_one(doc)

    return {"document_id": str(result.inserted_id), "filename": file.filename, "size": len(content)}


@app.post("/api/chat")
async def chat_with_document(payload: ChatRequest):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    try:
        doc = db["document"].find_one({"_id": ObjectId(payload.document_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid document_id")

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Placeholder response: in a real app you'd parse the PDF and run RAG/LLM
    answer = (
        f"You asked: '{payload.question}'. This is a placeholder answer based on the uploaded document "
        f"'{doc.get('filename', 'unknown')}'."
    )

    return {"answer": answer}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
