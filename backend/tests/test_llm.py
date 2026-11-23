import json
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch

import httpx

from app.services import llm


class LLMTest(unittest.IsolatedAsyncioTestCase):
    now = datetime.fromisoformat("2026-11-23T23:50:00+09:00")

    async def test_parse_trip_with_a_separate_notification_time(self):
        text = "내일 오전 9시까지 서울역에서 강남역 가야 해. 오전 8시에 알려줘"
        model_output = {
            "input_issue": None,
            "kind": "trip",
            "departure": "서울역",
            "destination": "강남역",
            "arrival_at": "2026-11-24T09:00:00+09:00",
            "send_at": "2026-11-24T08:00:00+09:00",
            "repeat": "none",
        }
        response = f"```json\n{json.dumps(model_output, ensure_ascii=False)}\n```"
        with patch.object(llm, "chat", AsyncMock(return_value=response)) as chat:
            result = await llm.parse_outing_text(text, self.now)

        self.assertEqual(result["kind"], "trip")
        self.assertEqual(result["location"], "강남역")
        self.assertEqual(result["arrival_at"].isoformat(), model_output["arrival_at"])
        self.assertEqual(result["send_at"].isoformat(), model_output["send_at"])
        messages = chat.await_args.args[0]
        self.assertIn("2026-11-23T23:50+09:00 (월요일)", messages[0]["content"])
        self.assertEqual(messages[1], {"role": "user", "content": text})
        self.assertEqual(chat.await_args.kwargs["temperature"], 0.0)

    async def test_parse_reminder_preparations_and_conditions(self):
        cases = (
            ("20분 뒤에 우산 챙기라고 알려줘", "2026-11-24T00:10:00+09:00", "none", "우산", None),
            (
                "평일 아침 7시 반에 영하면 패딩 챙기라고 알려줘",
                "2026-11-24T07:30:00+09:00", "weekdays", "패딩",
                {"type": "temperature", "op": "<", "value": 0},
            ),
            (
                "매일 7시 반에 강수확률 70% 이상이면 우산 챙기라고 알려줘",
                "2026-11-24T07:30:00+09:00", "daily", "우산",
                {"type": "precipitation", "op": ">=", "value": 70},
            ),
            (
                "매일 아침 7시에 강수확률이 40% 이상이면 우산을 챙기라고 알려줘",
                "2026-11-24T07:00:00+09:00", "daily", "우산",
                {"type": "precipitation", "op": ">=", "value": 40},
            ),
        )
        for text, send_at, repeat, items, condition in cases:
            with self.subTest(text=text):
                response = json.dumps({
                    "kind": "reminder", "send_at": send_at, "repeat": repeat,
                    "items_hint": items, "condition": condition,
                })
                with patch.object(llm, "chat", AsyncMock(return_value=response)):
                    result = await llm.parse_outing_text(text, self.now)

                self.assertEqual(result["send_at"].isoformat(), send_at)
                self.assertEqual(result["repeat"], repeat)
                self.assertEqual(result["items_hint"], items)
                self.assertEqual(result["condition"], condition)
                self.assertIsNone(result["location"])

    async def test_explicit_weather_range_is_rejected_before_model_call(self):
        requests = (
            "7시~20시 강수확률이 40% 이상이면 알려줘",
            "매일 아침 7시에, 오전 7시부터 오후 8시까지 강수확률이 40% 이상이면 우산을 챙기라고 알려줘",
            "07:00–20:00 사이의 날씨를 매일 아침 6시에 알려줘",
            "매일 오전 6시에 7~20시 동안 비 오면 알려줘",
        )
        for text in requests:
            with self.subTest(text=text), patch.object(llm, "chat", AsyncMock()) as chat:
                with self.assertRaisesRegex(llm.AlertInputError, "시각을 한 시점으로"):
                    await llm.parse_outing_text(text, self.now)
                chat.assert_not_awaited()

    async def test_model_detected_weather_range_is_rejected_even_with_send_time(self):
        text = "매일 아침 7시에 아침부터 퇴근할 때까지 비가 올지 알려줘"
        response = json.dumps({
            "input_issue": "weather_time_range",
            "kind": "reminder",
            "send_at": "2026-11-24T07:00:00+09:00",
        })
        with patch.object(llm, "chat", AsyncMock(return_value=response)):
            with self.assertRaisesRegex(llm.AlertInputError, "날씨를 확인할 시간 범위"):
                await llm.parse_outing_text(text, self.now)

    async def test_multiple_alerts_are_rejected_instead_of_registering_one(self):
        cases = (
            (
                "매일 아침 7시에 영하면 패딩 챙기라고 알려줘. 내일 오전 9시까지 강남역도 가야 해",
                {"input_issue": "multiple_alerts"},
            ),
            (
                "매일 아침 7시에 물 마시라고 알려주고, 오후 8시에는 운동하라고 알려줘",
                {"input_issue": "multiple_alerts", "kind": "reminder", "send_at": "2026-11-24T07:00:00+09:00"},
            ),
        )
        for text, model_output in cases:
            with self.subTest(text=text), patch.object(llm, "chat", AsyncMock(return_value=json.dumps(model_output))):
                with self.assertRaisesRegex(llm.AlertInputError, "한 번에 하나씩"):
                    await llm.parse_outing_text(text, self.now)

    async def test_invalid_weather_conditions_stop_registration(self):
        conditions = (
            {"type": "temperature", "op": "<"},
            {"type": "precipitation", "op": ">=", "value": 120},
            {"type": "precipitation", "value": 70},
            {"type": "temperature", "op": "<", "value": "NaN"},
        )
        for condition in conditions:
            with self.subTest(condition=condition):
                response = json.dumps({"kind": "reminder", "condition": condition})
                with patch.object(llm, "chat", AsyncMock(return_value=response)):
                    with self.assertRaises(llm.LLMError):
                        await llm.parse_outing_text("내일 비 오면 알려줘", self.now)

    async def test_invalid_json_raises_llm_error(self):
        with patch.object(llm, "chat", AsyncMock(return_value="{잘못된 응답}")):
            with self.assertRaises(llm.LLMError):
                await llm.parse_outing_text("20분 뒤에 알려줘", self.now)

    async def test_compose_marks_missing_and_past_departure_times(self):
        cases = (
            (None, "출발 권장 시각: 알 수 없음", "출발 시점: 알 수 없음"),
            (self.now, "출발 권장 시각: 오후 11:50", "출발 시점: 지금 출발"),
            (datetime.fromisoformat("2026-11-24T00:10:00+09:00"),
             "출발 권장 시각: 오전 12:10", "출발 시점: 예정"),
        )
        for leave_at, time_text, state_text in cases:
            with self.subTest(leave_at=leave_at):
                with patch.object(llm, "chat", AsyncMock(return_value="강남역 약속이 있어요.")) as chat:
                    message, generated = await llm.compose_alert_message(
                        {"kind": "trip", "destination": "강남역"}, None, None, leave_at, self.now,
                    )

                facts = chat.await_args.args[0][1]["content"]
                self.assertIn(time_text, facts)
                self.assertIn(state_text, facts)
                self.assertIn("날씨 정보 없음", facts)
                self.assertEqual(message, f"강남역 약속이 있어요.\n{llm.AI_LABEL}")
                self.assertTrue(generated)

    async def test_compose_limits_body_and_adds_one_ai_label(self):
        model_output = "가" * 130 + f"\n{llm.AI_LABEL}\n{llm.AI_LABEL}"
        with patch.object(llm, "chat", AsyncMock(return_value=model_output)):
            message, generated = await llm.compose_alert_message(
                {"kind": "reminder"}, None, None, None, self.now,
            )

        body, label = message.splitlines()
        self.assertEqual(len(body), 120)
        self.assertEqual(label, llm.AI_LABEL)
        self.assertTrue(generated)

    async def test_null_content_uses_a_template_without_an_ai_label(self):
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, json={"choices": [{"message": {"content": None}}]})
        )
        client = httpx.AsyncClient(transport=transport)
        with (
            patch.object(llm, "LLM_API_KEY", "test-only"),
            patch.object(llm, "LLM_MODEL", "test-model"),
            patch.object(llm.httpx, "AsyncClient", return_value=client),
        ):
            message, generated = await llm.compose_alert_message(
                {"kind": "trip", "destination": "강남역"}, None, 20, self.now, self.now,
            )

        self.assertFalse(generated)
        self.assertIn("지금 출발", message)
        self.assertIn("20분", message)
        self.assertNotIn(llm.AI_LABEL, message)

    async def test_template_uses_available_weather(self):
        alert = {"kind": "reminder", "message": "외출 준비 시간입니다."}
        with patch.object(llm, "chat", AsyncMock(side_effect=llm.LLMError("timeout"))) as chat:
            message, generated = await llm.compose_alert_message(
                alert, {"temperature": 0, "precipitation": 0.2}, None, None, self.now,
            )
            facts = chat.await_args.args[0][1]["content"]
            without_weather, _ = await llm.compose_alert_message(
                alert, {"temperature": None, "precipitation": None}, None, None, self.now,
            )

        self.assertFalse(generated)
        self.assertIn("기온 0도, 현재 강수량 0.2mm", facts)
        self.assertIn("우산을 챙기세요", message)
        self.assertNotIn("날씨", without_weather)
