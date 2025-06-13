# 2Team - 품질 분석 AI 어시스턴트

## 프로젝트 개요

**2Team 품질 분석 AI 어시스턴트**는 제철소 품질 데이터를 쉽고 직관적으로 분석할 수 있도록 지원하는 웹 기반 시스템입니다. 사용자는 자연어로 질문을 입력하면, LLM(OpenAI GPT) 기반 AI가 SQL 쿼리를 자동 생성·실행하고, 결과를 시각화 및 요약해줍니다. 여러 개의 채팅방(세션)에서 대화를 관리할 수 있으며, 각 대화의 주제와 요약, 삭제 등 다양한 기능을 제공합니다.

---

## 주요 기능

- **자연어 기반 품질 데이터 분석**: 사용자가 자연어로 질문하면, AI가 SQL 쿼리를 생성·실행하여 결과를 분석합니다.
- **데이터 시각화**: 연도별/월별 품질 부적합률 등 주요 지표를 차트로 시각화합니다.
- **채팅방(세션) 관리**: 여러 개의 대화방을 생성·삭제·선택할 수 있고, 각 대화의 주제가 자동 요약됩니다.
- **대화 요약 및 인사이트**: 각 채팅방의 첫 대화 내용을 바탕으로 주제를 요약해 목록에 표시합니다.
- **OpenAI API 연동**: LLM을 활용한 자연어 처리 및 분석 자동화.
- **DB 연동**: SQLite 기반 품질 데이터베이스와 연동하여 실시간 쿼리 및 분석.

---

## 프로젝트 구조

```
.
├── main.py                # FastAPI 백엔드 진입점, API 라우팅, 서버 실행
├── llm_service.py         # LLM(OpenAI) 연동, 자연어→SQL 변환, 분석/시각화/요약 생성
├── database.py            # SQLite DB 연결, 쿼리 실행 함수
├── models.py              # Pydantic 데이터 모델 정의
├── domain_knowledge.py    # 도메인 특화 프롬프트(제철소 품질관리)
├── quality_analysis.db    # SQLite 품질 데이터베이스 파일
├── static/                # 프론트엔드 정적 파일(JS, CSS)
│   ├── script.js          # 프론트엔드 동작(채팅, 차트, 세션 관리 등)
│   └── style.css          # 프론트엔드 스타일(레이아웃, 테마, 반응형 등)
├── templates/             # Jinja2 HTML 템플릿
│   └── index.html         # 메인 UI 템플릿
├── attached_assets/       # 예시 데이터/CSV/참고자료
│   ├── *.csv              # 품질 데이터 예시 CSV 파일
│   └── *.txt              # 참고자료, 프롬프트 예시 등
├── .env                   # (API Key 등 환경변수, git에는 포함 X)
├── .gitignore             # Git 추적 제외 파일 목록
├── README.md              # 프로젝트 설명서
└── LICENSE                # 라이선스
```

---

## 주요 폴더/파일 상세 설명

- **main.py**  
  FastAPI 서버의 진입점으로, API 라우팅, 세션/채팅 관리, 서버 실행을 담당합니다.

- **llm_service.py**  
  OpenAI LLM과 연동하여 자연어 질의→SQL 변환, 분석 결과 요약, 시각화 추천 등 AI 핵심 로직을 구현합니다.

- **database.py**  
  SQLite 데이터베이스 연결 및 쿼리 실행, 데이터 적재/초기화 기능을 제공합니다.

- **models.py**  
  FastAPI에서 사용하는 Pydantic 데이터 모델(요청/응답 구조 등)을 정의합니다.

- **domain_knowledge.py**  
  제철소 품질관리 도메인 특화 프롬프트(LLM에 전달하는 배경지식)를 포함합니다.

- **static/**  
  - `script.js`: 채팅, 차트, 세션 관리 등 프론트엔드 동작을 담당하는 JavaScript 파일
  - `style.css`: 전체 레이아웃, 테마, 반응형 등 프론트엔드 스타일을 담당하는 CSS 파일

- **templates/**  
  - `index.html`: 메인 UI를 구성하는 Jinja2 템플릿 파일

- **attached_assets/**  
  - 예시 CSV 데이터(품질 데이터), 참고자료, 프롬프트 예시 등 다양한 부가 자료 포함

---

## 실행 방법

1. **환경 준비**
   - Python 3.9 이상 필요
   - 필수 패키지 설치:  
     ```bash
     pip install -r requirements.txt
     ```
   - `.env` 파일에 OpenAI API Key 등 환경변수 설정  
     ```env
     OPENAI_API_KEY=sk-xxxxxx
     ```

2. **서버 실행**
   ```bash
   python main.py
   ```
   또는
   ```bash
   uvicorn main:app --reload
   ```

3. **웹 접속**
   - 브라우저에서 [http://localhost:8000](http://localhost:8000) 접속

---

## 주요 화면 및 사용법

- **지표 목록**: 연도별/월별 품질 부적합률 등 주요 지표를 차트로 확인할 수 있습니다.
- **채팅방 목록**: 여러 개의 대화방을 생성·삭제·선택할 수 있고, 각 대화의 주제가 자동 요약되어 표시됩니다.
- **LLM 분석**: 자연어로 질문을 입력하면, AI가 SQL 쿼리 생성→실행→시각화→요약까지 자동으로 처리합니다.
- **채팅방 관리**: 휴지통 아이콘으로 채팅방을 삭제할 수 있습니다.

---

## 데이터 및 보안

- **DB/CSV 데이터**: `attached_assets/` 폴더에 예시 데이터가 포함되어 있습니다.
- **API Key 보안**: `.env` 파일은 git에 포함되지 않도록 `.gitignore`에 등록되어 있습니다.
- **환경변수 관리**: OpenAI API Key 등 민감 정보는 반드시 환경변수로 관리하세요.

---
