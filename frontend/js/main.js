// 버튼 클릭, api 호출 등 동작 구현

// 백엔드가 프론트를 함께 서빙하므로 같은 주소("")를 사용
// Live Server(5500)로 따로 띄울 때만 아래 값을 "http://localhost:8000"으로 바꿔서 테스트
const API_BASE = "";

const views = {
    consent: document.getElementById("consent-view"),
    login: document.getElementById("login-view"),
    create: document.getElementById("create-view"),
    list: document.getElementById("list-view")
};

const logoutBtn = document.getElementById("logout-btn");

function showView(name) {
    Object.keys(views).forEach(function (key) {
        views[key].classList.toggle("hidden", key !== name);
    });
    logoutBtn.classList.toggle("hidden", name === "consent" || name === "login");
}

function getStored(key) {
    try {
        return localStorage.getItem(key);
    } catch (e) {
        return null;
    }
}

function setStored(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch (e) {
        return;
    }
}

// 로그인 쿠키를 함께 보내는 API 호출
function api(path, options) {
    const opts = Object.assign({ credentials: "include" }, options || {});
    return fetch(API_BASE + path, opts);
}

// 서버 오류 메시지(detail)를 꺼내기
function readError(res, fallback) {
    return res.json()
        .then(function (data) {
            if (data && typeof data.detail === "string") {
                return data.detail;
            }
            return fallback;
        })
        .catch(function () {
            return fallback;
        });
}

// 1. 개인정보 동의
const consentCheck = document.getElementById("consent-check");
const consentBtn = document.getElementById("consent-btn");

consentCheck.addEventListener("change", function () {
    consentBtn.disabled = !consentCheck.checked;
});

consentBtn.addEventListener("click", function () {
    setStored("consent", "agreed");
    showView("login");
});

// 2. 로그인 (카카오 OAuth 페이지로 이동)
document.getElementById("login-btn").addEventListener("click", function () {
    document.getElementById("login-status").textContent = "카카오 로그인 페이지로 이동합니다.";
    window.location.href = API_BASE + "/api/auth/kakao/login";
});

logoutBtn.addEventListener("click", function () {
    api("/api/auth/kakao/logout", { method: "POST" })
        .finally(function () {
            showView("login");
        });
});

// 3. 알림 등록 (자연어 한 문장 → AI 해석)
document.getElementById("create-form").addEventListener("submit", function (e) {
    e.preventDefault();

    const input = document.getElementById("plan-input");
    const status = document.getElementById("create-status");
    const submitBtn = e.target.querySelector("button[type=submit]");
    const text = input.value.trim();

    if (!text) {
        status.textContent = "외출 계획을 입력해 주세요.";
        return;
    }

    status.textContent = "AI가 계획을 정리하고 있습니다.";
    submitBtn.disabled = true;

    api("/api/alerts/natural", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: text })
    })
        .then(function (res) {
            if (res.status === 401) {
                showView("login");
                throw new Error("로그인이 필요합니다.");
            }
            if (!res.ok) {
                return readError(res, "알림을 등록하지 못했습니다.").then(function (msg) {
                    throw new Error(msg);
                });
            }
            return res.json();
        })
        .then(function () {
            input.value = "";
            status.textContent = "";
            loadAlerts();
            showView("list");
        })
        .catch(function (err) {
            status.textContent = err.message || "알림을 등록하지 못했습니다. 서버 연결을 확인해 주세요.";
        })
        .finally(function () {
            submitBtn.disabled = false;
        });
});

document.getElementById("go-list").addEventListener("click", function () {
    loadAlerts();
    showView("list");
});

document.getElementById("go-create").addEventListener("click", function () {
    showView("create");
});

// 4. 알림 목록
function loadAlerts() {
    const listEl = document.getElementById("alert-list");
    const emptyEl = document.getElementById("list-empty");

    listEl.innerHTML = "";
    emptyEl.textContent = "불러오는 중입니다.";

    api("/api/alerts")
        .then(function (res) {
            if (res.status === 401) {
                showView("login");
                throw new Error("unauthorized");
            }
            if (!res.ok) {
                throw new Error("load failed");
            }
            return res.json();
        })
        .then(function (data) {
            const items = Array.isArray(data) ? data : (data.alerts || []);
            if (items.length === 0) {
                emptyEl.textContent = "등록된 알림이 없습니다.";
                return;
            }
            emptyEl.textContent = "";
            items.forEach(function (item) {
                listEl.appendChild(renderAlert(item));
            });
        })
        .catch(function () {
            emptyEl.textContent = "알림을 불러오지 못했습니다. 서버 연결을 확인해 주세요.";
        });
}

const STATUS_LABELS = {
    active: "대기 중",
    repeat: "반복 중",
    sending: "발송 중",
    sent: "발송 완료",
    expired: "기간 만료"
};

const OP_TEXT = {
    "<": "미만",
    "<=": "이하",
    ">": "초과",
    ">=": "이상"
};

const REPEAT_TEXT = {
    daily: "매일",
    weekdays: "평일마다"
};

function conditionText(condition) {
    if (!condition || !condition.type) {
        return "";
    }
    // 예전 형식
    if (condition.type === "rain") {
        return "비가 올 때만";
    }
    if (condition.type === "temp_below") {
        return condition.value + "도 미만일 때만";
    }
    if (condition.type === "temp_above") {
        return condition.value + "도 초과일 때만";
    }
    // 현재 형식 {type, op, value}
    const op = OP_TEXT[condition.op] || "";
    if (condition.type === "precipitation") {
        return "강수확률 " + condition.value + "% " + op + "일 때만";
    }
    if (condition.type === "temperature") {
        return "기온 " + condition.value + "도 " + op + "일 때만";
    }
    return "";
}

function formatClock(value) {
    const date = new Date(value);
    if (isNaN(date.getTime())) {
        return value;
    }
    return String(date.getHours()).padStart(2, "0") + ":" + String(date.getMinutes()).padStart(2, "0");
}

function renderAlert(item) {
    const li = document.createElement("li");
    li.className = "card";

    const head = document.createElement("div");
    head.className = "card-head";

    const isReminder = item.kind === "reminder";
    const repeatText = REPEAT_TEXT[item.repeat] || "";

    const route = document.createElement("p");
    route.className = "card-route";
    if (isReminder) {
        const place = (item.location && item.location.place_name) || item.location_name;
        route.textContent = (repeatText ? repeatText + " " : "") + formatClock(item.notify_at) + " 알림" + (place ? " · " + place : "");
    } else {
        route.textContent = (item.departure || "출발지 미정") + " → " + (item.destination || "도착지 미정");
    }

    const statusBadge = document.createElement("span");
    let statusKey = item.status || (item.sent ? "sent" : "active");
    if (statusKey === "active" && item.repeat && item.repeat !== "none") {
        statusKey = "repeat";
    }
    statusBadge.className = "status-badge status-" + statusKey;
    statusBadge.textContent = STATUS_LABELS[statusKey] || statusKey;

    head.appendChild(route);
    head.appendChild(statusBadge);

    const time = document.createElement("p");
    time.className = "card-time";
    let timeText;
    if (isReminder) {
        timeText = (repeatText ? "다음 알림 " : "알림 ") + formatTime(item.notify_at);
    } else {
        timeText = "도착 " + formatTime(item.arrival_at);
        if (item.notify_mode === "departure") {
            timeText += " / 이동 시간에 맞춰 출발 알림";
        } else {
            timeText += " / 알림 " + formatTime(item.notify_at);
        }
    }
    const cond = conditionText(item.condition);
    if (cond) {
        timeText += " (" + cond + ")";
    }
    time.textContent = timeText;

    const isTemplateMessage = item.final_message && item.ai_generated === false;
    const message = document.createElement("p");
    message.className = "card-message";
    message.textContent = item.final_message || item.message || "알림 문구를 준비하고 있습니다.";
    if (isTemplateMessage) {
        message.textContent = message.textContent.replace(/\n\(AI가 작성한 메시지\)$/, "");
    }

    const foot = document.createElement("div");
    foot.className = "card-foot";

    if (item.final_message || item.ai_parsed) {
        const badge = document.createElement("span");
        badge.className = "ai-badge";
        badge.textContent = item.final_message
            ? (isTemplateMessage ? "기본 알림" : "AI 작성 메시지")
            : "AI 해석";
        foot.appendChild(badge);
    }

    const del = document.createElement("button");
    del.type = "button";
    del.className = "text-btn delete-btn";
    del.textContent = "삭제";
    del.setAttribute("aria-label", (item.destination || "알림") + " 알림 삭제");
    del.addEventListener("click", function () {
        if (!item.alert_id) {
            return;
        }
        del.disabled = true;
        api("/api/alerts/" + encodeURIComponent(item.alert_id), { method: "DELETE" })
            .then(function (res) {
                if (!res.ok) {
                    throw new Error("delete failed");
                }
                li.remove();
            })
            .catch(function () {
                del.disabled = false;
            });
    });

    foot.appendChild(del);

    li.appendChild(head);
    li.appendChild(time);
    li.appendChild(message);
    li.appendChild(foot);

    return li;
}

function formatTime(value) {
    if (!value) {
        return "미정";
    }
    const date = new Date(value);
    if (isNaN(date.getTime())) {
        return value;
    }
    const hour = String(date.getHours()).padStart(2, "0");
    const minute = String(date.getMinutes()).padStart(2, "0");
    return (date.getMonth() + 1) + "월 " + date.getDate() + "일 " + hour + ":" + minute;
}

// 시작 화면 결정
// 로그인 여부는 서버의 세션 쿠키로 확인 (/me)
function start() {
    const params = new URLSearchParams(window.location.search);
    const loginResult = params.get("login");
    if (loginResult) {
        window.history.replaceState({}, document.title, window.location.pathname);
    }

    if (getStored("consent") !== "agreed") {
        showView("consent");
        return;
    }

    api("/api/auth/kakao/me")
        .then(function (res) {
            if (res.ok) {
                showView("create");
                return;
            }
            showView("login");
            if (loginResult === "fail") {
                document.getElementById("login-status").textContent = "로그인에 실패했습니다. 다시 시도해 주세요.";
            }
        })
        .catch(function () {
            showView("login");
            document.getElementById("login-status").textContent = "서버에 연결하지 못했습니다. 잠시 후 다시 시도해 주세요.";
        });
}

start();
