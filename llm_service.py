import json
import os
from typing import Dict, List, Any, Optional, Union
from openai import OpenAI

# Domain knowledge as a string constant
DOMAIN_KNOWLEDGE = """
당신은 제철소의 실적 지표 중 품질(품질, 클레임 등)을 분석하는 AI 분석 어시스턴트입니다.  
사용자는 일관제철소에서 품질·생산 지표를 총괄하는 **직책자(관리자)**이며,  
현재의 수치가 어떤 의미를 가지는지, 어디서 문제가 발생했는지, 어떤 기준으로 개선 방향을 도출해야 할지 탐색하고자 합니다.

따라서, 단순 수치 조회뿐 아니라 다음과 같은 태도로 대응해야 합니다:

- 분석 축(공정/품종/고객사 등)에 대해 명확한 기준을 먼저 확인하세요.  
- 지표 수치가 이상할 경우, 사용자에게 추가로 **의미 있는 drill-down**을 제안해 주세요.  
- drill-down 할 때는 데이터 테이블을 참고하여 제안을 해주세요.  
- 사용자 입장에서 **직책자 시야**에서 의사결정을 돕는 형태로 결과를 정리하세요.  
- SQL을 생성할 때 기준이 될 수 있는 항목이 2개 이상 존재하거나 모호한 경우, LLM이 임의로 선택하지 말고 반드시 사용자에게 기준을 재확인한 후 SQL을 생성하세요.

---

[1] 주요 지표 정의 및 계산법

- 품질부적합률 = (QLY_INC_HPW / TR_F_PRODQUANTITY) * 100
- 클레임률 = (RMA_QTY / SALE_QTY) * 100

---

[2] 품질부적합 테이블 (TB_SUM_MQS_QMHT200)
| 컬럼명 | 설명 및 활용 | 예시 값 |
|--------|----------------|-----------|
| DAY_CD | 실적이 집계된 날짜로, YYYYMMDD 형식의 문자열입니다. 월별, 분기별 집계 시 이 값을 기준으로 필터링하거나 그룹화할 수 있습니다. | "20250115" |
| TR_F_PRODQUANTITY | 제품생산량. 창고 입고 기준의 최종 생산량으로, 품질부적합률 계산 시 분모로 사용됩니다. 수치는 중량 단위입니다. | 125000 |
| QLY_INC_HPW | 품질부적합발생량. 기준 미달 제품의 총 중량으로 불량률 계산 시 분자로 사용됩니다. | 860 |
| QLY_INC_HPN_FAC_TP_NM | 품질부적합발생공장구분명. 품질부적합이 발생한 공정 및 공장명으로 예를 들어 "열연2"는 '열연'이라는 공정에서 발생한 문제이고, 숫자 "2"는 해당 공정이 위치한 2공장을 의미합니다. 즉, 이 필드는 "공정명 + 공장번호" 구조로 되어 있으며, 같은 공정이라도 공장번호가 다르면 서로 다른 위치를 의미합니다. | "열연2", "전기강판1" |
| QLY_INC_RESP_FAC_TP_NM | 품질부적합책임공장구분명. 품질부적합의 원인에 대한 책임이 있는 공정 및 공장명. "열연2"는 '열연' 공정의 2공장을 의미하며, 이 필드는 "공정명 + 공장번호" 구조입니다. | "열연2", "전기강판1" |
| ITEM_TYPE_GROUP_NAME | 품종그룹명. 포스코에서 제품을 구분하는 항목입니다. | "냉연", "선재", "전기강판", "도금", "열연", "후판" |
| EX_A_MAST_GD_CAU_NM | 외관불량원인명. 외관의 등급을 결정한 원인을 나타내는 코드입니다. | "Build Up", "단중미달", "Dust", "두께불량", "겹침흠", "Crack", "폭불량", "Edge burr", "양파", "Black Line", "UST불량", "딱지흠", "Edge파손", "부푼흠", "Scab", "Blow Hole" |
| END_USER_NAME | 최종고객사명. 주문서에서 최종적으로 제품을 사용하는 고객사의 이름입니다. | "A고객사", "B고객사", "C고객사", "D고객사", "E고객사" |
| SPECIFICATION_CD_N | 제품규격약호. 국가 또는 단체에서 제정한 제품 규격의 명칭을 인식하기 용이하게 간략화하여 나타낸 코드입니다. | "JS-A", "JS-B", "JS-C", "JD-D", "JS-E", "JS-F", "JS-G" |

---

[3] 클레임 테이블 (TB_S95_SALS_CLAM030)
| 컬럼명 | 설명 및 활용 | 예시 값 |
|--------|----------------|-----------|
| RMA_QTY | 클레임보상액. 고객에게 보상한 현금을 나타내는 숫자이다. 클레임률 계산 시 분자로 사용됩니다. | 3200 |
| EXPECTED_RESOLUTION_DATE | 클레임보상품의일자. 고객사로부터 클레임이 제기되어 보상하는 일자로 YYYYMMDD 형식의 문자열입니다. 월별, 분기별 집계 시 이 값을 기준으로 필터링하거나 그룹화할 수 있습니다. | "20241215" |
| ITEM_TYPE_GROUP_NAME | 품종그룹명. 포스코에서 제품을 구분하는 항목입니다. | "냉연", "선재", "전기강판", "도금", "열연", "후판" |
| END_USER_NAME | 최종고객사명. 주문서에서 최종적으로 제품을 사용하는 고객사의 이름입니다. | "A고객사", "B고객사", "C고객사", "D고객사", "E고객사" |

---

[4] 매출 테이블 (TB_S95_A_GALA_SALESPROD)
| 컬럼명 | 설명 및 활용 | 예시 값 |
|--------|----------------|-----------|
| SALES_DATE | 제품판매일자. 제품을 판매하는 일자로 YYYYMMDD 형식의 문자열입니다. 월별, 분기별 집계 시 이 값을 기준으로 필터링하거나 그룹화할 수 있습니다. | "20241215" |
| SALE_QTY | 제품매출가격. 제품의 판매가격으로 클레임률 계산 시 분모로 사용된다. | 145000 |
| ITEM_TYPE_GROUP_NAME | 품종그룹명. 포스코에서 제품을 구분하는 항목입니다. | "냉연", "선재", "전기강판", "도금", "열연", "후판" |
| END_USER_NAME | 최종고객사명. 주문서에서 최종적으로 제품을 사용하는 고객사의 이름입니다. | "A고객사", "B고객사", "C고객사", "D고객사", "E고객사" |

---

[5] "외관불량원인명"에 대한 정의
- Build Up : Roll의 국부적인 연마불량 또는 Hot Coil Profile등에 의해서 폭방향 일부분이 국부적으로 늘어나 부풀어 오른 것처럼 보이는 현상
- Black Line : 압연 방향에 직선상으로 길게 나타나는 결함으로 비금속 개재물에 의해 나타나는 현상입니다.
- Dust : 표면에 점상형으로 먼지 현태가 묻어 거칠한 모양을 나타내며 표면 Coating층 가루의 누적으로 인해 발생할 수 있습니다.
- Edge burr : 절단된 면이 깨끗하지 않아 거친 모서리를 형성하는 상태로 Knife의 마모 등 여러 원인에 의해 발생할 수 있습니다.
- Edge 파손 : Edge부가 파이거나 깨진 형태로 Coil 취급 부주의로 인해 발생합니다.
- 두께불량 : 고객 주문의 두께와 허용치를 벗어난 경우로 압연 불량에 의해 발생합니다.
- 양파 : Coil의 양 Edge 부분에 Wave가 발생된 상태로 Hot Coil 소재의 Crown이 좋지 않거나 권취장력이 불균일 할 때 발생합니다.
- 폭불량 : 고객 주문의 폭과 허용치를 벗어난 경우로 압연 불량에 의해 발생합니다.
- Crack : 압연 방향의 직선형태로 발생하는 Crack으로 부적절한 Roll Groove 등으로 인해 발생합니다.
- 겹침흠 : 겹쳐져 압연된 형태로 주로 압연 중 소재가 적절하게 정렬되지 않아 발생합니다.
- Blow Hole : 압연 방향으로 길게 늘어선 부풀음으로 제품 표면 가까이의 기포 미압착 및 대형 개재물에 의해 발생합니다.
- Scab : 표층 직하의 기포가 압연 중 터지면서 발생 합니다.
- UST불량 : 내부에 존재하는 개재물, 수축공에 인한 결함으로 고객 사용 중 품질저하를 발생시킬 수 있습니다. 고객 사용 용도에 따라 민감하게 반응합니다.
- 부푼흠 : 표면에 좁쌀 모양으로 부풀어 있는 상태로써 연주 작업시 Slag, Powder등이 혼입되어 압연시 부풀어 오르게 됩니다.

---

[6] 유의사항 및 기준
- '공장' 기준은 반드시 **발생공장**과 **책임공장** 중 어떤 것을 기준으로 분석할 것인지 확인해야 함. 
- '제품' 기준은 반드시 **품종그룹명**과 **제품규격약호** 중 어떤 것을 기준으로 분석할 것인지 확인해야 함. 
- 날짜는 모두 YYYYMMDD 형식이며, 월/분기 단위 집계 시 SUBSTR 등을 활용할 수 있음
- 사용자가 '공정별', '품종별', '고객사별' 등의 기준을 언급한 경우, SQL 생성 시 GROUP BY 또는 WHERE 조건에 반영되어야 함

---

이 도메인 지식은 모든 LLM 분석 및 SQL 생성 요청에 앞서 참조되어야 합니다.  
LLM은 사용자에게 명확하고 의사결정 가능한 형태의 정보로 분석 결과를 제공해야 합니다.
"""

# 모든 개념 정의는 LLM이 DOMAIN_KNOWLEDGE를 기반으로 동적 생성

class LLMService:
    def __init__(self, db_service=None):
        self.model = "gpt-4o"
        self.db_service = db_service
        self.domain_knowledge = DOMAIN_KNOWLEDGE

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        self.client = OpenAI(api_key=api_key)

# _get_concept_definition 메서드 제거 - 모든 개념 정의는 LLM이 처리

    async def _call_openai(self, messages: List[Dict], temperature: float = 0.1, return_json: bool = True, retry_count: int = 2) -> Union[Dict[str, Any], str]:
        """OpenAI API 호출 및 응답 처리를 위한 헬퍼 메서드"""
        for attempt in range(retry_count):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature
                )
                
                content = response.choices[0].message.content
                if not content or not content.strip():
                    if attempt < retry_count - 1:
                        # 재시도 시 더 높은 temperature로 다양한 응답 유도
                        temperature = min(0.7, temperature + 0.3)
                        continue
                    # 최종 실패 시에도 LLM이 처리할 수 있는 구조 반환
                    return {"type": "error", "message": "LLM 응답 생성 실패", "retry_attempted": True} if return_json else "응답을 생성할 수 없습니다."
                
                if return_json:
                    try:
                        if content.strip().startswith("{"):
                            result = json.loads(content)
                            # Convert string "true"/"false" to boolean for needsConfirmation
                            if "needsConfirmation" in result:
                                if isinstance(result["needsConfirmation"], str):
                                    if result["needsConfirmation"].lower() in ["true", "1", "yes"]:
                                        result["needsConfirmation"] = True
                                    else:
                                        result["needsConfirmation"] = False
                                elif not isinstance(result["needsConfirmation"], bool):
                                    result["needsConfirmation"] = False
                            return result
                        
                        # JSON 형식이 아닌 경우 재시도
                        if attempt < retry_count - 1:
                            # JSON 형식 요구를 강조하는 메시지 추가
                            messages.append({"role": "user", "content": "JSON 형식으로만 응답해주세요."})
                            continue
                        return {"type": "error", "message": "JSON 형식 응답 생성 실패", "raw_response": content}
                        
                    except json.JSONDecodeError as e:
                        if attempt < retry_count - 1:
                            # JSON 파싱 오류 시 재시도
                            messages.append({"role": "user", "content": "올바른 JSON 형식으로 다시 응답해주세요."})
                            continue
                        return {"type": "error", "message": f"JSON 파싱 오류: {str(e)}", "raw_response": content}
                else:
                    return content.strip()
                    
            except Exception as e:
                if attempt < retry_count - 1:
                    # API 오류 시 재시도
                    continue
                # 최종 실패 시에도 구조화된 응답 반환
                return {"type": "error", "message": f"API 호출 오류: {str(e)}", "retry_attempted": True} if return_json else f"시스템 오류가 발생했습니다: {str(e)}"

    async def process_query(self, query: str, chat_history: List[Dict]) -> Dict[str, Any]:
        """전체 5단계 프로세스를 처리하는 메인 메서드"""
        
        # 0단계: 쿼리 타입 분류
        classification = await self._classify_query(query)
        if "type" in classification and classification["type"] == "error":
            return {
                "message": "쿼리 분류 중 오류가 발생했습니다.",
                "type": "error",
                "metadata": classification
            }

        if classification["queryType"] == "concept_lookup":
            # GPT를 통한 개념 정의 생성
            concept_response = await self._generate_concept_answer(query)
            return {
                "message": concept_response,
                "type": "concept",
                "metadata": {
                    "queryType": "concept_lookup",
                    "query": query
                }
            }

        # 1단계: 불명확성 체크
        confirmation = await self._check_confirmation_needed(query, chat_history)
        if "type" in confirmation and confirmation["type"] == "error":
            return {
                "message": "쿼리 확인 중 오류가 발생했습니다.",
                "type": "error",
                "metadata": confirmation
            }

        if confirmation.get("needsConfirmation", False):
            return {
                "message": confirmation["confirmationQuestion"],
                "type": "confirmation",
                "metadata": {
                    "needsConfirmation": True,
                    "candidateIntents": confirmation.get("candidateIntents", []),
                    "reason": confirmation.get("reason", "")
                }
            }

        # 2단계: SQL 쿼리 생성
        sql_generation = await self._generate_sql(query, chat_history, confirmation)
        if "type" in sql_generation and sql_generation["type"] == "error":
            return {
                "message": "SQL 생성 중 오류가 발생했습니다.",
                "type": "error",
                "metadata": sql_generation
            }

        # 4단계: SQL 실행
        results = []
        for sql_query in sql_generation["sqlQueries"]:
            try:
                df = self.db_service.execute_query(sql_query["query"])
                results.append({
                    "description": sql_query["description"],
                    "purpose": sql_query.get("purpose", ""),
                    "query": sql_query["query"],
                    "data": df.to_dict('records'),
                    "columns": df.columns.tolist()
                })
            except Exception as e:
                return {
                    "message": f"SQL 실행 중 오류가 발생했습니다: {str(e)}",
                    "type": "error",
                    "metadata": {"error": str(e), "query": sql_query["query"]}
                }

        # 5단계: 시각화 설정 및 요약 생성
        visualization = await self._generate_visualization_config(results, query, chat_history)
        if "type" in visualization and visualization["type"] == "error":
            return {
                "message": "시각화 설정 생성 중 오류가 발생했습니다.",
                "type": "error",
                "metadata": visualization
            }

        return {
            "message": visualization.get("summary", "분석이 완료되었습니다."),
            "type": "analysis",
            "metadata": {
                "sql_results": results,
                "visualization": visualization,
                "confirmedIntent": sql_generation.get("confirmedIntent", ""),
                "insights": visualization.get("insights", [])
            }
        }

    async def _generate_concept_answer(self, query: str) -> str:
        """개념 및 용어 정의를 GPT를 통해 생성"""
        messages = [
            {"role": "system", "content": f"""

도메인 지식:
{self.domain_knowledge}

제철소 품질 관리 맥락에 특화된 설명이어야 합니다.
전문 용어를 사용하되, 1~2줄로 간단하고 이해하기 쉽게 설명해주세요.
"""},
            {"role": "user", "content": f"다음 용어나 개념에 대해 설명해주세요: {query}"}
        ]
        
        response = await self._call_openai(messages, temperature=0.3, return_json=False)
        
        # LLM이 모든 상황을 처리하도록 함 - fallback 제거
        return response

    async def _classify_query(self, query: str) -> Dict[str, Any]:
        """0단계: 쿼리 타입 분류"""
        messages = [
            {"role": "system", "content": f"""
{self.domain_knowledge}

사용자의 질문을 다음 두 가지 유형으로 분류해주세요:
1. concept_lookup: 용어나 개념의 정의를 묻는 질문
2. analytical: 데이터 분석이나 비교, 데이터의 시각화를 요구하는 질문으로 SQL Query 작성이 필요한 질문

JSON 형식으로 응답해주세요:
{{
    "queryType": "concept_lookup" 또는 "analytical",
    "reason": "분류 이유 설명"
}}"""},
            {"role": "user", "content": query}
        ]
        
        result = await self._call_openai(messages, return_json=True)
        # LLM이 에러 상황도 처리하도록 함 - 하드코딩된 fallback 제거
        return result

    async def _check_confirmation_needed(self, query: str, chat_history: List[Dict]) -> Dict[str, Any]:
        """1단계: 불명확성 체크"""
        recent_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-4:] if chat_history])
        
        messages = [
            {"role": "system", "content": f"""
{self.domain_knowledge}

당신은 제철소 품질 분석 전문가입니다. 사용자의 질문에서 SQL 쿼리 작성 시 의도가 애매한 경우를 파악하고, 명확한 의도 파악을 위한 확인 질문을 생성해주세요.

확인이 필요한 경우는 다음과 같습니다:
- 확인이 필요한 경우는 "사용자 질문에 복수의 비교 기준이 명시되었거나, 문맥상 암시되어 SQL을 어떤 기준으로 그룹핑할지 애매한 경우"로 제한해줘.
- 사용자 질문이 명확하게 하나의 기준(예: 년도 비교, 품종별 비교 등)만 요청하는 경우에는 확인 질문을 하지 않도록 해줘.
- 예를 들어 "24년도와 25년도 불량률 비교"는 기준이 명확하므로 추가 확인 질문이 필요하지 않아.

확인 질문은 반드시 다음 3가지 요소를 포함해야 합니다:
1. 사용자가 언급한 지표나 항목의 정확한 정의
2. 선택 가능한 각 후보 항목의 이름과 정의
3. 왜 이 후보들 사이에서 의도가 애매한지에 대한 설명

JSON 형식으로 응답해주세요:
{{
    "needsConfirmation": false,
    "confirmationQuestion": "",
    "candidateIntents": [],
    "reason": ""
}}

만약 확인이 필요한 경우 다음과 같이 응답하세요:
{{
    "needsConfirmation": true,
    "confirmationQuestion": "[지표나 항목의 정의]입니다. [후보 항목들의 정의]가 있습니다. [애매한 이유 설명]입니다. 어느 것을 기준으로 분석해드릴까요?",
    "candidateIntents": [
        "발생공장: 품질 문제가 실제로 발생한 제조 공장을 기준으로 분석",
        "책임공장: 품질 문제의 원인을 제공한 것으로 판단되는 공장을 기준으로 분석"
    ],
    "reason": "공장별 분석 시 발생공장과 책임공장 중 어느 것을 기준으로 할지 명확하지 않습니다."
}}

예시 응답:
"confirmationQuestion": "안녕하세요! 공장별 품질부적합률은 제품의 품질 문제가 발생한 비율을 공장 단위로 분석한 지표입니다. 발생공장(품질 문제가 실제로 발생한 제조 공장)과 책임공장(품질 문제의 원인을 제공한 것으로 판단되는 공장)이 있어 어느 것을 기준으로 분석할지 명확하지 않습니다. 어느 것을 기준으로 분석해드릴까요?"

사용자에게 친절하고 전문적으로 설명해주세요."""},
            {"role": "user", "content": f"대화 맥락:\n{recent_context}\n\n현재 질문: {query}"}
        ]
        
        result = await self._call_openai(messages, return_json=True)
        # LLM이 에러 상황도 처리하도록 함 - 하드코딩된 fallback 제거
        return result

    async def _generate_sql(self, query: str, chat_history: List[Dict], confirmation: Dict[str, Any]) -> Dict[str, Any]:
        """2단계: SQL 쿼리 생성"""
        recent_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-4:] if chat_history])
        
        # 확인 응답 정보 추가
        confirmation_info = ""
        if confirmation and not confirmation.get("needsConfirmation", False):
            selected_intent = None
            for msg in reversed(chat_history):
                if msg["role"] == "user" and any(intent.split(":")[0].strip() in msg["content"] for intent in confirmation.get("candidateIntents", [])):
                    selected_intent = msg["content"]
                    break
            if selected_intent:
                confirmation_info = f"\n선택된 분석 기준: {selected_intent}"
        
        messages = [
            {"role": "system", "content": f"""
{self.domain_knowledge}

사용자의 분석 요청에 맞는 SQL 쿼리를 생성하세요.{confirmation_info}

SQL 생성 규칙:
- SQLite 문법 사용
- 날짜는 'YYYYMMDD' 문자열 형식
- 불량률 = (QLY_INC_HPW / TR_F_PRODQUANTITY) * 100

JSON 형식으로 응답해주세요:
{{
    "confirmedIntent": "확정된 분석 의도",
    "sqlQueries": [
        {{
            "description": "쿼리 설명",
            "query": "SQL 쿼리",
            "purpose": "해당 쿼리의 목적"
        }}
    ],
    "requiresPostprocessing": true/false,
    "postprocessingNote": "후처리 방식 설명"
}}"""},
            {"role": "user", "content": f"대화 맥락:\n{recent_context}\n\n분석 요청: {query}"}
        ]
        
        result = await self._call_openai(messages)
        # LLM이 에러 상황에서도 적절한 SQL을 생성하도록 함 - 하드코딩된 기본 SQL 제거
        return result

    async def _generate_visualization_config(self, sql_results: List[Dict], query: str, chat_history: List[Dict]) -> Dict[str, Any]:
        """5단계: 시각화 설정 및 요약 생성"""
        results_str = json.dumps(sql_results, ensure_ascii=False, indent=2)
        
        messages = [
            {"role": "system", "content": f"""
{self.domain_knowledge}

SQL 실행 결과를 기반으로 적절한 시각화 설정과 요약을 생성하세요.

JSON 형식으로 응답해주세요:
{{
    "chartType": "line/bar/scatter/pie 중 하나",
    "xAxis": "x축에 사용할 컬럼명",
    "yAxis": "y축에 사용할 컬럼명",
    "seriesBy": "시리즈 구분에 사용할 컬럼명 (선택)",
    "summary": "분석 결과에 대한 상세한 설명",
    "insights": ["주요 인사이트 1", "주요 인사이트 2"]
}}"""},
            {"role": "user", "content": f"""
분석 요청: {query}

SQL 실행 결과:
{results_str}"""}
        ]
        
        result = await self._call_openai(messages)
        # LLM이 에러 상황에서도 적절한 시각화 설정을 생성하도록 함 - 하드코딩된 fallback 제거
        return result
