# 배포 및 연동 가이드

## 구성

| 구성 요소 | 위치 | 역할 |
|---|---|---|
| 백엔드 + 프론트 | Render (Web Service 1개) | FastAPI가 API와 `frontend/` 화면을 같은 주소에서 제공 |
| 데이터베이스 | Firebase Firestore | 사용자 토큰, 알림 저장 |
| 자동화 | n8n Cloud | 10분마다 발송 대상 확인 후 발송 요청 |
| AI | LLM API (OpenAI 호환 형식) | 자연어 해석, 알림 문구 생성 |

### 기술적 의사결정: 프론트를 백엔드와 같은 주소에서 제공

- 기획 단계에서는 프론트를 Vercel, 백엔드를 Render에 따로 배포할 계획이었다.
- 로그인 상태를 쿠키로 유지하는데, 두 서비스의 도메인이 다르면 쿠키가 다른 사이트 쿠키로 취급된다. 아이폰 사파리 등은 이를 기본으로 차단해 로그인이 유지되지 않을 수 있다.
- FastAPI가 `frontend/` 정적 파일을 함께 제공하도록 바꿔 같은 주소에서 동작하게 했다. 쿠키, CORS, 리다이렉트 설정이 단순해지고 배포도 한 번으로 끝난다.

### 기술적 의사결정: 날씨 API

- 기상청 단기예보는 위경도를 격자 좌표로 변환해야 하고 API 키 승인 시간이 필요하다.
- 일정상 API 키 없이 위경도로 바로 조회할 수 있는 Open-Meteo를 n8n에서 사용했다.

## 1. Render 배포

**New → Web Service**에서 GitHub 저장소를 연결합니다.

| 항목 | 값 |
|---|---|
| Branch | `develop` (최종 제출 시 `main`) |
| Root Directory | `backend` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free |

### 환경변수 (Environment)

| 변수 | 값 |
|---|---|
| `PYTHON_VERSION` | `3.11.9` |
| `FIREBASE_PROJECT_ID` | Firebase 프로젝트 ID |
| `FIREBASE_CREDENTIALS_PATH` | `/etc/secrets/firebase-key.json` |
| `KAKAO_REST_API_KEY` | 카카오 REST API 키 |
| `KAKAO_CLIENT_SECRET` | 카카오 Client Secret |
| `KAKAO_REDIRECT_URI` | `https://<render 주소>/api/auth/kakao/callback` |
| `APP_SESSION_SECRET` | 긴 임의 문자열 |
| `COOKIE_SECURE` | `true` |
| `FRONTEND_URL` | `/` |
| `INTERNAL_API_KEY` | 긴 임의 문자열 (n8n Config 노드와 같은 값) |
| `LLM_BASE_URL` | LLM API 주소 (OpenAI 호환, 예: `https://api.openai.com/v1`) |
| `LLM_API_KEY` | LLM API 키 |
| `LLM_MODEL` | 사용할 모델 이름 |

임의 문자열은 터미널에서 `python -c "import secrets; print(secrets.token_urlsafe(32))"`로 만들 수 있습니다.

### Firebase 키 파일

**Environment → Secret Files**에서 파일 이름 `firebase-key.json`으로 서비스 계정 JSON 내용을 붙여 넣습니다. Render는 이 파일을 `/etc/secrets/firebase-key.json`에 둡니다. 키 파일은 저장소에 커밋하지 않습니다.

### 배포 확인

- `https://<render 주소>/health` → `{"status":"ok"}`
- `https://<render 주소>/health/firebase` → `{"status":"ok","firebase":"connected"}`
- `https://<render 주소>/` → 동의 화면
- `https://<render 주소>/docs` → API 문서

## 2. 카카오 디벨로퍼스 설정

| 위치 | 설정 |
|---|---|
| 앱 → 플랫폼 키 → REST API 키 → 리다이렉트 URI | `https://<render 주소>/api/auth/kakao/callback` 추가 (로컬용 `http://localhost:8000/...`은 유지) |
| 앱 → 플랫폼 → Web 사이트 도메인 | `https://<render 주소>` 추가 (메시지 버튼 링크용) |
| 카카오 로그인 → 동의항목 | `talk_message` (카카오톡 메시지 전송) 설정 |
| 카카오맵 API | 활성화 (장소 좌표 검색, 이동 시간 조회) |
| 앱 → 멤버 | 테스트할 팀원과 테스터 카카오 계정 |

## 3. n8n 연결

`automation/README.md`를 따릅니다. Config 노드의 `base_url`에 Render 주소를 넣고 Active를 켭니다.

## 4. 로컬 실행

```bash
cd backend
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

브라우저에서 `http://localhost:8000`으로 접속합니다. 화면과 API가 같은 주소라 Live Server는 필요 없습니다. (`127.0.0.1`과 `localhost`를 섞어 쓰면 쿠키가 따로 저장되니 하나로 통일합니다.)

## 5. API 요약

| 메서드 | 경로 | 인증 | 설명 |
|---|---|---|---|
| GET | `/api/auth/kakao/login` | - | 카카오 로그인 페이지로 이동 |
| GET | `/api/auth/kakao/callback` | - | 토큰 저장, 세션 쿠키 설정 후 `/?login=success`로 이동 |
| GET | `/api/auth/kakao/me` | 쿠키 | 로그인 확인 |
| POST | `/api/auth/kakao/logout` | - | 세션 쿠키 삭제 |
| POST | `/api/alerts/natural` | 쿠키 | 자연어 한 문장으로 알림 등록 (AI 해석, trip/reminder 자동 판단) |
| POST | `/api/alerts` | 쿠키 | 항목을 직접 입력해 알림 등록 |
| GET | `/api/alerts` | 쿠키 | 내 알림 목록 |
| GET | `/api/alerts/{id}` | 쿠키 | 알림 상세 |
| DELETE | `/api/alerts/{id}` | 쿠키 | 알림 삭제 |
| GET | `/api/internal/alerts/due` | X-Internal-Key | 지금 확인할 알림 목록 (n8n) |
| POST | `/api/internal/alerts/{id}/dispatch` | X-Internal-Key | AI 문구 생성 후 카카오톡 발송 (n8n) |

## 6. 알림 데이터 형식 (Firestore `users/{user_id}/alerts/{alert_id}`)

```json
{
  "alert_id": "uuid",
  "user_id": "카카오 사용자 ID",
  "kind": "reminder",
  "notify_at": "2026-11-23T07:30:00+09:00",
  "repeat": "daily",
  "condition": { "type": "temperature", "op": "<", "value": 0 },
  "message": "영하면 패딩 챙기라고 알려줘",
  "location": { "lat": 37.5, "lon": 127.0, "place_name": "회사" },
  "status": "active",
  "sent": false
}
```

| 필드 | 설명 |
|---|---|
| `kind` | `trip`(약속·외출 출발 알림) 또는 `reminder`(정해진 시각 알림) |
| `notify_at` | 발송(확인) 시각. 반복 알림은 발송 후 다음 시각으로 바뀜 |
| `repeat` | `none`, `daily`(매일), `weekdays`(평일) |
| `condition` | 날씨 조건. `type`은 `temperature`(기온, 도) 또는 `precipitation`(강수확률, %) |
| `location` | 날씨를 확인할 위치 좌표 (없으면 서울 기준) |
| `status` | `active`, `sending`, `sent`, `expired` |
| `sent` | 1회 알림이 발송되었는지 (반복 알림은 항상 false) |

trip 알림은 위 필드에 더해 `departure`, `destination`, `arrival_at`, `notify_mode`(`departure`/`fixed`), `departure_coord`, `destination_coord`를 가집니다.

### 입력 예시와 해석 결과

| 입력 | kind | 해석 |
|---|---|---|
| 내일 오후 2시까지 서울역에서 강남역 가야 해 | trip | 도착 14:00, 이동 시간에 맞춰 출발 알림 |
| 금요일 7시 홍대 약속, 비 오면 알려줘 | trip | 강수확률 50% 이상일 때만 출발 알림 |
| 매일 아침 7시 반에 영하면 패딩 챙기라고 알려줘 | reminder | 매일 07:30, 기온 < 0일 때 |
| 평일마다 8시에 회사 날씨 알려줘 | reminder | 평일 08:00, 회사 위치 날씨, 조건 없음 |
