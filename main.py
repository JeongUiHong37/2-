from dotenv import load_dotenv
import os

# .env 파일 로드 및 API 키 확인
load_dotenv()
if not os.getenv("OPENAI_API_KEY"):
    raise ValueError("OPENAI_API_KEY environment variable is required")

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

from database import DatabaseService
from llm_service import LLMService
from models import *

# Initialize services
db_service = DatabaseService()
llm_service = LLMService(db_service=db_service)

# Session storage
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
            
        # --- 여기서 기본 채팅방 5개 생성 ---
        if not sessions:
            for _ in range(5):
                session_id = str(uuid.uuid4())
                sessions[session_id] = ChatSession(
                    session_id=session_id,
                    chat_history=[],
                    current_state="idle",
                    created_at=datetime.now()
                )
    except Exception as e:
        print(f"Error during startup: {e}")
        raise
    
    yield

app = FastAPI(title="Quality Analysis System", version="1.0.0", lifespan=lifespan)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """메인 페이지 제공"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/start_session")
async def start_session():
    """새로운 채팅 세션 생성"""
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
    """채팅 메시지 처리"""
    try:
        if request.session_id not in sessions:
            raise HTTPException(status_code=404, detail="Session not found")
        
        session = sessions[request.session_id]
        user_message = request.message.strip()
        
        if not user_message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        
        # 사용자 메시지 기록
        session.chat_history.append({
            "role": "user",
            "content": user_message,
            "timestamp": datetime.now().isoformat()
        })
        
        # 메시지 처리
        response = await process_chat_message(session, user_message)
        
        # 시스템 응답 기록
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
    """LLM 서비스를 통한 5단계 프로세스 처리"""
    try:
        # LLM 서비스에 모든 처리 위임
        result = await llm_service.process_query(message, session.chat_history)
        
        # 상태 업데이트
        if result["type"] == "confirmation":
            session.current_state = "awaiting_confirmation"
        elif result["type"] in ["analysis", "concept"]:
            session.current_state = "confirmed"
        
        return ChatResponse(
            message=result["message"],
            type=result["type"],
            metadata=result["metadata"]
        )
        
    except Exception as e:
        print(f"Error in process_chat_message: {e}")
        return ChatResponse(
            message=f"처리 중 오류가 발생했습니다: {str(e)}",
            type="error",
            metadata={"error": str(e)}
        )

@app.post("/api/select_metric")
async def select_metric(request: MetricRequest):
    """메트릭 선택 처리 - 단순히 패널 활성화 상태만 반환"""
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "status": "success",
        "panels_active": True
    }

@app.post("/api/reset_session")
async def reset_session(request: ResetRequest):
    """세션 초기화"""
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    sessions[request.session_id].chat_history = []
    sessions[request.session_id].current_state = "idle"
    
    return {"status": "success", "message": "Session reset successfully"}

@app.post("/api/delete_session")
async def delete_session(request: ResetRequest):
    """채팅 세션 삭제"""
    if request.session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    del sessions[request.session_id]
    return {"status": "success"}

@app.get("/api/sessions")
async def get_sessions():
    """Get list of all sessions (for chat history panel)"""
    try:
        session_list = []
        for session_id, session in sessions.items():
            # 첫 user 메시지 요약(30자 이내, 줄바꿈 제거)
            first_message = next(
                (msg for msg in session.chat_history if msg["role"] == "user"),
                {"content": "새 대화"}
            )
            summary = first_message["content"].replace("\n", " ").strip()
            if len(summary) > 30:
                summary = summary[:30] + "..."
            session_list.append({
                "session_id": session_id,
                "title": summary,
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

@app.post("/api/yearly_quality_data")
async def get_yearly_quality_data(request: dict):
    """연도별 품질부적합률 데이터 제공"""
    try:
        # 품질부적합 데이터 조회
        query = """
        SELECT 
            SUBSTR(DAY_CD, 1, 4) as year,
            SUM(QLY_INC_HPW) as total_defects,
            SUM(TR_F_PRODQUANTITY) as total_production
        FROM TB_SUM_MQS_QMHT200 
        WHERE DAY_CD IS NOT NULL 
        GROUP BY SUBSTR(DAY_CD, 1, 4)
        ORDER BY year
        """
        
        df = db_service.execute_query(query)
        
        if df.empty:
            return {"years": [], "quality_rates": []}
        
        # 품질부적합률 계산 (품질부적합발생량 / 제품생산량 * 100)
        df['quality_rate'] = (df['total_defects'] / df['total_production'] * 100).round(2)
        
        return {
            "years": df['year'].tolist(),
            "quality_rates": df['quality_rate'].tolist()
        }
        
    except Exception as e:
        print(f"Error in get_yearly_quality_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/monthly_quality_trend")
async def get_monthly_quality_trend(request: dict):
    """2025년 1월~5월 품질부적합률 추세 데이터 제공"""
    try:
        # 2025년 1월~5월 월별 품질부적합률 데이터 조회
        query = """
        SELECT 
            SUBSTR(DAY_CD, 1, 6) as year_month,
            SUM(QLY_INC_HPW) as total_defects,
            SUM(TR_F_PRODQUANTITY) as total_production
        FROM TB_SUM_MQS_QMHT200 
        WHERE DAY_CD LIKE '2025%' 
        AND SUBSTR(DAY_CD, 5, 2) IN ('01', '02', '03', '04', '05')
        AND DAY_CD IS NOT NULL 
        GROUP BY SUBSTR(DAY_CD, 1, 6)
        ORDER BY year_month
        """
        
        df = db_service.execute_query(query)
        
        if df.empty:
            return {"months": [], "quality_rates": []}
        
        # 품질부적합률 계산 (품질부적합발생량 / 제품생산량 * 100)
        df['quality_rate'] = (df['total_defects'] / df['total_production'] * 100).round(2)
        
        # 월 이름으로 변환 (202501 -> 1월)
        month_names = []
        for year_month in df['year_month']:
            month = int(year_month[4:6])
            month_names.append(f"{month}월")
        
        return {
            "months": month_names,
            "quality_rates": df['quality_rate'].tolist()
        }
        
    except Exception as e:
        print(f"Error in get_monthly_quality_trend: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="debug")
