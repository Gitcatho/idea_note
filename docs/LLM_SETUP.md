# LLM 운영 설정과 복구

2026-10-19 사용자 승인으로 News_idea에 배포했습니다. 이후 추가 운영 변경은 별도 승인 범위를 따릅니다. 기존 서비스와 443/8443 Funnel 설정은 변경할 필요가 없습니다.

## 선택 모델

`OPENAI_MODEL=gpt-5.6-terra`. 공식 지원: https://developers.openai.com/api/docs/models/gpt-5.6-terra (Responses, Structured Outputs). 실제 키의 모델 권한은 별도 확인이 필요합니다. 키를 채팅·Git·명령 인수·로그에 입력하지 마세요.

## 서버에서 직접 키 입력

배포 담당자가 데이터·인증 DB를 먼저 일관된 SQLite 백업으로 보존한 후 진행합니다. 키는 사용자 본인이 터미널에서 아래 명령을 실행해 숨김 입력합니다. 명령 자체에는 실제 키가 포함되지 않습니다. 기존 키 파일이 있다면 덮어쓰지 않고 중단합니다.

```sh
docker exec -it news-idea-web-1 python -c 'import getpass,os; from pathlib import Path; p=Path("/data/.secrets"); p.mkdir(mode=0o700,exist_ok=True); key=getpass.getpass("OpenAI API key: "); assert 20<=len(key)<=512 and not any(c.isspace() for c in key), "Invalid key format"; fd=os.open(p/"openai_api_key",os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600); f=os.fdopen(fd,"w"); f.write(key); f.close()'
```

`compose.llm.yml`은 선택한 모델과 `/data/.secrets/openai_api_key` 파일 경로만 전달합니다. 키는 인증된 데이터 API·JSON 백업에 포함되지 않습니다. 서버 볼륨 전체 복사에는 비밀 파일도 포함될 수 있으므로 운영자 전용으로 보호하세요. 디스크 파일은 암호화되지 않습니다.

승인된 배포 시 기존 프로젝트/Compose 파일을 유지하고 선택 override만 추가합니다.

```sh
OPENAI_MODEL=gpt-5.6-terra docker compose -p news-idea -f compose.web.yml -f compose.llm.yml up -d --build --no-deps web
```

실제 API 요청은 사용자 동의 후 합성 본문으로 점검합니다. 최초 테스트도 과금될 수 있습니다. API 키 없음·모델 오류는 화면에 설정 오류로 표시하고 비밀값과 제공자 응답 본문은 로그에 출력하지 않습니다. 요청 한도는 인증 DB에 보존합니다.

## 정책 변화와 복구

이 버전은 기존 일반 회원도 승인 대기로 전환합니다. admin은 모든 탭을 유지합니다. 일반 회원의 기록과 기존 세션 행은 보존하고, 승인 및 탭 허가 후 다시 접근할 수 있습니다. 관리자가 승인 취소하면 기존 쿠키로도 API 접근을 차단합니다.

배포 전 현재 이미지·소스·인증 DB·회원별 데이터 DB를 백업하고 기존 회원 상태를 기록합니다. 장애 시 News_idea만 이전 이미지/Compose로 복원합니다. 인증 마이그레이션 이전으로 완전히 돌아갈 때에는 배포 전 인증 DB 복사본을 사용하며, 배포 후 생성된 계정·세션·권한을 잃을 수 있으므로 먼저 현재 DB도 보존해야 합니다. 다른 서비스·Funnel·기존 데스크톱 앱은 복구 대상이 아닙니다.


2026-10-19 배포용 숨김 입력 도우미를 서버에 준비했습니다. 사용자 본인이 Mac 터미널에서 실행합니다. 기존 키 파일이 있으면 덮어쓰지 않고 중단합니다. 키는 실행 인수나 채팅에 넣지 않습니다.

```sh
ssh -t jinho@100.84.155.62 'python3 /home/jinho/News_idea-web/approval-llm-rollout-20261019/set-openai-key.py'
```

이 도우미는 컨테이너 내부에서 getpass로 직접 입력받으며 호스트 Python은 키 값을 읽지 않습니다. 키 파일은 영속 볼륨에 보존되고 요청마다 설정을 읽으므로 키 입력 후 재시작할 필요가 없습니다. 운영 Compose 명령에는 `-f compose.web.yml -f compose.llm.yml`를 함께 사용해야 LLM 설정이 유지됩니다.

실제 운영 결과: 사용자가 키 직접 설정 완료,600 권한 확인. gpt-5.6-terra 합성 본문 실제 요약·근거·편집기 전달 성공. 키 설정 도우미를 다시 실행할 필요가 없습니다. 공개 메타설명 자동 발췌와 실제 셀룰러 접속은 별도 미검증입니다.
