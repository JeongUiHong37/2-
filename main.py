from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager
import sqlite3
import pandas as pd
import json
import uuid
from datetime import datetime
from typing import Dict, List, Optional
import os

from database import DatabaseService
from llm_service import LLMService
from models import *

# Initialize services
db_service = DatabaseService()
llm_service = LLMService()

# Session storage (in production, use Redis or similar)
sessions: Dict[str, ChatSession] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    try:
        # Initialize database
        db_service.init_database()
        
        # Load CSV data if tables are empty
        if db_service.is_database_empty():
            print("Loading CSV data into database...")
            db_service.load_csv_data()
            print("Database initialized successfully")
        else:
            print("Database already contains data")
            
    except Exception as e:
        print(f"Error during startup: {e}")
        raise
    
    yield
    
    # Cleanup code would go here if needed

app = FastAPI(title="Quality Analysis System", version="1.0.0", lifespan=lifespan)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main application page"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/start_session")
async def start_session():
    """Create a new chat session"""
    session_id = str(uuid.uuid4())
    sessions[session_id] = ChatSession(
        session_id=session_id,
        chat_history=[],
        current_state="idle",
        created_at=datetime.now()
    )
    return {"session_id": session_id}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    """Handle chat messages"""
    try:
        session_id = request.session_id
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = sessions[session_id]
        user_message = request.message.strip()
        
        if not user_message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # Add user message to history
        session.chat_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Process the message
        response = await process_chat_message(session, user_message)
        
        # Add assistant response to history
        session.chat_history.append({
            "role": "assistant",
            "content": response.message,
            "timestamp": datetime.now().isoformat(),
            "metadata": response.metadata
        })
        
        return response
        
    except Exception as e:
        print(f"Error in chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def process_chat_message(session: ChatSession, message: str) -> ChatResponse:
    """Process a chat message and return appropriate response"""
    
    # Step 1: Query classification
    classification = await llm_service.classify_query(message, session.chat_history)
    
    if classification["queryType"] == "concept_lookup":
        # Handle concept lookup (domain knowledge)
        concept_response = llm_service.handle_concept_lookup(message)
        return ChatResponse(
            message=concept_response,
            type="concept",
            metadata={"queryType": "concept_lookup"}
        )
    
    # Step 2: Check if confirmation is needed
    if session.current_state != "confirmed":
        confirmation_check = await llm_service.check_confirmation_needed(
            message, session.chat_history
        )
        
        if confirmation_check["needsConfirmation"]:
            session.current_state = "awaiting_confirmation"
            session.pending_intent = confirmation_check.get("candidateIntents", [])
            
            return ChatResponse(
                message=confirmation_check["confirmationQuestion"],
                type="confirmation",
                metadata={
                    "needsConfirmation": True,
                    "candidateIntents": confirmation_check.get("candidateIntents", [])
                }
            )
    
    # Step 3: Generate SQL and execute analysis
    session.current_state = "confirmed"
    
    try:
        # Generate SQL queries
        sql_generation = await llm_service.generate_sql(message, session.chat_history)
        
        # Execute SQL queries
        results = []
        for sql_query in sql_generation["sqlQueries"]:
            try:
                df = db_service.execute_query(sql_query["query"])
                results.append({
                    "description": sql_query["description"],
                    "query": sql_query["query"],
                    "data": df.to_dict('records'),
                    "columns": df.columns.tolist()
                })
            except Exception as e:
                print(f"SQL execution error: {e}")
                results.append({
                    "description": sql_query["description"],
                    "query": sql_query["query"],
                    "error": str(e)
                })
        
        # Generate visualization config and summary
        if results and not any("error" in r for r in results):
            viz_config = await llm_service.generate_visualization_config(
                results, message, session.chat_history
            )
            
            return ChatResponse(
                message=viz_config["summary"],
                type="analysis",
                metadata={
                    "sql_results": results,
                    "visualization": viz_config,
                    "confirmedIntent": sql_generation.get("confirmedIntent", "")
                }
            )
        else:
            # Handle SQL errors
            error_messages = [r.get("error", "") for r in results if "error" in r]
            error_response = f"죄송합니다. 데이터 조회 중 오류가 발생했습니다: {'; '.join(error_messages)}"
            
            return ChatResponse(
                message=error_response,
                type="error",
                metadata={"errors": error_messages}
            )
            
    except Exception as e:
        print(f"Analysis error: {e}")
        return ChatResponse(
            message="분석 처리 중 오류가 발생했습니다. 다시 시도해주세요.",
            type="error",
            metadata={"error": str(e)}
        )

@app.post("/api/select_metric")
async def select_metric(request: MetricRequest):
    """Handle metric selection from left panel"""
    try:
        session_id = request.session_id
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = sessions[session_id]
        
        if request.metric == "품질부적합":
            # Simulate clicking on quality non-conformance metric
            message = "품질부적합 현황을 보여주세요"
            response = await process_chat_message(session, message)
            
            # Add to chat history
            session.chat_history.append({
                "role": "user",
                "content": message,
                "timestamp": datetime.now().isoformat(),
                "metadata": {"source": "metric_selection"}
            })
            
            session.chat_history.append({
                "role": "assistant",
                "content": response.message,
                "timestamp": datetime.now().isoformat(),
                "metadata": response.metadata
            })
            
            return response
        else:
            return ChatResponse(
                message="해당 지표는 아직 지원되지 않습니다.",
                type="info",
                metadata={}
            )
            
    except Exception as e:
        print(f"Error in select_metric: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/reset_session")
async def reset_session(request: ResetRequest):
    """Reset session state"""
    try:
        session_id = request.session_id
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Reset session
        sessions[session_id] = ChatSession(
            session_id=session_id,
            chat_history=[],
            current_state="idle",
            created_at=datetime.now()
        )
        
        return {"status": "success", "message": "세션이 초기화되었습니다."}
        
    except Exception as e:
        print(f"Error in reset_session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/sessions")
async def get_sessions():
    """Get list of all sessions (for chat history panel)"""
    try:
        session_list = []
        for session_id, session in sessions.items():
            if session.chat_history:
                # Get first user message as title
                first_message = next(
                    (msg for msg in session.chat_history if msg["role"] == "user"),
                    {"content": "새 대화"}
                )
                session_list.append({
                    "session_id": session_id,
                    "title": first_message["content"][:50] + "..." if len(first_message["content"]) > 50 else first_message["content"],
                    "created_at": session.created_at.isoformat(),
                    "message_count": len(session.chat_history)
                })
        
        # Sort by creation time, newest first
        session_list.sort(key=lambda x: x["created_at"], reverse=True)
        return session_list
        
    except Exception as e:
        print(f"Error in get_sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get specific session data"""
    try:
        if session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = sessions[session_id]
        return {
            "session_id": session_id,
            "chat_history": session.chat_history,
            "current_state": session.current_state,
            "created_at": session.created_at.isoformat()
        }
        
    except Exception as e:
        print(f"Error in get_session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
