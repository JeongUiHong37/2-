import json
import os
import re
from typing import Dict, List, Any, Optional, Union
from openai import OpenAI

# Domain knowledge as a string constant
DOMAIN_KNOWLEDGE = """
당신은 제철소의 실적 지표 중 품질(품질, 클레임 등)을 분석하는 AI 분석 어시스턴트입니다.  
사용자는 일관제철소에서 품질·생산 지표를 총괄하는 **직책자(관리자)**이며,  
현재의 수치가 어떤 의미를 가지는지, 어디서 문제가 발생했는지, 어떤 기준으로 개선 방향을 도출해야 할지 탐색하고자 합니다.

따라서, 단순 수치 조회뿐 아니라 다음과 같은 태도로 대응해야 합니다:
  
- 지표 수치가 이상할 경우, 사용자에게 추가로 **의미 있는 drill-down**을 제안해 주세요.  
- drill-down 할 때는 데이터 테이블을 참고하여 제안을 해주세요.  
- 사용자 입장에서 **직책자 시야**에서 의사결정을 돕는 형태로 결과를 정리하세요.  

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
- 날짜는 모두 YYYYMMDD 형식이며, 월/분기 단위 집계 시 SUBSTR 등을 활용할 수 있음
- 사용자가 '공정별', '품종별', '고객사별' 등의 기준을 언급한 경우, SQL 생성 시 GROUP BY 또는 WHERE 조건에 반영되어야 함


[7] 예시 SQL
 - 2025년도에 발생한 고객사별 클레임률을 계산하는 SQL : SELECT TB_S95_SALS_CLAM030.END_USER_NAME, SUM(RMA_QTY) as 총클레임보상액, SUM(SALE_QTY) as 총매출가격, (SUM(RMA_QTY) * 1.0 / SUM(SALE_QTY)) * 100 as 클레임률 FROM TB_S95_SALS_CLAM030 JOIN TB_S95_A_GALA_SALESPROD ON TB_S95_SALS_CLAM030.END_USER_NAME = TB_S95_A_GALA_SALESPROD.END_USER_NAME WHERE SUBSTR(EXPECTED_RESOLUTION_DATE, 1, 4) = '2025' GROUP BY TB_S95_SALS_CLAM030.END_USER_NAME


---

이 도메인 지식은 모든 LLM 분석 및 SQL 생성 요청에 앞서 참조되어야 합니다.  
LLM은 사용자에게 명확하고 의사결정 가능한 형태의 정보로 분석 결과를 제공해야 합니다.
"""

DB_SCHEMA = """
[DB 스키마]

1. TB_SUM_MQS_QMHT200 (품질부적합통합실적)
   - DAY_CD (YYYYMMDD)
   - TR_F_PRODQUANTITY (제품생산량)
   - QLY_INC_HPW (품질부적합발생량)
   - QLY_INC_HPN_FAC_TP_NM (품질부적합발생공장구분명)
   - QLY_INC_RESP_FAC_TP_NM (품질부적합책임공장구분명)
   - ITEM_TYPE_GROUP_NAME (품종그룹명)
   - EX_A_MAST_GD_CAU_NM (외관불량원인명)
   - END_USER_NAME (최종고객사명)
   - SPECIFICATION_CD_N (제품규격약호)

2. TB_S95_SALS_CLAM030 (클레임제기보상)
   - END_USER_NAME (최종고객사명)
   - RMA_QTY (클레임보상액)
   - ITEM_TYPE_GROUP_NAME (품종그룹명)
   - EXPECTED_RESOLUTION_DATE (클레임보상품의일자, YYYYMMDD)

3. TB_S95_A_GALA_SALESPROD (매출실적분석제품)
   - END_USER_NAME (최종고객사명)
   - ITEM_TYPE_GROUP_NAME (품종그룹명)
   - SALE_QTY (매출액)
   - SALES_DATE (제품판매일자, YYYYMMDD)
"""

def remove_trailing_commas(json_string: str) -> str:
    # }, or ], 뒤에 오는 쉼표 제거
    return re.sub(r',\s*([}}\]])', r'\1', json_string)

def get_recent_context(chat_history, n=4):
    if not chat_history:
        return ""
    return "\n".join([f"{msg['role']}: {msg['content']}" for msg in chat_history[-n:]])

class LLMService:
    def __init__(self, db_service=None):
        self.model = "gpt-4o"
        self.db_service = db_service
        self.domain_knowledge = DOMAIN_KNOWLEDGE
        self.db_schema = DB_SCHEMA

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
                        content_stripped = remove_trailing_commas(content.strip())  # 쉼표 자동 제거 적용
                        if not content_stripped.startswith("{"):
                            print(f"[DEBUG] JSON 형식이 아님 - 전체 응답: {content}")
                            if attempt < retry_count - 1:
                                messages.append({"role": "user", "content": "반드시 설명 없이 JSON 형식만 반환하세요. 마크다운 코드블록(예: ```json)도 사용하지 마세요.\nJSON 안에서는 마지막 요소 뒤에 쉼표(,)를 절대 넣지 마세요. 예: {\"a\": 1,} ← 이런 형식은 금지입니다."})
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
                            messages.append({"role": "user", "content": "JSON 구문 오류가 있습니다. 설명 없이 JSON 형식만 반환하세요. 마크다운 코드블록(예: ```json)도 사용하지 마세요.\nJSON 안에서는 마지막 요소 뒤에 쉼표(,)를 절대 넣지 마세요. 예: {\"a\": 1,} ← 이런 형식은 금지입니다."})
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
        """사용자 쿼리 처리 메인 함수 (개념설명/분석 분기 및 needsConfirmation 반복 반문, 에러 응답 보완)"""
        # 0단계: 쿼리 타입 분류
        classification = await self._classify_query(query, chat_history)
        if classification.get("queryType") == "concept_lookup":
            answer = await self._generate_concept_answer(query, chat_history)
            return {
                "type": "concept",
                "message": answer,
                "metadata": {}
            }

        # 분석(analytical) 질문일 경우, needsConfirmation 반복 체크
        confirmation = None
        if classification.get("queryType") == "analytical":
            while True:
                confirmation = await self._check_confirmation_needed(query, chat_history)
                if confirmation.get("needsConfirmation", False):
                    # 반문 반환(프론트엔드에서 사용자의 추가 답변을 받아 chat_history에 누적 후 재호출 필요)
                    return {
                        "type": "confirmation",
                        "message": confirmation["confirmationQuestion"],
                        "metadata": confirmation
                    }
                else:
                    break

        # 2단계: SQL 생성 및 실행
        sql_generation = await self._generate_sql(query, chat_history, confirmation if confirmation else {})
        if "type" in sql_generation and sql_generation["type"] == "error":
            return {
                "type": sql_generation.get("type", "error"),
                "message": sql_generation.get("message", "오류가 발생했습니다."),
                "metadata": sql_generation.get("metadata", {}),
                "raw_response": sql_generation.get("raw_response", None)
            }
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
                "metadata": visualization.get("metadata", {})
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

    async def _generate_concept_answer(self, query: str, chat_history: List[Dict] = None) -> str:
        """개념 및 용어 정의를 GPT를 통해 생성"""
        recent_context = get_recent_context(chat_history)
        messages = [
            {"role": "system", "content": f"""
{self.domain_knowledge}
{self.db_schema}

대화 맥락:
{recent_context}

제철소 품질 관리 맥락에 특화된 설명이어야 합니다. 전문 용어를 사용하되, 1~2줄로 간단하고 이해하기 쉽게 설명해주세요.
"""},
            {"role": "user", "content": f"다음 용어나 개념에 대해 설명해주세요: {query}"}
        ]
        
        response = await self._call_openai(messages, temperature=0.3, return_json=False)
        
        return response

    async def _classify_query(self, query: str, chat_history: List[Dict] = None) -> Dict[str, Any]:
        """0단계: 쿼리 타입 분류"""
        print(f"[DEBUG] 쿼리 분류 시작: {query}")
        
        recent_context = get_recent_context(chat_history)
        messages = [
            {"role": "system", "content": f"""
{self.domain_knowledge}
{self.db_schema}

대화 맥락:
{recent_context}

아래 기준에 따라 사용자의 질문을 분류하세요:
1. concept_lookup: 용어나 개념의 정의를 묻는 질문
2. analytical: 데이터 분석이나 비교를 요구하는 질문

JSON 형식으로 응답:
{{"queryType": "concept_lookup" 또는 "analytical", "reason": "이유"}}
"""},
            {"role": "user", "content": query}
        ]
        result = await self._call_openai(messages, return_json=True)
        print(f"[DEBUG] OpenAI 분류 결과: {result}")
        return result

    async def _check_confirmation_needed(self, query: str, chat_history: List[Dict] = None) -> Dict[str, Any]:
        """1단계: 불명확성 체크"""
        recent_context = get_recent_context(chat_history)
        
        messages = [
            {"role": "system", "content": f"""
{self.domain_knowledge}
{self.db_schema}

대화 맥락:
{recent_context}

당신은 제철소 품질 분석 전문가입니다. 사용자의 질문에서 SQL 쿼리 작성 시 대상 항목이 애매한 경우를 파악하고, 명확한 의도 파악을 위한 확인 질문을 생성해주세요.

확인이 필요한 경우는 다음과 같습니다:
- 사용자 질문에 비교 기준에 해당하는 DB 항목이 복수개인 경우에만 확인을 해줘.
- 사용자 질문이 명확하게 하나의 기준(예: 년도 비교, 품종별 비교 등)만 요청하는 경우에는 확인 질문을 하지 않도록 해줘.
- 예를 들어 "24년도와 25년도 품질부적합률 비교"는 기준이 명확하므로 추가 확인 질문이 필요하지 않아.

확인 질문이 필요한 경우, 반드시 아래 구조를 따라 작성해주세요:

1. [지표명] 지표정의 : [계산식]
2. 층별화 기준 : [사용자가 언급한 분석 기준이나 조건]
3. 확인 필요기준 : 아래 [개수]개 항목이 확인이 필요합니다.
 - [항목1명] = [항목1 상세 설명]
 - [항목2명] = [항목2 상세 설명]

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
    "confirmationQuestion": "1. [지표명] 지표정의 : [계산식]\n2. 층별화 기준 : [분석 기준]\n3. 확인 필요기준 : 아래 [개수]개 항목이 확인이 필요합니다.\n - [항목1명] = [항목1 상세 설명]\n - [항목2명] = [항목2 상세 설명]\n\n어느 기준으로 분석해드릴까요?",
    "candidateIntents": [
        "[항목1명]: [항목1 설명]",
        "[항목2명]: [항목2 설명]"
    ],
    "reason": "[확인이 필요한 이유]"
}}

실제 예시:
{{
    "needsConfirmation": true,
    "confirmationQuestion": "1. 품질부적합률 지표정의 : (품질부적합발생량 / 제품생산량) × 100\n2. 층별화 기준 : 공장별 분석\n3. 확인 필요기준 : 아래 2개 항목이 확인이 필요합니다.\n - 품질부적합발생공장구분명 = 품질부적합이 발생한 공정 및 공장명\n - 품질부적합책임공장구분명 = 품질부적합의 원인에 대한 책임이 있는 공정 및 공장명\n\n어느 기준으로 분석해드릴까요?",
    "candidateIntents": [
        "발생공장: 품질 문제가 실제로 발생한 제조 공장을 기준으로 분석",
        "책임공장: 품질 문제의 원인을 제공한 것으로 판단되는 공장을 기준으로 분석"
    ],
    "reason": "공장별 분석 시 발생공장과 책임공장 중 어느 것을 기준으로 할지 명확하지 않습니다."
}}

사용자에게 친절하고 전문적으로 설명해주세요."""},
            {"role": "user", "content": f"대화 맥락:\n{recent_context}\n\n현재 질문: {query}"}
        ]
        
        result = await self._call_openai(messages, return_json=True)
        return result

    async def _generate_sql(self, query: str, chat_history: List[Dict], confirmation: Dict[str, Any]) -> Dict[str, Any]:
        """2단계: SQL 쿼리 생성"""
        print(f"[DEBUG] SQL 생성 시작 - needsConfirmation: {confirmation.get('needsConfirmation', False)}")
        recent_context = get_recent_context(chat_history)
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
{self.db_schema}

대화 맥락:
{recent_context}
{confirmation_info}

SQL 생성 규칙:
- SQLite 문법 사용
- 날짜는 'YYYYMMDD' 문자열 형식
- 품질부적합률 = (QLY_INC_HPW / TR_F_PRODQUANTITY) * 100
- 년도 비교 시: DAY_CD에서 SUBSTR(DAY_CD, 1, 4)로 년도 추출
- 나눗셈(%) 연산 시 반드시 분자 또는 분모에 1.0을 곱해 소수점까지 계산하세요. 예시 : (SUM(QLY_INC_HPW) * 1.0 / SUM(TR_F_PRODQUANTITY)) * 100
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

    async def _generate_visualization_config(self, sql_results: List[Dict], query: str, chat_history: List[Dict] = None) -> Dict[str, Any]:
        """5단계: 시각화 정보만 추천 (chartType, xAxis, yAxis, seriesBy)"""
        recent_context = get_recent_context(chat_history)
        
        # 실제 데이터 구조 분석
        if not sql_results or not sql_results[0].get('data'):
            return {"chartType": "bar", "xAxis": "X축", "yAxis": "Y축", "seriesBy": None}
        
        data_sample = sql_results[0]['data'][:3]  # 샘플 데이터
        available_columns = sql_results[0].get('columns', [])
        
        # 데이터 구조를 LLM에게 명확히 전달
        data_structure_info = f"""
실제 데이터 구조:
- 사용 가능한 컬럼들: {available_columns}
- 데이터 샘플 (처음 3개 행):
{json.dumps(data_sample, ensure_ascii=False, indent=2)}

컬럼 분석:
"""
        
        # 각 컬럼의 데이터 타입과 특성 분석
        for col in available_columns:
            sample_values = [str(row.get(col, '')) for row in data_sample[:3] if row.get(col)]
            data_structure_info += f"- {col}: {sample_values}\n"
        
        results_str = json.dumps(sql_results, ensure_ascii=False, indent=2)
        
        messages = [
            {"role": "system", "content": f"""
{self.domain_knowledge}
{self.db_schema}

대화 맥락:
{recent_context}

{data_structure_info}

SQL 실행 결과를 기반으로 실제 차트 생성에 필요한 시각화 정보만 JSON으로 추천하세요.

중요한 규칙:
1. chartType은 데이터 특성에 맞게 선택:
   - 시간/년도 비교 → "line" 
   - 카테고리별 비교 → "bar"
   - 비율/구성 → "pie"
   - 연관성 분석 → "scatter"

2. xAxis, yAxis는 반드시 실제 존재하는 컬럼명 중에서 선택해야 함
3. seriesBy는 그룹화할 컬럼이 있을 때만 지정 (없으면 null)
4. 년도나 날짜 컬럼이 있으면 우선적으로 xAxis로 고려
5. 비율이나 률(%) 관련 컬럼이 있으면 우선적으로 yAxis로 고려

**반드시 설명 없이 JSON 형식만 반환하세요. 마크다운 코드블럭은 사용하지 마세요.**

올바른 JSON 예시:
{{
    "chartType": "line",
    "xAxis": "YEAR",
    "yAxis": "품질부적합률",
    "seriesBy": null
}}

{{
    "chartType": "bar", 
    "xAxis": "ITEM_TYPE_GROUP_NAME",
    "yAxis": "품질부적합률",
    "seriesBy": "YEAR"
}}
"""},
            {"role": "user", "content": f"분석 요청: {query}\n\n사용자가 요청한 분석을 위해 위 데이터 구조를 바탕으로 가장 적절한 시각화 설정을 추천해주세요."}
        ]
        
        result = await self._call_openai(messages, return_json=True)
        print(f"[DEBUG] LLM 시각화 설정 추천: {result}")
        
        # 결과 검증 및 기본값 설정
        if isinstance(result, dict):
            # 기본값 설정
            if "chartType" not in result:
                result["chartType"] = "bar"
            if "xAxis" not in result and available_columns:
                result["xAxis"] = available_columns[0]
            if "yAxis" not in result and len(available_columns) > 1:
                result["yAxis"] = available_columns[1]
            if "seriesBy" not in result:
                result["seriesBy"] = None
                
            # seriesBy 값 정리 (문자열 "null"을 실제 None로 변환)
            if result.get("seriesBy") == "null" or result.get("seriesBy") == "None":
                result["seriesBy"] = None
                
            print(f"[DEBUG] 최종 시각화 설정: {result}")
        
        return result
