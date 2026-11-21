// 버튼 클릭, api 호출 등 동작 구현

// 배포 시 Render 백엔드 주소로 변경
const API_BASE = "http://127.0.0.1:8000";

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

function removeStored(key) {
    try {
        localStorage.removeItem(key);
    } catch (e) {
        return;
    }
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

// 로그인 후 돌아왔을 때 주소에서 사용자 정보 읽기
// TODO: 백엔드가 전달하는 파라미터 이름 확인 후 맞출 것
function handleLoginCallback() {
    const params = new URLSearchParams(window.location.search);
    const userId = params.get("user_id");

    if (!userId) {
        return;
    }

    setStored("user_id", userId);
    window.history.replaceState({}, document.title, window.location.pathname);
}

logoutBtn.addEventListener("click", function () {
    removeStored("user_id");
    showView("login");
});

// 3. 알림 등록
document.getElementById("create-form").addEventListener("submit", function (e) {
    e.preventDefault();

    const input = document.getElementById("plan-input");
    const status = document.getElementById("create-status");
    const text = input.value.trim();

    if (!text) {
        status.textContent = "외출 계획을 입력해 주세요.";
        return;
    }

    status.textContent = "AI가 계획을 정리하고 있습니다.";

    fetch(API_BASE + "/api/alerts", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: getStored("user_id"), text: text })
    })
        .then(function (res) {
            if (!res.ok) {
                throw new Error("create failed");
            }
            input.value = "";
            status.textContent = "";
            loadAlerts();
            showView("list");
        })
        .catch(function () {
            status.textContent = "알림을 등록하지 못했습니다. 서버 연결을 확인해 주세요.";
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

    const userId = encodeURIComponent(getStored("user_id") || "");

    fetch(API_BASE + "/api/alerts?user_id=" + userId)
        .then(function (res) {
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

function renderAlert(item) {
    const li = document.createElement("li");
    li.className = "card";

    const route = document.createElement("p");
    route.className = "card-route";
    route.textContent = (item.departure || "출발지 미정") + " → " + (item.destination || "도착지 미정");

    const time = document.createElement("p");
    time.className = "card-time";
    time.textContent = "도착 " + formatTime(item.arrival_at) + " / 알림 " + formatTime(item.notify_at);

    const message = document.createElement("p");
    message.className = "card-message";
    message.textContent = item.message || "알림 문구를 준비하고 있습니다.";

    const badge = document.createElement("span");
    badge.className = "ai-badge";
    badge.textContent = "AI 생성";

    li.appendChild(route);
    li.appendChild(time);
    li.appendChild(message);
    li.appendChild(badge);

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
handleLoginCallback();

if (getStored("consent") !== "agreed") {
    showView("consent");
} else if (!getStored("user_id")) {
    showView("login");
} else {
    showView("create");
}
