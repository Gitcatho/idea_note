# News_idea 자동 백업·부팅 운영 점검

2026-10-13 23:13 KST 읽기 전용 점검. 실제 재부팅·컨테이너 재시작·앱/정책 설정 변경 없음. 운영4개 기록과 로그인 세션1개의 전체 결과가 점검 전후 동일하며 기존 서비스와443/8443 Funnel 설정도 동일합니다. 세션 실제 값은 출력/파일에 저장하지 않았습니다.

## 확인 결과

| 항목 | 실제 확인 |
|---|---|
| News_idea | news-idea-web-1 running, healthy |
| 부팅 서비스 | docker·tailscaled 모두 enabled·active |
| 재시작 정책 | unless-stopped |
| 영속 저장소 | news-idea_news-data → /data, 기록DB·인증DB·백업 보존 |
| 공개 연결 | 8443 → 127.0.0.1:4310, 기존443 → 127.0.0.1:4320 유지 |
| 백업 | 유효한v1 JSON6개, 손상0개, 합계11,817bytes |
| 최신 백업 | 2026-10-13 23:09:50 KST,4개 기록 |
| 디스크 | 루트·/data 동일 디스크, 약206GB 가용,9% 사용 |
| inode | 약1,489만개 가용,4% 사용 |
| 로그 | json-file, 파일당5MB·최대3개, 최근500줄 정기백업 실패0건 |

증거: server-operations-status.json. 전체 서버 재부팅 후 실제 시작은 시험하지 않았습니다. 설정과 실행 상태 점검이며 이전 앱 프로세스 재시작 시험은 별도 QA 기록에 있습니다.

## 자동 백업의 정확한 동작

서버 시작 시 즉시 JSON 백업을 생성합니다. 그 뒤 데몬 스레드가86400초 기다려 백업하고 다시 기다립니다. 매일 자정 같은 고정 시각 작업이 아닙니다. 현재 프로세스 시작은10월13일23:04 KST이며 다음 정기 백업은10월14일23:04 KST경입니다. 시작 처리·백업 실행 시간만큼 차이가 있으며 중간 재시작하면 타이머가 다시 시작됩니다. 현재24시간 경과 전이므로 이번 정기 백업 발생 자체는 미검증입니다. 실행 코드의 스레드 시작과 프로세스6개 스레드를 확인했지만 스레드 수만으로 백업 스레드 정상 동작을 입증하지는 않습니다.

정기 백업 실패는 `Scheduled backup failed; check disk space and permissions.` 로그로 남고 서버는 계속 실행합니다. 실패 후 즉시 재시도하지 않으며 다음 시도는 약24시간 후입니다. 시작 시 백업이 실패하면 앱이 시작하지 못하고 Docker 재시작 정책이 적용됩니다. 성공 로그·백업 전용 상태 API·실패 알림·백업 파일 자동 정리는 없습니다. `healthy`는DB 접근을 검사하므로 오래된/실패한 백업을 의미하지 않습니다. 백업에는 기록만 포함되며 관리자 비밀번호 해시와 세션은 포함되지 않습니다.

## 확인 명령

Mac에서 `rtk ssh jinho@100.84.155.62`로 접속한 후 서버에서 아래 명령을 실행합니다. 서버에RTK를 설치하는 작업은 필요하지 않습니다.

```sh
systemctl is-enabled docker tailscaled
systemctl is-active docker tailscaled
docker inspect news-idea-web-1 --format 'state={{.State.Status}} health={{.State.Health.Status}} started={{.State.StartedAt}} restart={{.HostConfig.RestartPolicy.Name}}'
docker logs --since 48h --timestamps --tail 500 news-idea-web-1
docker exec news-idea-web-1 sh -c 'ls -lt /data/backups | head -n 8'
docker exec news-idea-web-1 df -h /data
docker exec news-idea-web-1 df -i /data
docker exec news-idea-web-1 du -sh /data/backups
df -h /
df -i /
```

Docker의 StartedAt과 로그 시각은 UTC로 표시될 수 있습니다. KST는 UTC에 9시간을 더한 값이며, 백업 파일명은 KST 기준입니다.

최신 파일이 올바른JSON인지 내용 출력 없이 검사하려면:

```sh
docker exec news-idea-web-1 python -c "from pathlib import Path; import json; f=max(Path('/data/backups').glob('backup-*.json'),key=lambda p:p.stat().st_mtime); d=json.loads(f.read_text()); assert d['format']=='news-idea' and d['version']==1 and isinstance(d['records'],list); print(f.name,'records=',len(d['records']),'JSON OK')"
```

파일이 없거나 잘렸으면 이 명령이 실패합니다. 파일 이름/생성 시각만으로 성공으로 판단하지 말고 유효한JSON과 필요시 별도 저장소 복구를 확인하세요. 이 검사는 JSON구조 확인이며 전체 입력 검증·복구 시험을 대체하지 않습니다. 이전 복구 시험은 QA.md에 기록했습니다.

운영DB·백업 접근 권한 점검은 쓰기 없이 수행합니다:

```sh
docker exec news-idea-web-1 id
docker exec news-idea-web-1 stat -c '%a %u:%g %n' /data /data/backups /data/news-idea.sqlite3
docker inspect news-idea-web-1 --format '{{json .Mounts}}'
```

이미지는UID10001 사용자로 실행하고 /data는쓰기 가능한 볼륨이어야 합니다. /app 루트파일시스템이읽기전용인 것은 정상입니다. 임의 chmod777이나 볼륨 교체는 하지 않습니다.

## 백업 실패·디스크 부족 대응 순서

1. 최신 **유효한** 백업 시각,프로세스 시작 시각,실패 로그를 함께 확인합니다. 연속 가동 중 최신 유효 백업이26시간 이상 오래되면 점검 기준으로 취급하세요. 이는 권장 수동 점검 기준이며 자동 알림이 설정된 것은 아닙니다.
2. `df -h`로바이트 공간,`df -i`로파일수 한도를 확인합니다. 디스크 사용90% 이상 또는 가용1GB 미만이면 조기 점검을 권장합니다. 이 값도 시스템에 등록된 경고 임계값은 아닙니다. 여유가 있으면 UID·권한·볼륨쓰기상태와 최근로그를 확인합니다. 현재의백업 오류 메시지는 원인을 구분하지 않아 로그만으로 디스크/권한 문제를 단정할 수 없습니다.
3. 부족하면 먼저 검증된 백업을 Mac·별도 디스크로 복사하고 해시·복구 여부를 확인합니다. 프로젝트var/ 경로는 Git 제외이며 개인내용을Git이나 공개폴더에 올리지 않습니다. 원본DB·auth.sqlite3·세션·볼륨을 삭제하지 않습니다. 오래된 백업 정리는 복사·검증 후 정확한 파일을 선택해 별도 승인 범위에서 진행합니다. `docker system prune`이나 볼륨일괄삭제로 기존서비스에 영향을 주지 않습니다.
4. 공간/권한 문제를 해결한 뒤 로그인 웹앱의 '백업·도움말 → 지금 백업'으로 재시도합니다. 성공 메시지,서버의 유효JSON 생성,필요시 임시저장소 복구까지 확인합니다. 이번 점검에서는 백업 생성·재시도를 실행하지 않았습니다.
5. 서버가 중지됐다면 원인 해결 후 News_idea만 시작합니다. 디스크가 가득 찬 상태에서 계속 재시작하는 것만으로는 해결되지 않습니다. 기존443 서비스나Docker/Tailscale 전체를 재시작할 필요는 없습니다.

## 부팅 후 점검과 수동 중지 주의

docker와tailscaled가enabled이므로 부팅 시 데몬 시작이 설정돼 있습니다. 현재 실행 중인 News_idea는unless-stopped로 복귀하고 Tailscale의기존백그라운드8443 설정도 보존돼 있습니다. 그러나 직접 `docker stop`한 컨테이너는 재부팅해도 자동 시작하지 않을 수 있습니다. 수동 중지했다면 승인된 운영 복구 때 아래처럼 해당프로젝트만 올립니다:

```sh
cd /home/jinho/News_idea-web
docker compose -p news-idea -f compose.web.yml up -d
docker compose -p news-idea -f compose.web.yml ps
tailscale serve status
```

이후 로그인 화면·인증된 기록4개·최신백업을 확인하고 기존443 라우팅을 비교합니다. healthcheck의unhealthy는 자동재시작 트리거가 아니므로 실패원인을 따로 조사합니다. 본 점검에서는 위복구명령이나실제재부팅을 실행하지 않았습니다.
