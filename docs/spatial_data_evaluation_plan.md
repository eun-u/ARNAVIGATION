# NaVi 대표회랑 공간데이터 평가 계획

기준일: 2026-09-17

## 1. 목적과 비목적

목적은 새 데이터를 많이 적재하는 것이 아니라, 현재 OSM 기반 Accessibility Graph의 `unknown` 중 어떤 값을 신뢰성 있게 줄일 수 있는지 판단하는 것입니다.

우선 답할 질문은 다음 세 가지입니다.

1. 수치지형도가 OSM보다 실제로 유용한 보행 객체 또는 속성을 추가하는가?
2. DEM으로 대표회랑 Edge에 사용할 만한 경사 후보를 어느 정도 생성할 수 있는가?
3. 정사영상으로 OSM·횡단보도 geometry의 오류나 불일치를 확인할 수 있는가?

이번 평가는 OSM 전면 대체, 안양 전역 Graph 재구축, 영상 AI 학습 또는 공공데이터만으로 `wheelchair_accessible=true/false`를 확정하는 작업이 아닙니다.

## 2. 현재 기준선

기준 Graph는 `data/processed/anyang_accessibility_graph.geojson`입니다.

- 생성 진입점: `scripts/build_graph.py`
- 원본: `data/raw/anyang_corridor_walk_20260915.graphml`
- 구조: NetworkX `MultiGraph`, 504 nodes / 723 edges
- 좌표계: EPSG:4326
- 범위: `126.9171049–126.9371927, 37.3864649–37.4081503`
- 공간 형상 출처: OSM 723개 Edge
- 접근성 출처: `osm_tags` 721개, `synthetic` 2개
- 기존 횡단보도 매핑: EPSG:5179에서 최근접 Edge까지 최대 15m
- 현재 `slope`, `width`는 OSM `incline`, `width` 태그를 숫자로 파싱하고, `curb_height`는 기본 `null`

새 데이터 평가 중에는 이 파일과 `scripts/build_graph.py`를 수정하지 않습니다. 각 평가 결과는 `edge_id`를 키로 한 sidecar 후보로 만들고, 채택 결정을 통과한 Feature만 후속 enrichment 단계에서 병합합니다. SQLite 상태 overlay와 Route Session 차단 흐름도 변경하지 않습니다.

## 3. 공통 평가 파이프라인

```text
immutable raw source
  → inventory / checksum / license check
  → CRS and encoding normalization
  → representative-corridor clip
  → spatial mapping to current edge_id
  → candidate feature sidecar
  → quantitative metrics + manual sample review
  → accept / partial accept / reject
  → accepted fields only: optional graph enrichment
```

### 3.1 원본과 파생물 경계

- `data/raw/`: 다운로드 원본. 압축을 풀어 덮어쓰지 않습니다.
- 향후 `data/processed/evaluation/`: clip, 매핑, 지표, 후보 Feature.
- 평가 보고서에는 원본 경로, SHA-256, 제작일, CRS, 변환 CRS, 처리 파라미터를 기록합니다.
- 파생 결과는 최소한 `source_dataset_id`, `source`, `derived`, `verified`, `method`, `created_at`을 가집니다.
- 평가 단계의 모든 후보는 `verified=false`입니다.

### 3.2 CRS와 회랑 마스크

- 원본 CRS를 먼저 읽고 누락 시 메타데이터와 실제 좌표 범위를 교차 검증합니다.
- 거리·buffer·면적 연산은 현재 매핑과 같은 EPSG:5179에서 수행합니다.
- API/Graph 교환용 결과 geometry는 마지막에 EPSG:4326으로 변환합니다.
- 기본 회랑 마스크는 Graph Edge union의 30m buffer입니다.
- 교차로·건물·영상 문맥 QA에는 별도로 100m context buffer를 사용합니다.
- 좌표변환 round-trip 오차는 표본점 기준 0.2m 이하인지 확인합니다. 이는 법적 정확도 기준이 아니라 처리 오류 탐지용 프로젝트 기준입니다.

### 3.3 공통 채택 상태

- `accept`: 정의된 범위에서 Graph Feature 후보로 승격 가능
- `partial_accept`: 특정 도엽·Edge·용도에만 사용하며 quality flag 필수
- `reject`: 현재 대표회랑 또는 Routing Feature에 사용하지 않음
- `hold`: 필수 sidecar, 정확한 도엽 또는 검증 표본 부족으로 결론 유보

어떤 상태에서도 데이터 하나만으로 `verified=true` 또는 최종 휠체어 통과 가능 판정을 만들지 않습니다.

## 4. 수치지형도 평가

### 4.1 입력과 현재 상태

- 입력: ZIP 내부 SHP/SHX/DBF/PRJ, 동반 XML, 2025 도엽의 XLSX 메타데이터
- 실제 CRS: EPSG:5186
- 인코딩: 2022 도엽은 CP949 명시 필요, 2025 도엽은 EUC-KR CPG 포함
- 대표회랑 2025 1:5,000 도엽: `37612037`, `37612038`, `37612047`, `37612048`
- 안양역 인근 2022 1:1,000 표본 도엽: `376120994`, `376120995`, `376120996`, `376121405`, `376121406`
- 2025 네 도엽 메타데이터 합집합: 약 `126.9000–126.9500, 37.3749–37.4251`
- 기준 Graph bbox `126.9171–126.9372, 37.3865–37.4082` 전체가 2025 네 도엽 안에 포함됨

따라서 Q1의 대표회랑 평가는 이제 시작할 수 있습니다. 2025 1:5,000 네 도엽은 전 회랑 inventory/geometry QA의 기본 입력으로 사용하고, 2022 1:1,000 다섯 도엽은 안양역 인근에서 해상도 차이와 추가 보행 객체의 실익을 비교하는 표본으로 사용합니다. 기존 off-corridor 도엽은 reader 회귀 시험 외에는 제외합니다.

### 4.2 전처리와 clipping

1. ZIP을 읽기 전 파일 세트 완전성(SHP/SHX/DBF/PRJ)을 검사합니다.
2. 공식 지형지물 속성목록으로 레이어 코드를 이름과 의미에 매핑합니다. 코드 의미를 geometry/필드명만 보고 추정하지 않습니다.
3. CP949/EUC-KR을 명시하고 한글 필드와 값의 깨짐 여부를 검사합니다.
4. geometry validity, empty geometry, duplicate UFID, Z/M 존재 여부를 기록합니다.
5. EPSG:5186에서 EPSG:5179로 변환한 뒤 30m 회랑과 100m context로 각각 clip합니다.
6. 원본과 clip 결과의 Feature 수·길이·면적 보존 관계를 검증합니다.

### 4.3 OSM/Graph 매핑

레이어 의미가 공식 카탈로그로 확인된 뒤 geometry 유형별로 처리합니다.

- 선형 객체: 후보 Edge를 공간 인덱스로 찾고, 15m 이내 거리, 방향 차이, buffer overlap, 선 길이 비율을 함께 사용합니다.
- 면 객체: Edge 5m buffer와의 교차 비율을 계산하되 면 중심선을 자동으로 새 Routing Edge로 만들지 않습니다.
- 점 객체: 의미에 맞는 Node/Edge 유형에만 최근접 매핑합니다. 일반 최근접만으로 계단·엘리베이터·출입구를 확정하지 않습니다.
- 하나의 객체가 여러 Edge와 유사하거나 고가/지하 등 수직 분리가 의심되면 `ambiguous`로 남깁니다.
- OSM에 없는 보행 후보 geometry는 별도 `new_object_candidate.geojson`으로 내보내고 사람 검토 전에는 Graph에 추가하지 않습니다.

### 4.4 생성 가능한 후보 Feature

공식 레이어 의미와 단위가 확인된 경우에만 다음을 후보로 만듭니다.

- 보행공간 geometry 보완 후보
- 보도 또는 통행공간의 폭 후보
- 포장·재질 기반 surface 후보
- 계단, 육교/지하도, 경사로, 출입구, 구조물 후보
- 건물·도로·경계 geometry QA 근거
- OSM에 없는 객체 또는 OSM과 불일치하는 객체 목록

차도 폭을 보도 유효폭으로, 구조물 높이를 턱 높이로, 일반 도로 재질을 보행면 재질로 전용하지 않습니다.

### 4.5 품질지표

- source coverage: 회랑 Edge 수와 총길이 중 도엽 범위에 포함되는 비율
- semantic coverage: 공식적으로 의미가 확인된 보행 관련 레이어 비율
- attribute completeness: 후보 필드별 null/unknown 비율
- unique match rate / ambiguous match rate / unmatched rate
- 매칭된 선의 median·p95 perpendicular distance
- 방향 차이와 5m buffer overlap 비율
- OSM 대비 추가 후보 객체 수와 수동 표본 정답률
- geometry validity, duplicate UFID, 도엽 경계 중복률
- 제작연도와 OSM snapshot 간 시간 차이

### 4.6 채택/기각 기준

- 회랑 coverage가 90% 이상이면 전체 회랑 평가, 10~90%면 해당 범위만 `partial_accept`, 10% 미만이면 대표회랑 데이터로 `reject`합니다.
- 자동 매핑은 unique match 80% 이상, p95 거리 10m 이하, 수동 표본 30건의 올바른 Edge 연결률 90% 이상일 때만 후보 생성에 사용합니다.
- 속성은 공식 의미·단위가 확인되고 null 비율이 20% 이하이며 수동 표본 일치율이 90% 이상일 때만 enrichment 후보가 됩니다.
- 새 Routing geometry는 자동 채택하지 않습니다. 연결성, 횡단 가능성, 수직 레벨을 사람 검토한 뒤 별도 승인합니다.
- 2025 네 도엽은 bbox 기준 전 회랑 coverage를 확보했지만, 실제 Feature coverage와 의미 적합성은 clipping 후 산출합니다. 2022 다섯 도엽은 표본구간에만 `partial_accept`입니다.

위 수치는 법적 정확도 기준이 아니라 PoC의 초기 품질 게이트이며, 첫 표본 검토 후 보고서에 근거를 남기고 조정할 수 있습니다.

### 4.7 정밀도로지도 보조 소스

2023 `경기안양_시범운행지구` 8.9km의 공식 WFS 14개 레이어를 확보했습니다. 현재 Graph bbox와 교차하는 보도 polygon 27개, 횡단보도 polygon 22개, 링크 145개 등은 수치지형도 확보 전에도 geometry QA 후보로 사용할 수 있습니다.

다만 정밀도로지도는 차량·자율주행 도로시설 중심 자료이며 실제 턱 높이, 유효 보도폭, 현재 장애물 또는 휠체어 통과 가능 여부를 제공하지 않습니다. 따라서 OSM 대체 Graph로 사용하지 않고 `source=NGII_HDMAP`, `verified=false`의 매핑 후보만 생성합니다. 벡터는 `partial_accept`, 점군은 보도면 분리와 현장 오차검증 계획이 생길 때까지 `hold`로 둡니다. 상세 판단은 `docs/ngii_download_assessment.md`를 따릅니다.

## 5. DEM 평가

### 5.1 입력과 현재 상태

- 입력: ZIP 내부 `37612.img`
- 형식: Erdas Imagine/HFA, float32
- CRS: EPSG:5179
- 크기/해상도: 254×316, 90m
- nodata: -9999
- WGS84 범위: `126.7464–127.0067, 37.2430–37.5007`
- 기준 Graph coverage: bbox 기준 100%

DEM은 회랑을 덮지만 723개 Edge 중 549개가 한 픽셀 크기인 90m보다 짧습니다. 따라서 바로 기존 `slope` 필드를 채우거나 `steep_slope` Hard Constraint를 발동하지 않습니다.

### 5.2 전처리와 sampling

1. raster CRS, affine, nodata, dtype, resolution, bounds를 검사합니다.
2. 100m context buffer로 window clip하되 resampling 없이 원 해상도를 보존합니다.
3. Edge geometry를 EPSG:5179로 변환하고 시작·끝점과 45m 간격 이하의 중간점을 생성합니다.
4. nearest와 bilinear sampling을 모두 계산해 민감도를 비교합니다.
5. nodata 또는 raster 밖 표본이 하나라도 있으면 해당 Edge quality를 낮춥니다.
6. 시작/끝 고도차 기반 signed slope와 절대값, 중간 구간 최대 경사 후보를 별도로 계산합니다.
7. 동일 셀에서 시작·끝이 샘플된 Edge는 `insufficient_resolution`로 표시합니다.

### 5.3 생성 가능한 후보 Feature

평가 sidecar에는 다음을 기록합니다.

```text
edge_id
elevation_start_m
elevation_end_m
slope_pct_signed_candidate
slope_pct_abs_candidate
max_segment_slope_pct_candidate
sample_count
distinct_cell_count
dem_resolution_m
quality_flag
source_dataset_id
derived=true
verified=false
```

채택 전에는 기존 `slope`를 덮어쓰지 않습니다. 채택되더라도 `slope_provenance`에 데이터셋, 해상도, 보간법, 계산시각, 검증 상태를 함께 보존합니다.

### 5.4 품질지표

- valid raster coverage: Edge 수·길이 기준 유효 표본 비율
- nodata 비율
- Edge당 distinct cell 수와 동일 셀 시작/끝 비율
- DEM 해상도 대비 Edge 길이 비율
- nearest와 bilinear 결과 차이
- slope 분포, 극단값, 인접 Edge 불연속
- 올바른 도엽의 등고선/표고점 또는 독립 현장 표본과의 고도 RMSE/MAE
- 현장 경사 표본과의 slope MAE 및 8% 실험 임계값 분류 혼동행렬
- DEM Feature 적용 전후 경로 변경 Edge 수와 경로 단절 수

### 5.5 채택/기각 기준

- raster 유효 coverage는 회랑 Edge 총길이의 95% 이상이어야 합니다.
- Edge Hard Constraint용 값은 최소 3개 독립 셀을 통과하고, 독립 표본 대비 경사 MAE 2 percentage points 이하이며, 임계값 초과 분류 precision/recall이 각각 0.90 이상인 Edge에만 허용합니다.
- 조건을 만족하지 못하지만 광역 지형 경향이 안정적이면 `coarse_terrain_context`로만 `partial_accept`합니다.
- current route를 바꾸는 Hard Constraint에는 low-resolution 또는 unverified DEM 값을 사용하지 않습니다.
- 현재 90m DEM은 대표회랑 coverage 자료로는 `accept`, Edge 단위 Hard Constraint 경사원으로는 현 단계 `reject`, 광역 경사 경고 후보로는 `partial_accept`입니다.

## 6. 정사영상 평가

### 6.1 입력과 현재 상태

- 기존 입력: RGB TIFF와 XML 메타데이터, 도엽 `37612049`, 비산동
- 기존 TIFF 크기: 9,252×11,508, uint8, 3 bands
- 기존 메타데이터 GSD: 0.25m
- 기존 TIFF 내장 CRS/affine/GCP/RPC: 없음
- 기존 도엽과 기준 Graph 교차: 없음
- 추가 입력: 2025 공식 JPEG 미리보기와 HTML 메타데이터 4세트
- 추가 도엽: `37612037`, `37612038`, `37612047`, `37612048`
- 추가 미리보기 크기: 약 4,535×5,641, 약 0.51m/pixel
- 공식 검색 결과 extent: EPSG:5179, 현재 Graph 전역을 네 도엽이 덮음

따라서 Q3의 예비 시각 QA는 진행할 수 있습니다. 다만 미리보기는 0.25m 원본 TIF가 아니며, 공식 extent를 사용하더라도 기준점 RMSE를 확인하기 전에는 geometry 수정 또는 정량 Feature에 사용하지 않습니다.

### 6.2 georeferencing과 clipping

1. 공식 도엽 인덱스, world file 또는 제공기관 sidecar를 우선 확보합니다.
2. 예상 CRS는 메타데이터와 공식 자료로 EPSG code까지 확정합니다.
3. 도로 모서리·교차로·건물 모서리 등 안정된 기준점 최소 20개로 위치를 검증합니다.
4. RMSE, 최대오차와 공간적 편향을 기록합니다.
5. 검증된 affine을 별도 sidecar로 보존하고 원 TIFF를 수정하지 않습니다.
6. 정확한 대표회랑 도엽을 확보한 뒤 100m context로 clip합니다.
7. 평가용 산출물은 원본 배포 제한을 확인한 뒤 로컬 전용으로 유지합니다.

### 6.3 OSM/Graph 비교 방법

- OSM Edge, 안양시 횡단보도 점, 수치지형도 geometry를 서로 다른 색으로 overlay합니다.
- Graph Edge에서 영상상 보행공간 중심까지 수직 offset을 표본화합니다.
- 횡단보도 점과 영상상 횡단 표시 중심의 거리, 도로섬/교통섬 누락, 교차로 형상 불일치를 검토합니다.
- 그림자, 차량, 수목, 촬영각으로 판단이 어려운 구간은 `not_interpretable`로 둡니다.
- 영상에서 보이는 객체는 `visual_evidence_candidate`일 뿐 계단·턱·실시간 장애물 Feature로 자동 승격하지 않습니다.

### 6.4 생성 가능한 결과

- OSM geometry offset 후보
- 횡단보도 위치 수정 후보
- 도로섬/교차로 구조 불일치 후보
- 보행공간 존재/부재 검토 후보
- 사람이 확인할 수 있는 이미지 chip과 원 영상 좌표 참조

정사영상만으로 턱 높이, 실제 유효폭, 경사, 현재 공사 상태 또는 휠체어 통과 가능 여부를 정량 Feature로 만들지 않습니다.

### 6.5 품질지표

- georeferencing RMSE / 최대오차 / 체계적 편향
- 회랑 coverage와 해석 가능 구간 비율
- Graph Edge offset median·p95
- 횡단보도 점 offset median·p95
- 불일치 후보 수, 후보 유형과 심각도
- 수동 표본 30건의 판독자 간 일치율
- 촬영일 대비 OSM·공공데이터 기준일 차이

### 6.6 채택/기각 기준

- 공식 또는 검증 가능한 georeferencing이 없으면 지도 QA에 `reject`합니다.
- 기준점 RMSE 1.5m 이하, 최대오차 3m 이하, 회랑 coverage 90% 이상, 해석 가능 구간 85% 이상일 때 visual QA source로 `accept`합니다.
- geometry 수정 후보는 두 명 검토 또는 독립 공공 geometry와의 합치가 있어야 승인 대상으로 보냅니다.
- 영상 판독만으로 Routing Hard Constraint를 만들지 않습니다.
- 현재 네 미리보기는 회랑 시각 QA 후보로 `partial_accept`입니다. 기준점 RMSE 검증과 25cm 원본 TIF 확보 전에는 geometry 자동 수정에 사용하지 않습니다.

## 7. Graph 통합 전 최종 게이트

데이터별 평가가 끝난 뒤에도 다음 조건을 모두 확인합니다.

1. 기존 `edge_id`와 geometry를 불필요하게 바꾸지 않는다.
2. 원본 `source=osm`을 유지하고 속성별 파생 provenance를 별도로 기록한다.
3. unknown을 결측치 또는 낮은 품질 추정으로 억지로 채우지 않는다.
4. 파생 데이터만으로 `verified=true`, `verified_pass`, `verified_block`을 만들지 않는다.
5. 변경 전후 Graph build가 deterministic하고 기존 데모 reroute 회귀 테스트를 통과한다.
6. 새 Feature가 실제로 Edge 통과 가능 여부, cost 또는 목적지 정밀도 중 하나를 개선한다.
7. 경로 변화가 발생하면 변경 Edge, 원인, 출처, 품질등급을 보고서에 남긴다.

## 8. 평가 구현 시 예상 산출물

코드 구현 승인이 아니라 다음 단계의 작업 경계를 정의한 목록입니다.

```text
scripts/validate_spatial_sources.py
scripts/evaluate_topographic_map.py
scripts/evaluate_dem.py
scripts/evaluate_orthophoto.py

data/processed/evaluation/corridor_mask.geojson
data/processed/evaluation/topographic_map/matches.geojson
data/processed/evaluation/topographic_map/new_object_candidates.geojson
data/processed/evaluation/dem/edge_slope_candidates.csv
data/processed/evaluation/orthophoto/geometry_review_candidates.geojson
data/processed/evaluation/metrics.json

docs/spatial_data_evaluation_report.md
```

`build_graph.py` 변경은 위 보고서에서 채택된 Feature가 생긴 뒤 별도 단계로 진행합니다.

## 9. 실행 순서와 예상 소요

1. 현재 원본용 validator와 공통 회랑 마스크: 2~3시간
2. DEM 평가기와 지표: 3~4시간
3. 수치지형도 layer inventory/matcher: 4~6시간
4. 정사영상 georeferencing/overlay 평가기: 4~6시간
5. 수동 표본 QA와 채택 보고서: 4~8시간

총 예상은 약 2~3 개발일입니다. 대표회랑 수치지형도는 확보되어 Q1 평가를 시작할 수 있고, DEM 메타·해상도 평가와 정사영상 미리보기 기반 예비 Q3 평가도 가능합니다. 정사영상의 정량 geometry QA 확정에는 25cm 원본 TIF와 georeferencing 검증이 추가로 필요합니다.
