# 현대건설 DART → GitHub Pages 재무 대시보드

금융감독원 **OpenDART 공식 API**에서 현대건설(종목코드 000720)의 2022~2025년 **연간 연결 재무제표**를 수집하고, 교수님이 제공한 「재무제표 및 재무비율 실무 가이드」의 일부 지표를 계산하여 GitHub Pages 정적 대시보드에 게시하는 교양 실습용 프로젝트입니다.

**중요:** 이 저장소의 최초 파일에는 **실제 DART 재무수치가 들어 있지 않습니다.** GitHub Actions 실행 후 수집된 원자료와 계산 결과가 채워집니다. GitHub Pages는 **화면을 공개하는 곳**이고, 금융감독원 API는 **서버 측 GitHub Actions에서만 호출**합니다. 인증키를 GitHub Pages의 HTML/JS나 공개 URL에 넣지 마세요.

## 1. 파일 구성

```text
.github/workflows/dart-dashboard.yml    # 버튼 클릭으로 API 수집·GitHub Pages 배포
scripts/fetch_dart.py                    # DART 호출, 주요 수치 추출·재무비율 계산
site/index.html                         # 웹 대시보드 (GitHub Pages)
site/data/financials.json               # 처음엔 수집 전 안내, 실행 후 실제 수치
report/analysis.md                      # 실행 후 생성되는 공시 근거·재무비율 보고서
data/raw/dart_2022.json ...             # 실행 후 생성되는 API 원본 응답
```

## 2. GitHub에 업로드

1. 이 ZIP을 **압축 해제**합니다. ZIP 자체를 올리는 대신 압축을 푼 폴더 안의 내용을 저장소 최상위에 올립니다. 특히 `.github/workflows/dart-dashboard.yml` 파일이 누락되지 않았는지 확인하세요.
2. 내 저장소: https://github.com/kwontk2006-ai/--DART → `Add file` → `Upload files` → 파일을 추가 → `Commit changes`.
3. `README.md`, `site/index.html`, `scripts/fetch_dart.py`, `.github/workflows/dart-dashboard.yml`이 저장소에 보여야 합니다.

## 3. 인증키를 GitHub Secret으로 등록

저장소 `Settings` → `Secrets and variables` → `Actions` → `New repository secret`에서:

- **Name:** `DART_API_KEY`
- **Secret:** 본인이 발급받은 40자리 키 (여기에만 입력)

이 키를 ChatGPT 대화, README, 공개 저장소 파일, GitHub Pages 웹페이지에 붙여넣지 마세요.

## 4. GitHub Pages와 Actions 실행

1. 저장소 `Settings` → `Pages` → `Build and deployment` → **Source = GitHub Actions** 로 설정.
2. `Actions` 탭 → `Collect DART data and publish dashboard` → `Run workflow` → 실행.
3. 작업이 모두 녹색으로 끝나면 `Settings → Pages`의 배포 주소를 열어 데이터가 표시되는지 확인.
4. 공개 페이지 예상 주소: `https://kwontk2006-ai.github.io/--DART/` (실제 배포 완료 후 이용 가능).

만약 데이터 커밋 단계에서 403 오류가 발생하면 `Settings → Actions → General → Workflow permissions`의 쓰기 권한을 확인하세요. Pages 배포만 완료되어도 원자료·보고서 커밋이 실패한 경우 작업 전체가 실패하므로 로그로 확인해야 합니다.

## 5. 기준·출처 및 제한

- API: https://opendart.fss.or.kr/api/fnlttSinglAcntAll.json
- 고유번호 확인: https://opendart.fss.or.kr/api/corpCode.xml (키 필요)
- 입력: 사업연도 2022~2025, `reprt_code=11011`(사업보고서), `fs_div=CFS`(연결)
- 금액: 원(KRW), 화면에서는 보기 쉽게 조 원으로만 변환.
- 2022년 ROA·ROE와 매출증가율은 **2021년 자료를 미수집해 공란**입니다.
- 원자료가 미존재하거나 계정코드가 중복될 경우 **0으로 대체하지 않으며** 결과는 공란과 주의사항으로 표시합니다.
- 공사수주·계약자산·매출채권·CAPEX·금융비용·시장주가 등은 추가 API 또는 사업보고서 주석 분석이 필요하여 현재 자동 계산 결과에 포함하지 않습니다. FCF, ROIC, PER, PBR도 임의 산출하지 않습니다.
- 데이터는 실행 시점에 수집된 DART의 API 응답 기준이며, 이후 정정공시가 있으면 다시 수집하여 검증해야 합니다.

공식 가이드: https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020
