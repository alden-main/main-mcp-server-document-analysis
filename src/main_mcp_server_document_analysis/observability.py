"""민감 원문을 보관하지 않는 최소 감사와 health 상태를 제공한다."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True)
class AuditEvent:
    """원문·citation·토큰을 제외한 안전한 감사 이벤트다."""

    request_id: str | None
    service_id: str
    service_version: str
    tool_name: str
    result_code: str
    standard_version: str | None
    duration_ms: int


class SafeAuditLog:
    """테스트와 작은 배포에서 사용할 메모리 기반 안전 감사 저장소다."""

    def __init__(self) -> None:
        """비어 있는 이벤트 목록을 만든다."""
        self.events: list[AuditEvent] = []

    def record(self, *, request_id: str | None, tool_name: str, result_code: str, standard_version: str | None, started_at: float) -> None:
        """허용 목록의 metadata만 감사 이벤트로 추가한다."""
        self.events.append(AuditEvent(
            request_id, "report-validation", "0.1.0", tool_name,
            result_code, standard_version, int((perf_counter() - started_at) * 1000),
        ))

    def health(self, ready: bool) -> dict[str, str]:
        """민감정보 없는 liveness/readiness 상태를 반환한다."""
        return {"status": "ok" if ready else "unavailable"}
