// 버튼 클릭, api 호출 등 동작 구현

// Backend API 통신 테스트
fetch("http://127.0.0.1:8000/health")
    .then(response => response.json())
    .then(data => {
        console.log("Backend 연결 성공:", data);
    })
    .catch(error => {
        console.error("Backend 연결 실패:", error);
    });