import os
# Set env var BEFORE importing other things that might use it
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import glob
from typing import List
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from huggingface_hub import snapshot_download
from app.core.config import settings
from app.services.loaders import CustomDocxLoader, CustomDocLoader, CustomExcelLoader
from app.ocr.ocr_service import ocr_process
from dotenv import load_dotenv

import json

# 加载环境变量
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))

def load_project_types():
    try:
        json_path = os.path.join(settings.BASE_DIR, "data", "project_types.json")
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return [{"id": "general", "name": "通用/默认"}]
    except Exception as e:
        print(f"Error loading project types: {e}")
        return [{"id": "general", "name": "通用/默认"}]

def load_documents(source_dir: str, doc_type: str, project_type_id: str) -> List:
    documents = []
    # 支持的文件类型
    file_extensions = ["*.pdf", "*.docx", "*.doc", "*.xlsx", "*.xls", "*.txt", "*.md"]
    
    if not os.path.exists(source_dir):
        # Don't print error for missing dirs, just skip (some types might not have cases yet)
        return []

    for ext in file_extensions:
        # 递归查找文件
        files = glob.glob(os.path.join(source_dir, "**", ext), recursive=True)
        for file_path in files:
            print(f"Loading {project_type_id}/{doc_type}: {file_path}")
            try:
                if file_path.lower().endswith(".pdf"):
                    # Try PyPDFLoader first
                    loader = PyPDFLoader(file_path)
                    docs = loader.load()
                    # Check if PDF has text content (not a scanned PDF)
                    total_text = sum(len(doc.page_content.strip()) for doc in docs)
                    if total_text < 50:  # Less than 50 chars total = likely scanned
                        print(f"PDF appears to be scanned, using OCR: {file_path}")
                        from langchain_core.documents import Document
                        ocr_result = ocr_process(file_path)
                        docs = [Document(page_content=ocr_result.get('full_text', ''), metadata={})]
                        print(f"OCR extracted {len(ocr_result.get('full_text', ''))} chars")
                elif file_path.lower().endswith(".docx"):
                    loader = CustomDocxLoader(file_path)
                    docs = loader.load()
                elif file_path.lower().endswith(".doc"):
                    loader = CustomDocLoader(file_path)
                    docs = loader.load()
                elif file_path.lower().endswith(".xlsx") or file_path.lower().endswith(".xls"):
                    loader = CustomExcelLoader(file_path)
                    docs = loader.load()
                else:
                    loader = TextLoader(file_path, encoding="utf-8")
                    docs = loader.load()
                # 为每个文档块添加元数据标签
                for doc in docs:
                    doc.metadata["type"] = doc_type
                    doc.metadata["source"] = os.path.basename(file_path)
                    doc.metadata["project_type"] = project_type_id
                
                documents.extend(docs)
                print(f"Successfully loaded {len(docs)} chunks from {file_path}")
            except Exception as e:
                import traceback
                print(f"Error loading {file_path}:")
                traceback.print_exc()
                
    return documents

def ingest_docs():
    # 1. 获取项目类型
    project_types = load_project_types()
    all_docs = []

    for pt in project_types:
        type_id = pt["id"]
        policy_dir = os.path.join(settings.DOCS_DIRECTORY, type_id, "policies")
        case_dir = os.path.join(settings.DOCS_DIRECTORY, type_id, "cases")
        
        all_docs.extend(load_documents(policy_dir, "policy", type_id))
        all_docs.extend(load_documents(case_dir, "case", type_id))
    
    if not all_docs:
        print("No documents found in any project type directory.")
        return

    # 3. 文本切块
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=200,
        separators=["\n\n", "\n", "。", "！", "？", " ", ""]
    )
    splits = text_splitter.split_documents(all_docs)
    print(f"Split into {len(splits)} chunks.")

    # 4. 向量化并存入 Chroma
    print("Loading embedding model (paraphrase-multilingual-MiniLM-L12-v2)...")
    # Use local cache directory to avoid system permission issues and corruption
    cache_dir = os.path.join(settings.BASE_DIR, "data", "model_cache")
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
        
    model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    
    # Attempt 1: Try with current environment (Mirror)
    endpoint = os.environ.get('HF_ENDPOINT', 'Default')
    print(f"Attempting download from {endpoint}...")
    try:
        model_path = snapshot_download(
            repo_id=model_name,
            local_dir=cache_dir,
            local_dir_use_symlinks=False,
            resume_download=True,
            allow_patterns=["*.json", "*.txt", "*.bin", "*.safetensors", "vocab.txt"]
        )
        print(f"Model ready at: {model_path}")
    except Exception as e:
        print(f"Download failed from {endpoint}: {e}")
        print("Retrying with default Hugging Face endpoint...")
        
        # Remove mirror setting to use default
        if "HF_ENDPOINT" in os.environ:
            del os.environ["HF_ENDPOINT"]
            
        try:
            model_path = snapshot_download(
                repo_id=model_name,
                local_dir=cache_dir,
                local_dir_use_symlinks=False,
                resume_download=True,
                allow_patterns=["*.json", "*.txt", "*.bin", "*.safetensors", "vocab.txt"]
            )
            print(f"Model ready at: {model_path}")
        except Exception as e2:
            print(f"All download attempts failed: {e2}")
            return
        
    embedding_function = HuggingFaceEmbeddings(
        model_name=cache_dir
    )
    
    print("Creating vector database...")
    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=embedding_function,
        persist_directory=settings.PERSIST_DIRECTORY
    )
    print(f"Successfully ingested to {settings.PERSIST_DIRECTORY}")

if __name__ == "__main__":
    ingest_docs()
