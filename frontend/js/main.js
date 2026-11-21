// 백엔드 API 통신 테스트
fetch("http://localhost:8000/health", {
    credentials: "include"
})
    .then(response => response.json())
    .then(data => {
        console.log("Backend 연결 성공:", data);
    })
    .catch(error => {
        console.error("Backend 연결 실패:", error);
    });
