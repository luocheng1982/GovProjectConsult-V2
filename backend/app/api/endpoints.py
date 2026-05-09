from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from typing import Optional, List
from pydantic import BaseModel
from app.services.chat_service import ChatService
from app.core.utils import extract_text_from_file
from app.core.config import settings
from app.core.logger import log_chat_request, log_chat_response, log_error, log_feedback
import os
import shutil
import json
import time

router = APIRouter()
chat_service = None

def get_chat_service():
    global chat_service
    if chat_service is None:
        chat_service = ChatService()
    return chat_service

class ProjectType(BaseModel):
    id: str
    name: str

class ChatRequest(BaseModel):
    message: str
    project_type: str = "general"

class ChatResponse(BaseModel):
    response: str
    file_url: Optional[str] = None
    project_type: str
    sources: Optional[List[dict]] = None

class DocumentInfo(BaseModel):
    filename: str
    type: str
    path: str
    project_type: str

class GenerateIdRequest(BaseModel):
    name: str

class LoginRequest(BaseModel):
    password: str

class FeedbackRequest(BaseModel):
    feedback_type: str
    message_index: int
    user_message: Optional[str] = None
    ai_response: Optional[str] = None
    project_type: Optional[str] = None
    is_cancel: Optional[bool] = False

@router.post("/login")
async def login(request: LoginRequest):
    if request.password == settings.ADMIN_PASSWORD:
        return {"status": "success", "role": "admin"}
    else:
        raise HTTPException(status_code=401, detail="Invalid password")

@router.post("/generate-id")
async def generate_id(request: GenerateIdRequest):
    try:
        service = get_chat_service()
        generated_id = await service.generate_id_from_name(request.name)
        return {"id": generated_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/project-types", response_model=List[ProjectType])
async def list_project_types():
    try:
        json_path = os.path.join(settings.BASE_DIR, "data", "project_types.json")
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return [{"id": "general", "name": "通用/默认"}]
    except Exception as e:
        print(f"Error loading project types: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/project-types", response_model=ProjectType)
async def create_project_type(project_type: ProjectType):
    try:
        json_path = os.path.join(settings.BASE_DIR, "data", "project_types.json")
        types = []
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                types = json.load(f)
        
        # Check if ID exists
        if any(t['id'] == project_type.id for t in types):
            raise HTTPException(status_code=400, detail="Project type ID already exists")
            
        types.append(project_type.dict())
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(types, f, ensure_ascii=False, indent=2)
            
        # Create directories
        os.makedirs(os.path.join(settings.DOCS_DIRECTORY, project_type.id, "policies"), exist_ok=True)
        os.makedirs(os.path.join(settings.DOCS_DIRECTORY, project_type.id, "cases"), exist_ok=True)
        
        return project_type
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/project-types/{type_id}", response_model=ProjectType)
async def update_project_type(type_id: str, project_type: ProjectType):
    try:
        json_path = os.path.join(settings.BASE_DIR, "data", "project_types.json")
        types = []
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                types = json.load(f)
        
        # If updating general and it's not in the JSON yet, we might need to handle it
        # But usually 'general' is either in JSON or implicitly handled.
        # Let's ensure we can update it.
        
        found = False
        for i, t in enumerate(types):
            if t['id'] == type_id:
                types[i]['name'] = project_type.name
                found = True
                break
        
        if not found:
            if type_id == "general":
                # Special case: if general is not in JSON, add it
                types.append({"id": "general", "name": project_type.name})
            else:
                raise HTTPException(status_code=404, detail="Project type not found")
            
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(types, f, ensure_ascii=False, indent=2)
            
        return ProjectType(id=type_id, name=project_type.name)
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/project-types/{type_id}")
async def delete_project_type(type_id: str):
    if type_id == "general":
         raise HTTPException(status_code=400, detail="Cannot delete default project type")
    
    # 1. Update JSON
    json_path = os.path.join(settings.BASE_DIR, "data", "project_types.json")
    if not os.path.exists(json_path):
         raise HTTPException(status_code=404, detail="Project types not found")
    
    with open(json_path, 'r', encoding='utf-8') as f:
        types = json.load(f)
    
    # Filter out
    new_types = [t for t in types if t['id'] != type_id]
    
    if len(new_types) == len(types):
        raise HTTPException(status_code=404, detail="Project type not found")
        
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(new_types, f, ensure_ascii=False, indent=2)

    # 2. Delete Directory
    dir_path = os.path.join(settings.DOCS_DIRECTORY, type_id)
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)

    # 3. Delete from Chroma
    service = get_chat_service()
    service.delete_project_docs(type_id)
    
    return {"status": "success", "message": f"Deleted project type {type_id}"}

@router.get("/documents", response_model=List[DocumentInfo])
async def list_documents(project_type: str = "general"):
    try:
        service = get_chat_service()
        return service.list_documents(project_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/documents/{doc_type}/{filename}")
async def delete_document(doc_type: str, filename: str, project_type: str = "general"):
    try:
        service = get_chat_service()
        if doc_type not in ["policy", "case"]:
             raise HTTPException(status_code=400, detail="Invalid doc_type. Must be 'policy' or 'case'")
        
        success = service.delete_document(filename, doc_type, project_type)
        if not success:
            raise HTTPException(status_code=404, detail="Document not found or failed to delete")
        return {"status": "success", "message": f"Deleted {filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/documents/{doc_type}/{filename}/download")
async def download_document(doc_type: str, filename: str, project_type: str = "general"):
    try:
        if doc_type not in ["policy", "case"]:
            raise HTTPException(status_code=400, detail="Invalid doc_type")
        
        subdir = "policies" if doc_type == "policy" else "cases"
        file_path = os.path.join(settings.DOCS_DIRECTORY, project_type, subdir, filename)
        
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")
            
        return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/documents/upload")
async def upload_knowledge_base_file(
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    project_type: str = Form("general")
):
    try:
        if doc_type not in ["policy", "case"]:
            raise HTTPException(status_code=400, detail="Invalid doc_type. Must be 'policy' or 'case'")
            
        # 1. Determine save path
        subdir = "policies" if doc_type == "policy" else "cases"
        save_dir = os.path.join(settings.DOCS_DIRECTORY, project_type, subdir)
        os.makedirs(save_dir, exist_ok=True)
        
        file_path = os.path.join(save_dir, file.filename)
        
        # 2. Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 3. Process and add to vector store
        service = get_chat_service()
        success = await service.add_document(file_path, doc_type, project_type)
        
        if not success:
            # Clean up if ingestion fails
            if os.path.exists(file_path):
                os.remove(file_path)
            raise HTTPException(status_code=500, detail="Failed to ingest document")
            
        return {"status": "success", "message": f"Uploaded and indexed {file.filename}"}
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error uploading KB file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/chat", response_model=ChatResponse)
async def chat(
    message: str = Form(...),
    project_type: str = Form("general"),
    file: Optional[UploadFile] = File(None)
):
    start_time = time.time()
    file_name = file.filename if file else None

    try:
        service = get_chat_service()

        file_content = None
        file_url = None

        if file:
            file_content = await extract_text_from_file(file)
            if file_content.startswith("Error"):
                log_error("FILE_EXTRACTION", file_content)
                raise HTTPException(status_code=400, detail=file_content)

            uploads_dir = os.path.join(settings.BASE_DIR, "data", "uploads")
            os.makedirs(uploads_dir, exist_ok=True)

            await file.seek(0)

            save_path = os.path.join(uploads_dir, file.filename)
            with open(save_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            file_url = f"/api/v1/uploads/{file.filename}"

        log_chat_request(message, project_type, file_name)

        result = await service.get_response(message, file_content, project_type)

        processing_time = time.time() - start_time
        log_chat_response(result["answer"], len(result.get("sources", [])), processing_time)

        return ChatResponse(
            response=result["answer"],
            file_url=file_url,
            project_type=project_type,
            sources=result["sources"]
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        processing_time = time.time() - start_time
        log_error("CHAT_PROCESSING", str(e), f"processing_time={processing_time:.2f}s")
        print(f"Error processing chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/uploads/{filename}")
async def get_uploaded_file(filename: str):
    try:
        uploads_dir = os.path.join(settings.BASE_DIR, "data", "uploads")
        file_path = os.path.join(uploads_dir, filename)
        
        if not os.path.exists(file_path):
             raise HTTPException(status_code=404, detail="File not found")
             
        return FileResponse(path=file_path, filename=filename)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/analyze", response_model=ChatResponse)
async def analyze_file(file: UploadFile = File(...)):
    try:
        # 1. Extract text
        content = await extract_text_from_file(file)
        if content.startswith("Error"):
            raise HTTPException(status_code=400, detail=content)
            
        # 2. Analyze
        service = get_chat_service()
        answer = await service.analyze_document(content, file.filename)
        
        return ChatResponse(response=answer, project_type="general")
    except Exception as e:
        print(f"Error processing file analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/feedback")
async def submit_feedback(request: FeedbackRequest):
    try:
        if request.feedback_type not in ["like", "dislike"]:
            raise HTTPException(status_code=400, detail="feedback_type must be 'like' or 'dislike'")
        
        log_feedback(
            feedback_type=request.feedback_type,
            message_index=request.message_index,
            user_message=request.user_message,
            ai_response=request.ai_response,
            project_type=request.project_type,
            is_cancel=request.is_cancel
        )
        
        action = "cancelled" if request.is_cancel else "recorded"
        return {"status": "success", "message": f"Feedback {action}: {request.feedback_type}"}
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"Error recording feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))