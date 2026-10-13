# 로그인 웹앱: 실행과 운영

매일 백업의 실제 실행 주기, 재부팅 자동 시작 점검 결과와 백업 실패·디스크 부족 확인 절차는 [OPERATIONS.md](OPERATIONS.md)를 참고하세요.

2026-10-13 KST. 사용자 승인 후 라즈베리파이 배포와 8443 Funnel 공개 완료. 기존 서비스와 443 Funnel 보존 확인. 실제 데이터 이전·운영 관리자 비밀번호 설정은 사용자가 직접 수행합니다.

후속 완료: 사용자가 관리자 비밀번호를 직접 설정했습니다. 이후 사용자 요청으로 원본 데스크톱 DB를 읽기 전용으로 백업하고4개 기록을 웹 저장소에 추가형 이전했습니다. 기존 웹0개→4개, 충돌0개. 로그인된 실제 화면의 채용1개·공모전3개·복수 일정 확인. 원본 DB·앱·DMG 해시 보존. 개인 백업 위치는 프로젝트 var/migrations/20261013-224359/이며 Git에서 제외됩니다. 아래 빈 운영 저장소 설명은 최초 배포 시점의 기록입니다.

## 현재 운영 상태와 비밀번호 설정

- 확인된 주소: https://pi-home.tail5eceb8.ts.net:8443/
- 서버 경로: /home/jinho/News_idea-web. 컨테이너: news-idea-web-1. 데이터 볼륨: news-idea_news-data.
- 운영 저장소는 기록0개, 관리자0개, 세션0개로 배포. 비밀번호 설정 전에는 모든 로그인이 실패하며 데이터 API 접근도 차단됩니다. 기본·임시 운영 비밀번호는 없습니다.
- 테스트 비밀번호는 별도 QA 컨테이너의 메모리에만 생성·사용했고 QA 컨테이너와 볼륨은 제거했습니다. 운영 볼륨에 테스트 데이터·계정을 넣지 않았습니다.

Mac 터미널에서 다음 명령을 사용자가 직접 실행합니다. SSH 인증은 기존 방식이며 비밀번호는 숨김 입력 두 번으로 설정합니다. 코드·명령 인수·환경 변수·채팅에 비밀번호를 넣지 마세요.

```sh
rtk ssh -t jinho@100.84.155.62 'cd /home/jinho/News_idea-web && docker compose -p news-idea -f compose.web.yml exec web python webapp.py --set-password'
```

사용자 요청에 따라 최소 길이를10자로 변경했습니다. 10자 이상 비밀번호 설정 후 위 HTTPS 주소에서 로그인합니다. 서버 재시작 없이 적용됩니다. 같은 명령으로 비밀번호를 변경하면 기존 세션과 로그인 제한 기록이 초기화됩니다. 사용자 비밀번호를 에이전트에게 알려줄 필요는 없습니다.

검증: ARM64 Python15개, 내부 HTTP8개, 서버 HTTPS7개, 공개 DNS의 Funnel 릴레이에 직접 연결한 모바일 Chromium6개 통과. 운영 컨테이너 전환 후 공개 주소의 로그인 화면·미인증 API 차단도 검증. 공개 릴레이 경로는 MagicDNS를 우회했지만 휴대폰 셀룰러 시험과 서버 전체 재부팅은 수행하지 않았습니다. 기존 서비스 보존을 위해 전체 재부팅하지 않았습니다.

Docker 커널 memory cgroup은 지원되지 않습니다. Compose의 적용되지 않는 mem_limit 대신 Linux 앱 프로세스의 가상 주소 공간에 512MiB RLIMIT_AS 상한을 설정했고 /proc/1/limits에서 확인했습니다. 이는 컨테이너 전체 RAM 제한과 다릅니다. CPU1개 제한·읽기 전용 루트·로그5MB×3·재시작 정책·건강 상태를 실제 확인했습니다. 커널·부팅 옵션은 변경하지 않았습니다.

## 범위와 저장소

개인 관리자 계정 한 개만 지원합니다. 회원가입·추가 계정·첨부파일 업로드는 없습니다. 관리자만 전체 기록과 백업에 접근합니다. 다중 사용자로 확대할 때는 레코드 소유자와 백업 범위를 별도로 설계해야 합니다.

기존 desktop.py, store.py, static/app.js, macOS 앱·DMG와 사용자 DB는 보존합니다. 웹앱은 독립 SQLite 두 개를 사용합니다: news-idea.sqlite3(기록), auth.sqlite3(비밀번호 해시·세션·시도 제한). 최초 웹 실행은 빈 기록이며 기존 북마크·개인 데이터를 자동 발견하거나 가져오지 않습니다. 소스 변경 전 사본은 /tmp/news-idea-before-web-20261013에 있으며 임시 폴더이므로 장기 백업 위치는 아닙니다.

## 로컬 실행

Python 3.13을 사용하세요. 시스템 Python 3.9에는 scrypt가 없어 지원하지 않습니다.

```sh
rtk python3.13 -m venv .venv-web
rtk .venv-web/bin/pip install -r requirements-web.txt
rtk .venv-web/bin/python webapp.py --data-root /tmp/news-idea-web-dev --set-password
rtk .venv-web/bin/python webapp.py --data-root /tmp/news-idea-web-dev
```

http://127.0.0.1:4310 을 엽니다. 비밀번호는 터미널의 숨김 입력으로 직접 지정합니다. 명령 인수·환경 변수·채팅에 비밀번호를 입력하지 마세요. 기본 웹 데이터 위치는 프로젝트 var/web이며 Git에서 제외됩니다. 테스트 경로와 실사용 경로를 구분하세요.

```sh
rtk .venv-web/bin/python -W error::ResourceWarning -m unittest discover -s tests -v
rtk node --check static/app.js
rtk node --check static/web.js
PLAYWRIGHT_MODULE=/path/to/playwright rtk node tests/web-browser-tests.cjs
```

브라우저 테스트는 로컬 4311과 임시 DB를 사용하며 Chromium이 필요합니다. 테스트에 적힌 비밀번호는 합성 테스트 전용이고 관리자 초기 비밀번호가 아닙니다. 테스트는 실제 사용자 데이터를 사용하지 않습니다.

## 인증과 노출

- Werkzeug scrypt 해시, 임의 256비트 세션 토큰. DB에는 토큰 SHA-256만 저장. 유효기간 12시간, HttpOnly·SameSite=Strict·HTTPS Secure 쿠키.
- 로그아웃은 DB 세션 삭제, 비밀번호 재설정은 모든 세션 삭제. 브라우저 뒤로 이동 시 재검사.
- 로그인 시도는 전체 관리자 계정에 대해 15분 동안 5회 제한하며 SQLite에 보존. 프록시 헤더로 우회할 수 없지만 공격자가 잠시 관리자 로그인을 막을 수 있음. 필요하면 터미널에서 비밀번호 재설정으로 제한 해제.
- 모든 기록·백업 API와 앱 화면·앱 자산에 인증 검사. 변경 요청은 정확한 Origin과 세션 CSRF 토큰 필요. 로그인도 Origin 검사. Host도 지정 origin과 일치해야 함.
- 공개 예외는 로그인 화면·로그인 전용 JS/CSS와 내용 없는 /healthz 상태값뿐. DB·백업·임의 파일 경로는 제공하지 않음. 백업은 인증된 export API로만 다운로드.
- 프록시 인증 헤더를 계정 인증으로 사용하지 않음. 프로덕션 NEWS_ORIGIN은 정확한 HTTPS origin 필수. HTTP는 localhost 개발에만 허용.
- 공고 자동 수집은 계속 미연결. 공식 출처 수동 확인·등록 방식 유지.

## 라즈베리파이 읽기 전용 점검 결과

기존 id_ed25519 SSH 인증으로 BatchMode 접속 성공. 비밀번호·개인키 내용은 열람하지 않았습니다.

- Debian 13.5 trixie, Linux aarch64, Python 3.13.5.
- RAM 총 7819MiB, 가용 약 5968MiB. 루트 디스크 가용 약 207GB.
- Docker 29.7.2, Compose v5.5.0, Tailscale 1.102.2. tailscaled와 docker 서비스 실행 중.
- 기존 컨테이너 pi-hermes-discord-bot-1, my-pm-test-api-1 실행 중. 기존 API는 127.0.0.1:4320.
- TCP 22,111, Tailscale IP의443과 동적 포트, loopback4320 사용 중. UDP111,5353,41641과 동적 포트 사용 중. 4310·8443은 점검 당시 리스닝 없음.
- GitHub Actions runner와 SSH·네트워크·NFS 관련 서비스 등 실행 중. 서비스 설정·환경·원본 파일은 열람하거나 변경하지 않음.
- 기존 Funnel 설정: https://pi-home.tail5eceb8.ts.net 의 / → http://127.0.0.1:4320. 443은 다른 서비스에서 사용 중이므로 덮어쓰면 안 됨.

Funnel이 실제로 설정돼 있어 도메인 구매 없이 ts.net HTTPS 사용이 가능합니다. Serve는 tailnet 내부 전용이고 Funnel은 인터넷 공개입니다. 공식 문서: https://tailscale.com/docs/features/tailscale-funnel . 승인 후 8443 활성화와 유효한 TLS 접속을 확인했습니다. jinho의 일반 CLI는 변경 권한이 없어 승인된 해당 Funnel 명령만 sudo -n으로 실행했습니다. operator나 tailnet 접근 정책은 변경하지 않았습니다.

## 승인 후 적용한 변경과 영향

1. 서버의 신규 /home/jinho/News_idea-web 경로에 웹 실행에 필요한 소스만 복사. 기존 프로젝트·컨테이너 파일은 변경하지 않음.
2. `docker compose -p news-idea -f compose.web.yml`로 신규 이미지·컨테이너와 news-idea_news-data 볼륨 생성. Linux host networking을 사용하되 Waitress는 127.0.0.1:4310만 리스닝. CPU1개, 앱 프로세스 주소 공간512MiB, 로그5MB×3 파일. 도커 이미지·데이터·백업만큼 디스크 사용.
3. 사용자가 SSH 터미널에서 관리자 비밀번호를 숨김 입력으로 설정. 에이전트가 운영 비밀번호를 대신 설정하거나 수집하지 않음.
4. 서버 내부와 SSH 터널에서 테스트 데이터로 검증한 뒤 기존 Tailscale 설정을 별도 파일로 보존. 승인된 경우에만 8443 Funnel 추가:

```sh
sudo -n tailscale funnel --bg --https=8443 http://127.0.0.1:4310
tailscale funnel status
```

이 명령은 **8443의 로그인 화면·로그인 API·상태 엔드포인트를 누구나 인터넷에서 접속 가능하게** 합니다. 인증 성공 후에만 앱·메모·백업 API에 접근할 수 있습니다. 443의 기존 서비스는 유지합니다. 권한 부족이나 정책 변경 안내가 나오면 멈추고 해당 변경 범위를 별도 승인받습니다. `funnel reset` 또는 `serve reset`은 기존 서비스를 지우므로 사용하지 않습니다.

확정 origin은 `https://pi-home.tail5eceb8.ts.net:8443`입니다. 실제 CLI 출력과 HTTPS 요청, 공개 Funnel 릴레이 Chromium에서 확인했습니다. 휴대폰 셀룰러에서 Tailscale을 끈 접속은 별도 시험이 필요합니다.

## 배포·재배포 명령

서버 신규 경로에서 .env를 mode600으로 만들고 NEWS_ORIGIN에 승인된 정확한 HTTPS origin을 기록합니다. .env에는 비밀번호가 필요 없습니다. .env와 var는 Git/Docker 컨텍스트에서 제외됩니다.

```sh
docker compose -p news-idea -f compose.web.yml build
# 사용자가 직접 입력. 비밀번호는 출력되지 않음.
docker compose -p news-idea -f compose.web.yml run --rm web python webapp.py --set-password
docker compose -p news-idea -f compose.web.yml up -d
docker compose -p news-idea -f compose.web.yml ps
```

docker.service와 tailscaled.service 부팅 활성화(enabled)를 읽기 전용으로 확인했습니다. 재부팅 자동 시작은 restart:unless-stopped로 운영합니다. 실제 ARM64 이미지 빌드와 QA 앱 프로세스 종료 후 Docker 자동 재시작·데이터 보존을 검증했습니다. Docker의 수동 stop/kill은 자동 재시작을 억제하므로 중지했다면 up -d로 다시 시작합니다. healthcheck는 저장소 접근도 점검하지만 unhealthy 자체가 재시작을 발생시키지는 않습니다. unhealthy면 디스크·로그를 확인하고 해당 서비스만 재시작하세요. 전체 서버 재부팅 시험은 미수행입니다.

## 백업·이전·복구

서버 시작 시, 이후 24시간마다, 가져오기 직전에 JSON 백업을 추가합니다. 화면에서 즉시 백업과 다운로드도 가능합니다. 자동 백업 실패는 내용 없는 오류 로그에 남깁니다. 백업은 누적되며 자동 삭제하지 않습니다. 디스크 사용량을 점검하고 중요한 백업을 다른 안전한 장치로 내려받으세요. JSON에는 개인 메모가 포함됩니다.

기존 데스크톱 데이터는 사용자가 원본 앱에서 먼저 백업한 뒤 JSON 내보내기를 수행합니다. 로그인 웹앱의 JSON 가져오기에서 이 파일을 명시적으로 선택합니다. 미리보기·원본 자동 탐색은 하지 않으며 기존 ID는 건너뜁니다. 데스크톱 원본과 백업은 삭제하지 않습니다.

기록 복구는 빈 웹 데이터 저장소에 관리자 비밀번호를 설정하고 검증된 v1 JSON을 가져옵니다. 기존 ID의 잘못된 내용을 덮어쓰는 복구는 지원하지 않으므로 새로운 볼륨에서 검증한 후 전환합니다. 전체 장애 복구용으로 인증 DB까지 보존하려면 **뉴스 앱만 중지한 뒤 전체 볼륨 사본**을 안전한 외부 위치에 저장하세요. 인증 DB 사본에는 해시와 활성 세션 정보가 포함되므로 비밀로 취급하고, 복구 후 비밀번호 재설정으로 세션을 모두 무효화합니다.

## 공개 및 배포 되돌리기

설치된 CLI 도움말에 따라 해당 8443 설정만 끕니다:

```sh
sudo -n tailscale funnel --https=8443 off
tailscale funnel status
docker compose -p news-idea -f compose.web.yml stop web
```

443 기존 라우팅이 그대로인지 전·후 비교합니다. 포트 해제 명령은 실제 Funnel 출력에서 안내받았지만 운영 공개를 유지하려고 실행하지 않았습니다. 기존 설정 사본은 서버 tailscale-before.json에 보존했습니다. Compose down을 사용할 때도 `-v`를 사용하지 않아 데이터를 보존합니다. 배포 이미지 ID는 deployment-status.json에 기록했습니다. 이전 이미지를 기록해 두고 앱만 교체하면 코드 롤백이 가능합니다. 서비스 중지·포트 공개 해제와 데이터 삭제는 별개입니다.
