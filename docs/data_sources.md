# NaVi 공공·공간 데이터 소스 카탈로그

기준일: 2026-09-17

이 문서는 NaVi 대표회랑 평가에 사용할 원본 데이터의 위치, 출처, 사용 경계와 현재 확인 상태를 기록합니다. 원본은 가능한 한 다운로드 당시 파일명과 압축 상태를 유지합니다.

## 비밀정보와 공개 링크

- 경기데이터드림 인증키는 Git에서 제외된 루트 `.env`의 `GYEONGGI_DISABLED_FACILITIES_API_KEY`에만 저장합니다.
- 실제 인증키는 문서, 예제, 로그, Android 리소스에 기록하지 않습니다.
- 커밋 가능한 예시는 `.env.example`에 빈 값으로만 둡니다.
- 경기데이터드림 Open API base URL은 `https://openapi.gg.go.kr`입니다.
- 경기데이터드림 장애인편의시설 데이터셋 페이지는 아래 URL입니다.
  - `https://data.gg.go.kr/portal/data/service/selectServicePage.do?infId=VSSNHR6NY83ZUFTBPS1434786061&infSeq=3`
- 데이터셋별 실제 요청 경로는 제공기관 명세서로 확인하기 전에는 추정하지 않습니다. 현재 상태는 `endpoint_verification_required`입니다.
- 안양시 도로공사안내 공식 목록은 아래 URL입니다. 전달받은 추적 파라미터는 제거했습니다.
  - `https://www.anyang.go.kr/main/selectBbsNttList.do?bbsNo=94&key=1737`
- 도로공사 게시물은 비정형 공고이므로 자동으로 공용 Graph를 차단하지 않습니다. 구조화 결과는 `pending`, `verified=false` 후보로만 만들고 사람 검수를 거칩니다.

## 원본 보관 위치

| 자료 | 원본 경로 | 확인된 형식/좌표계 | 현재 용도 |
|---|---|---|---|
| NGII 수치지형도 2025, 37612037/038/047/048 | `data/raw/ngii/digital_topographic_map/2025/{sheet_id}/` | ZIP 안 SHP 38~51개 레이어, EPSG:5186, XML/XLSX 메타데이터 | 네 도엽이 대표회랑 Graph bbox 전체를 덮음. 보행 객체 inventory와 OSM geometry QA |
| NGII 수치지도 2.0 2022, 376120994/995/996/1405/1406 | `data/raw/ngii/digital_topographic_map/2022/{sheet_id}/` | ZIP 안 SHP 41~47개 레이어, EPSG:5186, XML 메타데이터 | 안양역 인근 1:1,000 세부 표본구간 평가 |
| NGII 수치지형도 2025, 37612049 | `data/raw/ngii/digital_topographic_map/2025/37612049/` | ZIP 안 SHP 40개 레이어, EPSG:5186, XML/XLSX 메타데이터 | 수치지형도 처리기 검증용. 현재 대표회랑과 불일치 |
| NGII 수치지도 2.0 2022, 376121501~376121513 | `data/raw/ngii/digital_topographic_map/2022/{sheet_id}/` | ZIP 안 SHP 21~27개 레이어, EPSG:5186, XML 메타데이터 | 수치지형도 처리기 검증용. 현재 대표회랑과 불일치 |
| NGII 공개 DEM 2025, 37612 | `data/raw/ngii/dem/2025/37612/` | ZIP 안 HFA/IMG, EPSG:5179, float32, 90m, nodata=-9999 | 대표회랑 coverage 및 경사 후보의 해상도 적합성 평가 |
| NGII 정사영상 2025, 37612049 | `data/raw/ngii/orthophoto/2025/37612049/` | RGB TIFF, 9,252×11,508, 메타데이터상 GSD 0.25m | 시각 QA 후보. 현재 대표회랑과 불일치 |
| NGII 정사영상 2025 QA본, 37612037/038/047/048 | `data/raw/ngii/orthophoto_preview/2025/` | 공식 JPEG 미리보기 4장과 HTML 메타데이터, 약 0.51m/pixel | 대표회랑 OSM·횡단보도 geometry의 시각 QA. 25cm 원본 TIF 신청은 최종 제출 확인 대기 |
| NGII 정밀도로지도 2023, 경기안양 시범운행지구 | `data/raw/ngii/precision_road_map/2023/gyeonggi_anyang_pilot/` | 공식 WFS GeoJSON 14개 레이어, EPSG:4326 | 대표회랑 동측의 보도·횡단보도·연석 geometry 후보 평가 |
| NGII 연속수치지도 오선택본 2026-09-17 | `data/raw/ngii/continuous_digital_map/2026/off_corridor_selection_202609174822/` | ZIP, EPSG:5179, 294,310,019 bytes | 대표회랑과 불일치. `hold` 격리, Graph 입력 금지 |
| 안양시 횡단보도 현황 2026-08-26 | `data/raw/anyang/crosswalks/2026/` | UTF-8 CSV, WGS84 위경도 2,728건 | 별도 후속 평가 대상. 기존 40개 표본의 갱신/확장 후보 |

대용량 NGII 다운로드는 `.gitignore`의 `data/raw/ngii/` 규칙으로 로컬 전용 보관합니다. 2025 수치지형도 메타데이터에는 `재배포 금지`가 명시되어 있으므로 원본을 저장소나 배포 패키지에 포함하지 않습니다.

## 현재 확인된 품질 주의사항

### 수치지형도

- 실제 SHP CRS는 모든 확인 도엽에서 EPSG:5186입니다.
- 2022 DBF에는 `.cpg`가 없고 기본 판독 시 한글 필드명이 깨집니다. 읽을 때 `CP949`를 명시해야 합니다.
- 2025 SHP에는 `EUC-KR` CPG가 포함되어 있습니다.
- 2025 XML은 181행 부근의 닫는 태그 오류로 well-formed XML이 아닙니다. 원본은 수정하지 않고, XLSX와 실제 SHP 메타데이터를 함께 대조합니다.
- 2025 메타데이터는 제목에 1:1,000 통합구축, 공간해상도에 1:5,000, 배포포맷에 DXF를 기록하지만 실제 전달물은 SHP입니다. 축척·포맷은 단일 메타 필드만 신뢰하지 않습니다.
- 새로 확보한 2025 네 도엽의 메타데이터 합집합은 대략 `126.9000–126.9500, 37.3749–37.4251`이며 기준 Graph bbox 전체를 포함합니다.
- 새로 확보한 2022 다섯 도엽의 SHP 헤더 합집합은 EPSG:5186 기준 대략 `192473.82–193802.39, 532852.89–533963.83`입니다. 이는 전 회랑 대체본이 아니라 안양역 주변 세부 표본입니다.
- 9개 ZIP 모두 `tar -tf`로 열렸고 SHP/SHX/DBF/PRJ 구성과 SHA-256은 `data/raw/ngii/digital_topographic_map/source_manifest.json`에 기록했습니다.
- 기존 도엽 `37612049`의 공간 범위는 대략 `126.9500–126.9750, 37.3749–37.4001`로 대표회랑과 불일치하므로 계속 처리기 시험용으로만 둡니다.

### DEM

- 실제 래스터는 EPSG:5179, 254×316 픽셀, 90m 격자입니다.
- 범위는 WGS84로 대략 `126.7464–127.0067, 37.2430–37.5007`이며 현재 대표회랑을 포함합니다.
- 기준 Graph Edge 길이 중앙값은 약 58.3m이고 723개 중 549개가 90m보다 짧습니다. 따라서 이 DEM은 보도 단위 Hard Constraint 경사를 바로 생성하기에는 해상도가 거칩니다.

### 정사영상

- TIFF는 RGB uint8이고 메타데이터에는 GSD 0.25m, GRS80/TM 중부원점이라고 기록되어 있습니다.
- TIFF 자체에는 CRS, affine transform, GCP, RPC가 없습니다. 동반 world file도 없습니다.
- 공식 도엽 인덱스 또는 동반 좌표 파일로 georeferencing을 복원하고 기준점으로 검증하기 전에는 픽셀을 지도 좌표로 간주하지 않습니다.
- 도엽 37612049는 현재 대표회랑과 교차하지 않습니다.
- 대표회랑을 덮는 2025 도엽은 `37612037`, `37612038`, `37612047`, `37612048`로 확인했습니다.
- 네 도엽의 공식 미리보기와 메타데이터를 확보했습니다. 미리보기는 약 0.51m/pixel JPEG이므로 0.25m 원본 TIF와 동일한 자료로 취급하지 않습니다.
- 공식 사이트가 제공한 EPSG:5179 extent를 미리보기의 image extent로 사용하되, 기준점 오차를 측정하기 전에는 geometry 자동 수정에 사용하지 않습니다.

### 정밀도로지도

- 2023 `경기안양_시범운행지구` 8.9km의 14개 공식 WFS 레이어를 EPSG:4326 GeoJSON으로 저장했습니다.
- 현재 Graph bbox와 교차하는 주요 객체는 보도 polygon 27개, 횡단보도 polygon 22개, 콘크리트 연석 계열 33개입니다.
- 자료는 자율주행 차량용 도로·도로시설 표현이 중심이며 2023년 제작본입니다. 실제 턱 높이, 유효 보도폭, 현재 장애물 또는 휠체어 통과 가능 여부를 제공하지 않습니다.
- 따라서 벡터 geometry는 `partial_accept` QA 후보이며, 자동으로 `wheelchair_accessible`, `blocked`, `verified=true`를 만들지 않습니다.
- 상세 범위와 레이어별 overlap은 `docs/ngii_download_assessment.md` 및 원본 폴더의 `source_manifest.json`에 기록합니다.

### 횡단보도 CSV

- 2,728건 모두 관리번호와 위경도를 가지며 관리번호 중복은 확인되지 않았습니다.
- 기준 Graph bounding box 안에는 467건이 있습니다.
- `보도턱낮춤여부`와 `점자블록유무`는 각각 2,553건이 비어 있습니다. 빈 값을 `없음`으로 해석하지 않고 `unknown`으로 유지합니다.

## 데이터 승격 원칙

1. 원본 파일은 변경하지 않습니다.
2. 좌표 변환, clipping, 매핑, 계산 결과는 파생 데이터로 분리합니다.
3. 데이터가 Edge 통과 가능 여부, 비용 또는 출발·도착 정밀도 중 하나를 개선하지 않으면 Graph에 넣지 않습니다.
4. 파생 값은 `derived=true`, `verified=false`와 원본 데이터셋 ID·방법·해상도를 보존합니다.
5. AI·게시물 파싱·영상 판독 결과는 후보일 뿐입니다. 공용 Graph 변경은 사람 승인 후에만 가능합니다.
6. 사용자 Route Session의 임시 차단은 공용 Graph 검증 상태와 분리합니다.
