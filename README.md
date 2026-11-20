# AI 기반 외출 알림 서비스

## 1. 프로젝트 소개

## 2. 팀원 역할

## 3. 기술 스택

## 4. 프로젝트 구조

- 본 프로젝트는 크게 Backend, Frontend, Automation, Docs 4개 영역으로 구성되어 있습니다.

```text
ai-outing-talk/
├── automation/
│
├── backend/
│   ├── app/
│   │   ├── config.py
│   │   ├── firebase.py
│   │   ├── main.py
│   │   ├── routers/
│   │   ├── schemas/
│   │   └── services/
│   ├── tests/
│   │   ├── test_firestore_read.py
│   │   └── test_firestore_write.py
│   ├── .env
│   ├── .env.example
│   └── requirements.txt
│
├── docs/
│   ├── project_proposal.md
│   └── functional_requirements.md
│
├── frontend/
│   ├── css/
│   │   └── style.css
│   ├── js/
│   │   └── main.js
│   └── index.html
│
├── .gitignore
└── README.md
```

### 폴더 및 파일 설명

| 경로 | 설명 |
|---|---|
| `backend/` | FastAPI 기반 백엔드 서버 |
| `backend/app/` | 백엔드 애플리케이션 코드 |
| `routers/` | API 요청 처리 |
| `schemas/` | 데이터 구조 및 유효성 검증 |
| `services/` | 주요 기능 및 비즈니스 로직 |
| `frontend/` | 사용자 웹 화면 |
| `automation/` | n8n 자동화 워크플로우 |
| `docs/` | 프로젝트 관련 문서 |
| `requirements.txt` | Python 패키지 의존성 목록 |
| `.env.example` | 환경변수 설정 예시 |
| `README.md` | 프로젝트 소개 및 실행 안내 |


## 5. 설치 및 실행 방법

### Frontend
- VS Code Live Server 확장 프로그램 사용
- `frontend/index.html` 실행

### Backend
- 가상환경 활성화
- 패키지 설치
- FastAPI 서버 실행


## 6. 사용자 테스트 결과

## 7. 링크
- 배포 URL: 
- 발표 자료: 