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
- 나눗셈(%) 연산 시 반드시 분자 또는 분모에 1.0을 곱해 소수점까지 계산하세요. 예시 : (SUM(QLY_INC_HPW) * 1.0 / SUM(TR_F_PRODQUANTITY)) * 100

---

이 도메인 지식은 모든 LLM 분석 및 SQL 생성 요청에 앞서 참조되어야 합니다.  
LLM은 사용자에게 명확하고 의사결정 가능한 형태의 정보로 분석 결과를 제공해야 합니다.
"""

class LLMService:
    def __init__(self, db_service=None):
        self.model = "gpt-4o"
        self.db_service = db_service
        self.domain_knowledge = DOMAIN_KNOWLEDGE

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        print(f"[DEBUG] OpenAI API 키 설정됨: {api_key[:10]}...{api_key[-10:]}")
        self.client = OpenAI(api_key=api_key)

    async def _call_openai(self, messages: List[Dict], temperature: float = 0.1, return_json: bool = True, retry_count: int = 2) -> Union[Dict[str, Any], str]:
        """OpenAI API 호출 및 응답 처리를 위한 헬퍼 메서드"""
        for attempt in range(retry_count):
            try:
                print(f"[DEBUG] OpenAI API 호출 시도 {attempt + 1}/{retry_count}")
                print(f"[DEBUG] 모델: {self.model}")
                print(f"[DEBUG] Temperature: {temperature}")
                print(f"[DEBUG] Messages: {len(messages)}개")
                
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature
                )
                
                content = response.choices[0].message.content
                print(f"[DEBUG] API 응답 길이: {len(content) if content else 0}")
                print(f"[DEBUG] LLM 응답 원문: {content}")
                
                if not content or not content.strip():
                    print(f"[DEBUG] 빈 응답 수신, 재시도: {attempt < retry_count - 1}")
                    if attempt < retry_count - 1:
                        temperature = min(0.7, temperature + 0.3)
                        continue
                    return {"type": "error", "message": "LLM 응답 생성 실패", "retry_attempted": True} if return_json else "응답을 생성할 수 없습니다."
                
                if return_json:
                    try:
                        print(f"[DEBUG] JSON 파싱 시도 - 응답 시작: {content[:200]}...")
                        content_stripped = content.strip()
                        if not content_stripped.startswith("{"):
                            print(f"[DEBUG] JSON 형식이 아님 - 전체 응답: {content}")
                            if attempt < retry_count - 1:
                                messages.append({"role": "user", "content": "반드시 설명 없이 JSON 형식만 반환하세요. 마크다운 코드블록(예: ```json)도 사용하지 마세요."})
                                continue
                            return {"type": "error", "message": "JSON 형식 응답 생성 실패", "raw_response": content}
                        result = json.loads(content_stripped)
                        if "needsConfirmation" in result:
                            if isinstance(result["needsConfirmation"], str):
                                if result["needsConfirmation"].lower() in ["true", "1", "yes"]:
                                    result["needsConfirmation"] = True
                                else:
                                    result["needsConfirmation"] = False
                            elif not isinstance(result["needsConfirmation"], bool):
                                result["needsConfirmation"] = False
                        print(f"[DEBUG] JSON 파싱 성공 - 키들: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
                        return result
                    except json.JSONDecodeError as e:
                        print(f"[DEBUG] JSON 파싱 오류: {str(e)}")
                        print(f"[DEBUG] 파싱 실패한 전체 응답: {content}")
                        if attempt < retry_count - 1:
                            messages.append({"role": "user", "content": "JSON 구문 오류가 있습니다. 설명 없이 JSON 형식만 반환하세요. 마크다운 코드블록(예: ```json)도 사용하지 마세요."})
                            continue
                        return {"type": "error", "message": f"JSON 파싱 오류: {str(e)}", "raw_response": content}
                else:
                    return content.strip()
            except Exception as e:
                print(f"[DEBUG] API 호출 예외: {str(e)}")
                if attempt < retry_count - 1:
                    continue
                return {"type": "error", "message": f"API 호출 오류: {str(e)}", "retry_attempted": True} if return_json else f"시스템 오류가 발생했습니다: {str(e)}"

    async def process_query(self, query: str, chat_history: List[Dict]) -> Dict[str, Any]:
        """사용자 쿼리 처리 메인 함수 (1~2단계는 절대 수정 금지)"""
        # 1~2단계: SQL 생성 (수정 금지)
        sql_generation = await self._generate_sql(query, chat_history, {})
        if "type" in sql_generation and sql_generation["type"] == "error":
            return sql_generation
        if "sqlQueries" not in sql_generation or not sql_generation["sqlQueries"]:
            return {"type": "error", "message": "SQL 쿼리 생성 실패", "metadata": {}}

        # 3단계: SQL 실행 및 결과 추출
        results = []
        for sql_query in sql_generation["sqlQueries"]:
            try:
                df = self.db_service.execute_query(sql_query["query"])
                df = df.astype(str)
                if df.empty or (df.fillna(0).sum().sum() == 0):
                    return {
                        "message": "데이터 없음 또는 오류 가능성: 쿼리 결과가 비어있거나 모두 0입니다.",
                        "type": "error",
                        "metadata": {"sql_result": df.to_dict('records'), "query": sql_query["query"]}
                    }
                results.append({
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

        # 4단계: 실행 결과를 LLM에 전달하여 시각화 정보만 추천받음
        visualization = await self._generate_visualization_config(results, query, chat_history)
        if "type" in visualization and visualization["type"] == "error":
            return {
                "message": "시각화 설정 생성 중 오류가 발생했습니다.",
                "type": "error",
                "metadata": visualization
            }

        # 5~6단계: summary, insights 등 부가 설명 없이 시각화 정보만 반환
        return {
            "message": "분석이 완료되었습니다.",
            "type": "analysis",
            "metadata": {
                "sql_results": results,
                "visualization": visualization,
                "confirmedIntent": sql_generation.get("confirmedIntent", "")
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
        
        return response

    async def _classify_query(self, query: str) -> Dict[str, Any]:
        """0단계: 쿼리 타입 분류"""
        print(f"[DEBUG] 쿼리 분류 시작: {query}")
        
        messages = [
            {"role": "system", "content": """사용자의 질문을 분류해주세요:
1. concept_lookup: 용어나 개념의 정의를 묻는 질문
2. analytical: 데이터 분석이나 비교를 요구하는 질문

JSON 형식으로 응답:
{"queryType": "concept_lookup" 또는 "analytical", "reason": "이유"}"""},
            {"role": "user", "content": query}
        ]
        
        result = await self._call_openai(messages, return_json=True)
        print(f"[DEBUG] OpenAI 분류 결과: {result}")
        
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
        return result

    async def _generate_sql(self, query: str, chat_history: List[Dict], confirmation: Dict[str, Any]) -> Dict[str, Any]:
        """2단계: SQL 쿼리 생성"""
        print(f"[DEBUG] SQL 생성 시작 - needsConfirmation: {confirmation.get('needsConfirmation', False)}")
        recent_context = "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-4:] if chat_history])
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
- 품질부적합률 = (QLY_INC_HPW / TR_F_PRODQUANTITY) * 100
- 년도 비교 시: DAY_CD에서 SUBSTR(DAY_CD, 1, 4)로 년도 추출
- 24년 = '2024', 25년 = '2025'

**중요: 반드시 설명 없이 JSON 형식만 반환하세요. 마크다운 코드블록(예: ```json)도 사용하지 마세요. 다른 텍스트는 포함하지 마세요.**

{{
    "confirmedIntent": "확정된 분석 의도",
    "sqlQueries": [
        {{

            "query": "SQL 쿼리",

        }}
    ],
}}

예시 - 24년과 25년 품질부적합률 비교:
{{
    "confirmedIntent": "2024년과 2025년의 품질부적합률 비교 분석",
    "sqlQueries": [
        {{
            "query": "SELECT SUBSTR(DAY_CD, 1, 4) as YEAR, SUM(QLY_INC_HPW) as 총품질부적합량, SUM(TR_F_PRODQUANTITY) as 총생산량, (SUM(QLY_INC_HPW) / SUM(TR_F_PRODQUANTITY)) * 100 as 품질부적합률 FROM TB_SUM_MQS_QMHT200 WHERE SUBSTR(DAY_CD, 1, 4) IN ('2024', '2025') GROUP BY SUBSTR(DAY_CD, 1, 4) ORDER BY YEAR",
        }}
    ],
}}"""},
            {"role": "user", "content": f"대화 맥락:\n{recent_context}\n\n분석 요청: {query}"}
        ]
        result = await self._call_openai(messages, return_json=True)
        print("[DEBUG] _generate_sql() LLM 응답 구조:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        if isinstance(result, dict) and "sqlQueries" in result:
            for i, query in enumerate(result["sqlQueries"]):
                print(f"[DEBUG] LLM 생성 SQL: {str(query.get('query', ''))}")
        if isinstance(result, dict):
            print(f"[DEBUG] result keys: {list(result.keys())}")
            if "sqlQueries" in result:
                print(f"[DEBUG] sqlQueries 존재: {len(result['sqlQueries'])}개")
                for i, query in enumerate(result['sqlQueries']):
                    print(f"[DEBUG] Query {i+1}: {str(query)}")
            else:
                print(f"[DEBUG] sqlQueries 키가 없음!")
            if "type" in result and result["type"] == "error":
                print(f"[DEBUG] 오류 응답 감지: {str(result.get('message', 'Unknown error'))}")
        else:
            print(f"[DEBUG] result가 딕셔너리가 아님: {str(result)}")
        return result

    async def _generate_visualization_config(self, sql_results: List[Dict], query: str, chat_history: List[Dict]) -> Dict[str, Any]:
        """5단계: 시각화 정보만 추천 (chartType, xAxis, yAxis, seriesBy)"""
        results_str = json.dumps(sql_results, ensure_ascii=False, indent=2)
        messages = [
            {"role": "system", "content": f"""
{self.domain_knowledge}

SQL 실행 결과를 기반으로 실제 차트 생성에 필요한 시각화 정보만 JSON으로 추천하세요.
- 반드시 chartType, xAxis, yAxis, seriesBy만 포함
- summary, insights 등 부가 설명은 절대 포함하지 마세요.
- 마크다운 코드블럭(예: ```json), 설명 텍스트 등은 절대 추가하지 마세요. JSON만 반환하세요.

JSON 예시:
{{
    "chartType": "bar",
    "xAxis": "YEAR",
    "yAxis": "품질부적합률",
    "seriesBy": null
}}"""},
            {"role": "user", "content": f"""
분석 요청: {query}

SQL 실행 결과:
{results_str}"""}
        ]
        result = await self._call_openai(messages, return_json=True)
        return result
