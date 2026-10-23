# macOS 개발 환경에서 Linux A100 서버로 배포하기

Report Validation MCP를 macOS에서 개발한 뒤 Linux A100 서버로 배포하는 절차다. 이 서비스는 CPU 기반 MCP 서버로 GPU, CUDA, NVIDIA Container Toolkit, `--gpus` 옵션이 필요 없다.

## 배포 구조

```text
AI/LLM service network ─┐
                        ├─ Gateway ─ mcp-gateway-network (internal) ─ report-validation-mcp
외부 클라이언트 ─────────┘
```

- Gateway만 AI/LLM 서비스 network와 `mcp-gateway-network` 양쪽에 연결한다.
- MCP 컨테이너는 `mcp-gateway-network`에만 연결하고 호스트 포트를 공개하지 않는다.
- 이 network에는 Gateway와 MCP 외 컨테이너를 연결하지 않는다. Docker network 멤버십이 호출 신뢰 경계다.
- MCP는 JWT, API key, Authorization, claim, scope 헤더를 해석하지 않는다. 사용자 인증·인가·감사는 Gateway가 담당한다.

예시는 이미지 태그 `0.1.0`, 서버 경로 `/srv/report-validation-mcp`를 사용한다. 일반적인 A100 서버는 x86_64이므로 macOS Apple Silicon에서도 `linux/amd64` 이미지를 빌드한다.

## 1. macOS에서 검증 및 이미지 빌드

```bash
uv run --python 3.12 python -m unittest discover -s tests -v
docker compose config --quiet

docker buildx build \
  --platform linux/amd64 \
  --tag report-validation-mcp:0.1.0 \
  --load \
  .

docker image inspect report-validation-mcp:0.1.0 \
  --format '{{.Os}}/{{.Architecture}}'
# 기대값: linux/amd64

mkdir -p dist
docker save report-validation-mcp:0.1.0 | gzip > dist/report-validation-mcp_0.1.0_linux-amd64.tar.gz
shasum -a 256 dist/report-validation-mcp_0.1.0_linux-amd64.tar.gz
```

대상 서버가 arm64라면 `linux/amd64`를 `linux/arm64`로 바꾼다. 사설 registry가 있으면 이미지 아카이브 전송 대신 push/pull을 사용해도 된다.

## 2. Linux 서버로 전달

```bash
ssh <server-user>@<server-host> \
  'sudo install -d -m 0755 /srv/report-validation-mcp'

scp compose.yaml <server-user>@<server-host>:/tmp/report-validation-compose.yaml
scp dist/report-validation-mcp_0.1.0_linux-amd64.tar.gz \
  <server-user>@<server-host>:/tmp/
```

서버에서 macOS에서 기록한 SHA-256을 대조한 뒤 이미지를 불러온다.

```bash
ssh <server-user>@<server-host>
cd /tmp
sha256sum report-validation-mcp_0.1.0_linux-amd64.tar.gz
sudo mv report-validation-compose.yaml /srv/report-validation-mcp/compose.yaml
sudo docker load -i report-validation-mcp_0.1.0_linux-amd64.tar.gz
sudo docker image inspect report-validation-mcp:0.1.0 \
  --format '{{.Os}}/{{.Architecture}}'
```

## 3. Gateway 전용 network와 MCP 시작

`compose.yaml`은 외부 Docker network `mcp-gateway-network`를 사용한다. Gateway가 이미 만들었다면 다시 만들지 않는다.

```bash
sudo docker network inspect mcp-gateway-network >/dev/null 2>&1 \
  || sudo docker network create --internal mcp-gateway-network

cd /srv/report-validation-mcp
sudo docker compose up -d --no-build
sudo docker compose ps
sudo docker compose logs --tail=100 report-validation-mcp
```

서버에서 소스로 재빌드하지 않도록 항상 `--no-build`를 사용한다. Gateway와 MCP 외 컨테이너가 연결되지 않았는지 확인한다.

```bash
sudo docker network inspect mcp-gateway-network
```

## 4. 정상 상태와 Gateway 연결 확인

호스트 포트는 열리지 않는다. 컨테이너 내부에서 healthcheck를 확인한다.

```bash
CONTAINER_ID=$(sudo docker compose -f /srv/report-validation-mcp/compose.yaml ps -q report-validation-mcp)
sudo docker inspect --format '{{.State.Health.Status}}' "$CONTAINER_ID"
sudo docker exec "$CONTAINER_ID" python -c \
  "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/healthz').read().decode())"
```

Gateway의 MCP 대상은 `http://report-validation-mcp:8000/mcp`이고 healthcheck 대상은 `http://report-validation-mcp:8000/healthz`다. Gateway는 MCP의 기본 최대 본문 1 MiB 이하, 30초 timeout 및 호출자별 rate limit을 적용해야 한다.

보고서가 한 요청의 문자열 제한(기본 100,000자) 또는 전체 JSON-RPC 본문 제한(기본 1 MiB)을
넘으면, Gateway는 문단 또는 문장 경계에서 보고서를 분할해 조각별로 MCP를 호출해야 한다.
바이트 기준으로 원문을 임의 절단하면 문장·인코딩·근거 문맥이 손상될 수 있다. 반환 citation의
offset은 조각의 `report.text` 기준이므로, Gateway는 각 조각의 원본 시작 offset을 보관하고
필요할 때 원본 문서 좌표로 환산한다. 기준·검색어·semantic candidate를 포함한 JSON 구조도
1 MiB 본문 제한에 포함된다.

## 업데이트와 롤백

새 태그의 이미지를 빌드·테스트·전달·`docker load`한 뒤 Compose의 `image` 태그를 새 값으로 바꾸고 다음을 실행한다.

```bash
cd /srv/report-validation-mcp
sudo docker compose up -d --no-build
```

문제가 있으면 Compose 태그를 이전 이미지로 되돌리고 같은 명령을 실행한다. 이전 이미지는 롤백 검증 전까지 삭제하지 않는다.

## 문제 해결

| 증상 | 조치 |
| --- | --- |
| `exec format error` | 서버 `uname -m`과 이미지의 OS/Architecture를 확인하고 맞는 `--platform`으로 다시 빌드한다. |
| external network를 찾지 못함 | `sudo docker network create --internal mcp-gateway-network`를 한 번 실행한다. |
| healthcheck가 `unhealthy` | `sudo docker compose logs report-validation-mcp`으로 원인을 확인한다. 호스트 포트를 추가하지 않는다. |
| Gateway가 연결하지 못함 | Gateway가 같은 network에 연결돼 있고 `http://report-validation-mcp:8000/mcp`를 사용 중인지 확인한다. |
| AI 서비스가 MCP에 직접 연결됨 | AI 서비스 컨테이너를 `mcp-gateway-network`에서 분리한다. Gateway만 두 network에 연결한다. |
