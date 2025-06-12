import json
import os
from typing import Dict, List, Any, Optional
from openai import OpenAI

from domain_knowledge import DOMAIN_KNOWLEDGE, get_concept_definition

class LLMService:
    def __init__(self):
        # the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
        # do not change this unless explicitly requested by the user
        self.model = "gpt-4o"
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.client = OpenAI(api_key=api_key)
    
    async def classify_query(self, query: str, chat_history: List[Dict]) -> Dict[str, Any]:
        """Classify query as concept_lookup or analytical"""
        
        system_prompt = f"""
        당신은 제철소 품질 분석 시스템의 쿼리 분류 전문가입니다.
        
        사용자의 질문을 다음 두 가지 유형으로 분류해주세요:
        1. concept_lookup: 용어나 개념의 정의를 묻는 질문
        2. analytical: 데이터 분석이나 시각화를 요구하는 질문
        
        도메인 지식:
        {DOMAIN_KNOWLEDGE}
        
        JSON 형식으로 응답해주세요:
        {{
            "queryType": "concept_lookup" 또는 "analytical",
            "reason": "분류 이유 설명"
        }}
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"질문: {query}"}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"Error in classify_query: {e}")
            return {"queryType": "analytical", "reason": "분류 오류로 인한 기본값"}
    
    def handle_concept_lookup(self, query: str) -> str:
        """Handle concept lookup queries using domain knowledge"""
        # Extract key terms from query and find definitions
        concept_response = get_concept_definition(query)
        
        if concept_response:
            return concept_response
        else:
            return "죄송합니다. 해당 용어에 대한 정의를 찾을 수 없습니다. 다른 용어로 다시 질문해주세요."
    
    async def check_confirmation_needed(self, query: str, chat_history: List[Dict]) -> Dict[str, Any]:
        """Check if confirmation is needed for the query"""
        
        # Get recent context from chat history
        recent_context = ""
        if chat_history:
            recent_messages = chat_history[-4:]  # Last 4 messages
            for msg in recent_messages:
                recent_context += f"{msg['role']}: {msg['content']}\n"
        
        system_prompt = f"""
        당신은 제철소 품질 분석 시스템의 확인 질문 판단 전문가입니다.
        
        사용자의 질문이 모호하거나 여러 해석이 가능한 경우, 명확한 기준을 위해 반문해야 합니다.
        
        도메인 지식:
        {DOMAIN_KNOWLEDGE}
        
        확인이 필요한 경우의 예:
        - "공정별로 보여줘" → 발생공정 vs 책임공정 구분 필요
        - "불량률 보여줘" → 기간, 품종, 고객사 등 기준 필요
        - "클레임 현황" → 기간, 고객사, 품종 등 기준 필요
        
        JSON 형식으로 응답해주세요:
        {{
            "needsConfirmation": true/false,
            "confirmationQuestion": "확인 질문 (needsConfirmation이 true인 경우)",
            "candidateIntents": ["가능한 의도 1", "가능한 의도 2"]
        }}
        """
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        if recent_context:
            messages.append({"role": "user", "content": f"이전 대화 맥락:\n{recent_context}"})
        
        messages.append({"role": "user", "content": f"현재 질문: {query}"})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.2
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"Error in check_confirmation_needed: {e}")
            return {"needsConfirmation": False}
    
    async def generate_sql(self, query: str, chat_history: List[Dict]) -> Dict[str, Any]:
        """Generate SQL queries based on user intent"""
        
        # Get recent context
        recent_context = ""
        if chat_history:
            recent_messages = chat_history[-6:]
            for msg in recent_messages:
                recent_context += f"{msg['role']}: {msg['content']}\n"
        
        system_prompt = f"""
        당신은 제철소 품질 분석을 위한 SQL 생성 전문가입니다.
        
        도메인 지식:
        {DOMAIN_KNOWLEDGE}
        
        테이블 구조:
        1. TB_SUM_MQS_QMHT200 (품질부적합통합실적)
           - DAY_CD: 분석일자 (YYYYMMDD)
           - TR_F_PRODQUANTITY: 제품생산량
           - QLY_INC_HPW: 품질부적합발생량
           - ITEM_TYPE_GROUP_NAME: 품종그룹명
           - EX_A_MAST_GD_CAU_NM: 외관종합등급원인명
           - END_USER_NAME: 최종고객사명
           - QLY_INC_HPN_FAC_TP_NM: 품질부적합발생공장구분명
           - QLY_INC_RESP_FAC_TP_NM: 품질부적합책임공장구분명
        
        2. TB_S95_SALS_CLAM030 (클레임제기보상)
           - END_USER_NAME: 최종고객사명
           - RMA_QTY: Claim보상금액
           - ITEM_TYPE_GROUP_NAME: 품종그룹명
           - EXPECTED_RESOLUTION_DATE: Claim보상품의일자 (YYYYMMDD)
        
        3. TB_S95_A_GALA_SALESPROD (매출실적분석제품)
           - END_USER_NAME: 최종고객사명
           - ITEM_TYPE_GROUP_NAME: 품종그룹명
           - SALE_QTY: 매출액
           - SALES_DATE: 제품판매매출일자 (YYYYMMDD)
        
        SQL 생성 규칙:
        - SQLite 문법 사용
        - 날짜는 'YYYYMMDD' 문자열 형식
        - 불량률 = QLY_INC_HPW / TR_F_PRODQUANTITY * 100
        - 적절한 GROUP BY, ORDER BY 사용
        - 최근 데이터 우선 (ORDER BY DAY_CD DESC 등)
        
        JSON 형식으로 응답해주세요:
        {{
            "confirmedIntent": "확정된 분석 의도",
            "sqlQueries": [
                {{
                    "description": "쿼리 설명",
                    "query": "실제 SQL 쿼리"
                }}
            ],
            "requiresPostprocessing": true/false,
            "postprocessingNote": "후처리 필요사항 (해당시)"
        }}
        """
        
        messages = [
            {"role": "system", "content": system_prompt}
        ]
        
        if recent_context:
            messages.append({"role": "user", "content": f"이전 대화 맥락:\n{recent_context}"})
        
        messages.append({"role": "user", "content": f"분석 요청: {query}"})
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"Error in generate_sql: {e}")
            raise
    
    async def generate_visualization_config(self, sql_results: List[Dict], query: str, chat_history: List[Dict]) -> Dict[str, Any]:
        """Generate visualization configuration and summary"""
        
        # Prepare data summary for LLM
        data_summary = []
        for result in sql_results:
            if "data" in result and result["data"]:
                summary = {
                    "description": result["description"],
                    "columns": result["columns"],
                    "row_count": len(result["data"]),
                    "sample_data": result["data"][:3] if result["data"] else []
                }
                data_summary.append(summary)
        
        system_prompt = f"""
        당신은 제철소 품질 데이터 시각화 및 요약 전문가입니다.
        
        도메인 지식:
        {DOMAIN_KNOWLEDGE}
        
        데이터 분석 결과를 바탕으로 적절한 차트 타입과 요약을 생성해주세요.
        
        차트 타입 가이드:
        - line: 시계열 트렌드 분석
        - bar: 카테고리별 비교
        - pie: 구성비 분석
        - scatter: 상관관계 분석
        
        JSON 형식으로 응답해주세요:
        {{
            "summary": "분석 결과 요약 설명 (한국어, 3-5문장)",
            "chartType": "line/bar/pie/scatter",
            "xAxis": "X축 컬럼명",
            "yAxis": "Y축 컬럼명",
            "seriesBy": "시리즈 구분 컬럼명 (선택사항)",
            "title": "차트 제목"
        }}
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"분석 요청: {query}"},
            {"role": "user", "content": f"데이터 요약: {json.dumps(data_summary, ensure_ascii=False, indent=2)}"}
        ]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"Error in generate_visualization_config: {e}")
            return {
                "summary": "데이터 분석이 완료되었습니다.",
                "chartType": "bar",
                "xAxis": sql_results[0]["columns"][0] if sql_results and sql_results[0].get("columns") else "x",
                "yAxis": sql_results[0]["columns"][1] if sql_results and sql_results[0].get("columns") and len(sql_results[0]["columns"]) > 1 else "y",
                "title": "분석 결과"
            }
