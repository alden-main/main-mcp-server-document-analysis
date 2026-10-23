# Gateway 연동 MCP 서버 공통 표준

## 목적과 적용 범위

이 문서는 여러 AI 서비스와 MCP 서버 사이에 Gateway를 도입하기 전에, 각 **MCP 서버가 공통으로 구현·문서화해야 할 운영 계약**을 정의한다. 현재 프로젝트는 Gateway와 MCP 서버만 연결된 공통 Docker 네트워크를 신뢰 경계로 사용한다.

이 문서는 특정 Gateway, ID 공급자, 프록시 제품 또는 LLM 공급자를 지정하지 않는다. Gateway의 인증 방식·라우팅·정책 엔진은 별도 설계 대상으로 둔다. 다만 서버가 Gateway 뒤에서 안전하고 예측 가능하게 동작하기 위한 최소 계약은 여기서 고정한다. 현재 프로젝트에서는 Gateway-MCP 내부 구간의 JWT, API key, 서명 claim, mTLS를 사용하지 않는다.

## 규범 표기

- **필수(MUST)**: Gateway 연동 대상 MCP 서버가 반드시 만족해야 한다.
- **권장(SHOULD)**: 특별한 근거가 없으면 만족해야 한다.
- **선택(MAY)**: 서버 특성에 따라 적용할 수 있다.

## 1. 전송과 네트워크 경계

| 항목 | 표준 |
|---|---|
| 원격 전송 | 필수: Streamable HTTP MCP를 사용한다. |
| MCP endpoint | 필수: 서비스 루트 기준 `/mcp`를 사용한다. Gateway는 외부 경로를 내부 `/mcp`로 라우팅할 수 있다. |
| 로컬 개발 | 선택: stdio MCP를 함께 제공할 수 있다. 원격 Gateway 경로의 대체물로 사용하지 않는다. |
| 외부 노출 | 필수: 운영 MCP 서버는 Gateway 또는 인증된 프록시 뒤의 사설 네트워크에서만 접근 가능해야 한다. Gateway를 우회하는 공개 포트를 두지 않는다. |
| 공통 MCP 네트워크 | 필수: Gateway와 MCP 서버만 `mcp-gateway-network`에 연결한다. AI 서비스는 이 네트워크에 연결하지 않고, Gateway만 AI 서비스 네트워크와 MCP 네트워크 양쪽에 연결한다. |
| 네트워크 생성 | 권장: `mcp-gateway-network`는 Docker `--internal` 네트워크로 생성한다. Compose에서는 현재 프로젝트의 외부 네트워크 이름 `mcp-gateway-network`를 그대로 사용한다. |
| TLS·토큰 | 현재 프로젝트: Gateway-MCP 내부 구간의 TLS, mTLS, JWT, API key, 서명 claim을 사용하지 않는다. Docker 네트워크 멤버십이 호출 신뢰의 근거다. |
| HTTP 메서드·세션 | 필수: Streamable HTTP의 MCP 프로토콜 요구를 그대로 지원한다. 임의 REST API를 MCP endpoint에 추가하지 않는다. |

## 2. 서비스 식별과 호환성

각 서버는 다음 정보를 배포 문서와 서비스 메타데이터에 필수로 제공한다.

| 필드 | 규칙 | 예시 |
|---|---|---|
| `service_id` | 조직 내 불변, 소문자 kebab-case | `medical-term-review` |
| `service_version` | Semantic Versioning | `1.2.0` |
| `mcp_endpoint` | 서비스 내부 endpoint | `/mcp` |
| `transport` | 원격 전송 방식 | `streamable-http` |
| `tool_contract_version` | 도구 schema 호환성 버전 | `v1` |
| `data_classification` | 처리 데이터의 등급 | `sensitive-medical` |

- 필수: `service_id`는 배포·이미지·감사 로그에서 같은 값을 사용한다.
- 필수: 기존 도구의 입력/출력 schema를 호환되지 않게 바꿀 때 `tool_contract_version` 또는 주 버전을 올린다.
- 권장: Gateway는 `service_id`와 도구명을 기준으로 라우팅·인가 정책을 적용한다.

## 3. 인증과 호출자 정체성

- 필수: 외부 호출의 인증·인가가 필요하면 AI 서비스와 Gateway의 경계에서 처리한다. MCP 서버는 인터넷에서 직접 호출될 수 없어야 한다.
- 필수: MCP 서버는 `mcp-gateway-network`에서 온 요청을 Gateway 요청으로 취급한다. 이 네트워크에 Gateway와 MCP 서버 외 컨테이너를 연결하지 않는다.
- 필수: MCP 서버는 JWT, API key, `Authorization`, claim, scope 헤더를 요구·해석·저장하지 않는다.
- 필수: Docker 관리자와 `mcp-gateway-network`에 컨테이너를 연결할 수 있는 주체는 신뢰할 수 있어야 한다.
- 선택: 향후 MCP 서버가 사용자·테넌트별 권한을 직접 판단해야 하면, 별도 계약으로 mTLS 또는 서명된 claim 검증을 도입한다. 임의 헤더만으로 identity를 전달해서는 안 된다.

## 4. 도구 권한(scope) 계약

현재 프로젝트의 MCP 서버는 Gateway 전용 네트워크를 신뢰하므로 도구별 scope를 검사하지 않는다. 사용자별 권한이 필요한 경우 Gateway가 AI 서비스 경계에서 정책을 평가한다. 아래 형식은 향후 사용자·테넌트별 권한을 도입할 때만 사용한다.

| 동작 | scope 예시 |
|---|---|
| 조회·검색 | `<service_id>:read` |
| 분석 실행 | `<service_id>:analyze` |
| 검토·제안 제출 | `<service_id>:submit` |
| 상태 변경·승인 | `<service_id>:decide` |
| 관리성 작업 | `<service_id>:admin` |

- 필수: 각 서버의 도구 문서에 Gateway 전용 네트워크 신뢰 모드와 데이터 변경 여부를 표시한다.
- 필수: 상태 변경 도구를 도입하면 사용자별 인가를 Gateway에서 수행할지, MCP 서버에도 검증을 추가할지 별도 계약으로 확정한다.

## 5. 공통 오류 계약

도구 수준의 예상 가능한 오류는 아래 형식을 사용한다.

```json
{
  "error": {
    "code": "stable_machine_code",
    "message": "민감한 원문·토큰·내부 경로를 포함하지 않는 설명",
    "retryable": false
  }
}
```

| 코드 | 의미 | 재시도 |
|---|---|---|
| `invalid_input` | 입력 schema·범위·형식 오류 | 아니오 |
| `not_found` | 요청한 공개 리소스·분석·식별자를 찾을 수 없음 | 아니오 |
| `conflict` | 멱등하지 않은 상태 전이 또는 버전 충돌 | 아니오 |
| `rate_limited` | 호출 한도 초과 | 예, `Retry-After` 존중 |
| `request_too_large` | 본문 또는 파일 크기 제한 초과 | 아니오 |
| `upstream_unavailable` | 필수 내부 의존성이 일시적으로 사용 불가 | 예 |
| `internal_error` | 예상하지 못한 서버 오류 | 보통 예 |

- 필수: 오류 코드는 안정된 기계 판독용 문자열이며, 내부 예외 문자열을 그대로 노출하지 않는다.
- 필수: HTTP/Gateway 차원의 인증·제한 오류와 MCP 도구 응답 오류의 책임을 문서화한다.
- 권장: `retryable=true`인 오류에는 재시도 조건과 최대 대기 시간을 응답 헤더 또는 Gateway 문서에 제공한다.

## 6. 추적성·감사·개인정보

- 필수: MCP 서버 로그에는 최소 `timestamp`, `service_id`, `service_version`, `tool_name`, 결과 코드를 남긴다.
- 권장: 사용자별 감사가 필요하면 Gateway가 `request_id`, 사용자·테넌트 식별자와 결과를 기록한다. MCP 서버에는 해당 식별자를 전달하지 않는다.
- 필수: 원문, 접근 토큰, 인증 헤더, 비밀번호, 진료 기록 등 민감 원문을 일반 로그·오류·추적 데이터에 기록하지 않는다.
- 선택: 테넌트 데이터 또는 사용자별 감사가 있는 배포는 Gateway에서 테넌트 경계 검증 및 사용자 식별자의 가명화를 수행한다.

## 7. 상태·확장성·멱등성

- 필수: 후속 호출에 필요한 식별자(예: `analysis_id`, `search_result_id`)가 여러 replica 중 어느 인스턴스에 요청되어도 검증 가능해야 한다.
- 필수: 프로세스 메모리만으로 보관한 상태가 있다면, 다중 replica 배포에서는 공유 저장소로 이전하거나 Gateway가 해당 수명 동안 sticky routing을 보장해야 한다.
- 필수: 상태 변경 도구는 가능한 경우 idempotency key를 받고, 동일 키의 재시도 결과를 일관되게 반환한다.
- 권장: 식별자는 추측하기 어려운 UUID 또는 동등한 무작위성을 사용한다.
- 권장: 서버는 시작 시 스키마 호환성·읽기 전용 데이터 버전·필수 의존성을 검증한다.

## 8. 리소스 한도와 복원력

각 서버는 다음 값을 문서화하고 Gateway 정책과 상한을 맞춘다.

- 최대 요청 본문 크기와 최대 입력 단위
- 도구별 timeout 및 Gateway timeout
- 동시 요청·세션·검색 결과 제한
- rate limit 단위(호출자, 테넌트, 도구 등)
- 재시도 가능한 의존성 및 backoff 정책

- 필수: 무제한 재시도, 무제한 결과, 무제한 입력을 허용하지 않는다.
- 필수: 시간 초과 또는 취소 뒤에도 상태 변경이 중복되지 않도록 설계한다.

## 9. 헬스체크와 운영 관찰성

- 필수: 컨테이너는 애플리케이션 프로세스가 실행 중인지 확인하는 healthcheck를 제공한다.
- 권장: Gateway 또는 오케스트레이터용 `/healthz` endpoint는 인증 없이도 민감 정보 없이 `200` 또는 `503`만 반환한다. MCP `/mcp` endpoint와 분리한다.
- 권장: readiness는 사전/DB 연결, 필수 schema 및 쓰기 저장소 상태를 확인한다.
- 필수: 메트릭·로그 라벨에는 `service_id`, `service_version`, 결과 코드, 도구명을 포함하고, 원문·토큰을 포함하지 않는다.

## 10. 서버별 도입 체크리스트

새 MCP 서버 또는 기존 서버를 Gateway에 연결하기 전에 다음을 확인한다.

- [ ] `/mcp` Streamable HTTP를 내부 네트워크에서 제공한다.
- [ ] `service_id`, 버전, 도구 계약 버전, 데이터 등급을 문서화했다.
- [ ] Gateway 전용 네트워크 신뢰 모드와 상태 변경 여부를 문서화했다.
- [ ] 공통 오류 형식과 안정된 오류 코드를 사용한다.
- [ ] MCP 로그에 서비스·도구·결과 코드가 있고, 사용자별 감사가 필요하면 Gateway가 이를 기록한다.
- [ ] 민감 원문·토큰이 로그·오류·감사 데이터에 없는지 검증했다.
- [ ] 다중 replica에서 식별자·세션·근거 검증이 유지되는지 검증했다.
- [ ] 요청 크기·timeout·결과 수·rate limit 상한을 문서화했다.
- [ ] healthcheck와 비민감 readiness 정책을 제공한다.
- [ ] Gateway와 MCP 서버만 `mcp-gateway-network`에 연결돼 있으며, Gateway 우회 경로와 공개 포트가 없다.

## 현재 프로젝트 적용 상태

| 항목 | 상태 | 비고 |
|---|---|---|
| Streamable HTTP `/mcp` | 적용 | `korean-standard-dictionary:8000/mcp` |
| Gateway 전용 네트워크 | 적용 | 외부 Docker 네트워크 `mcp-gateway-network` |
| AI 서비스 네트워크 분리 | 적용 대상 | AI 서비스는 별도 네트워크에만 연결하고 Gateway만 양쪽에 연결 |
| JWT·API key·claim·scope 검사 | 미적용 | Gateway-MCP 구간은 전용 네트워크 신뢰 모델을 사용 |
| 호스트 포트 공개 | 미적용 | Compose는 `expose: 8000`만 사용 |
| `/healthz` | 적용 | DB와 Kiwi 분석기 준비 상태를 확인 |

이 모델의 전제는 `mcp-gateway-network`에 Gateway와 MCP 서버 외 컨테이너를 연결하지 않고, Docker 관리자 권한을 신뢰하는 것이다. 이 전제가 바뀌면 JWT 자체를 임의로 추가하기보다 별도 보안 계약을 수립한다.
