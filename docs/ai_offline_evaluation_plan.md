# NaVi M2 오프라인 AI 평가 계획

## 현재 목적

이 평가는 경로를 자동 차단할 모델을 확정하는 절차가 아니다. M1의 ARCore pose/depth 없이
일반 카메라 영상만으로 얻을 수 있는 탐지 성능과 기기 지연시간의 기준선을 만든다.
결과는 `pending`, `verified=false` 후보이며 사람 검수 전에는 공용 Graph를 바꾸지 않는다.

## 구현된 평가 경로

```text
정지 이미지 / 일반 MP4
  → versioned manifest + normalized annotation
  → AndroidMediaFrameDecoder
  → MediaPipe EfficientDet-Lite0 int8 (CPU/IMAGE)
  → optional TemporalDetectionTracker
  → IoU matching
  → JSON/CSV metrics + regression gate
```

- manifest 스키마: `data/ai-evaluation/manifest.schema.json`
- 평가 구현: `android/feature/ai-perception`
- 모델 확보: `scripts/fetch_ai_baseline_model.ps1`
- 기준 런타임: MediaPipe Tasks Vision 1.0.0
- 기준 기기: 현재 연결된 Galaxy SM-S911N. 에뮬레이터 결과는 기능 검증용이고 성능 기준으로 쓰지 않는다.

## 라벨 계층

### 범용 detector 기준선

COCO EfficientDet에서 바로 비교할 수 있는 라벨은 `person`, `bicycle`, `car`,
`motorcycle` 등이다. 이들은 일시적 점유 후보일 뿐 통행 불가 판정이 아니다.

### NaVi 현장 라벨 후보

다음 라벨은 별도 수집·학습 또는 segmentation/기하 계산이 필요하다.

- `construction_barrier`, `fixed_obstacle`, `parked_micromobility`
- `curb_ramp`, `tactile_paving`
- `sidewalk`, `roadway`, `terrain`
- `surface_damage`, `standing_water`

객체가 보인다는 사실만으로 잔여 통행 폭을 알 수 없고, 점자블록의 부재 같은 음성
사실은 범용 detector만으로 확정할 수 없다. 해당 판단은 M3의 depth·pose 융합과 사람
검수가 필요하다.

## 최소 현장 평가 세트

첫 회차는 학습 세트가 아니라 고정 평가 세트로 만든다.

1. 대표 회랑을 서로 다른 방향으로 최소 4회 보행 촬영한다.
2. 맑은 낮, 역광/그늘, 저조도, 젖은 노면 조건을 분리 기록한다.
3. 영상은 1초 간격 후보 frame으로 추출하되 연속 유사 frame을 모두 정답 수에 넣지 않는다.
4. 같은 촬영 세션의 frame은 서로 다른 비교 split에 나누지 않는다.
5. 대상이 작거나 가려졌거나 화면 밖에 잘린 경우 annotation 속성으로 남기고 별도 분석한다.
6. 얼굴과 차량 번호판은 저장 전에 비식별화하고 원본 보존 위치·기간·접근자를 기록한다.

카카오 로드뷰 이미지는 현재 저장소 문서상 수동 판독 참고용이며 저장·학습·재배포
권리가 확인되지 않았다. 따라서 이번 detector 평가 세트로 내려받거나 재사용하지 않는다.

## 측정과 회귀 기준

- 전체 및 클래스별 precision, recall, F1
- 특히 안전 관련 후보의 false negative와 작은 객체 크기별 recall
- 추론 p50/p95/max latency와 실패 frame 수
- 조도·날씨·기기별 성능 차이
- track ID 유지 길이와 ID switch 수(후속 metric)
- 20분 구동 시 온도, 처리 FPS, throttling(후속 계측)

초기 데이터 없이 임의의 production threshold를 고정하지 않는다. 첫 고정 평가 세트의
관측값을 저장한 뒤 `OfflineRegressionPolicy`에 하락 방지 기준을 설정한다.

## M1 의존 경계

다음 항목부터는 M1의 ARCore session 구현이 선행되어야 한다.

- ARCore CPU image를 복사 없이 `PerceptionFrameLease`로 전달
- image timestamp와 camera pose/depth timestamp 정렬
- ARCore Recording/Playback dataset의 영상·IMU·pose 재생
- detector/segmentation 결과의 실제 거리, 잔여 폭, 로컬/지리 좌표 추정
- tracking loss와 device capability에 따른 2D HUD fallback 연동

일반 MP4 기반 detector 실험은 M1 없이 계속할 수 있지만, 공간 장애물 관측을 만드는
순간부터 M1과 M3의 계약이 필요하다.
