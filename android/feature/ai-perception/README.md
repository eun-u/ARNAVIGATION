# AI perception offline harness

실행 가능한 전체 절차와 M1 경계는 [M2 device-free harness](../../../docs/m2_device_free_harness.md)에 정리되어 있다.

M2의 현재 기준선은 정지 이미지와 일반 MP4를 재생해 MediaPipe 객체 탐지 모델을
비교하는 결정론적 Android 평가 파이프라인이다. ARCore pose/depth에는 의존하지 않는다.

`OfflineReplayHarness`는 한 번에 하나의 `PerceptionFrameLease`만 열어
`PerceptionEngine`에 전달한다. 따라서 입력 크기와 관계없이 in-flight frame 수는 1로
제한된다. 각 프레임은 성공·실패 여부와 무관하게 닫힌다.

현재 산출 지표:

- 라벨과 IoU 임계값을 이용한 TP, FP, FN
- 전체 및 클래스별 precision, recall, F1
- 엔진이 보고한 inference latency의 mean, p50, p95, max
- 실패 프레임과 원인, 실행 중 관찰된 모델 버전
- JSON 상세 리포트와 CSV 지표
- 전체/클래스별 회귀 임계값 판정

## 데이터 manifest

스키마는 `data/ai-evaluation/manifest.schema.json`에 있다. 경로는 manifest 디렉터리
기준 상대 경로만 허용한다. 좌표는 회전을 적용한 화면 기준 `[0, 1]` 정규화 좌표다.

```json
{
  "schema_version": 1,
  "dataset_id": "anyang-daylight-v1",
  "frames": [
    {
      "case_id": "still-001",
      "image_path": "frames/001.jpg",
      "timestamp_nanos": 0,
      "rotation_degrees": 0,
      "annotations": [
        {"label":"person","left":0.1,"top":0.2,"right":0.4,"bottom":0.9}
      ]
    },
    {
      "case_id": "video-001-1500ms",
      "video_path": "walk.mp4",
      "video_position_ms": 1500,
      "timestamp_nanos": 1500000000,
      "annotations": []
    }
  ]
}
```

`AndroidMediaFrameDecoder`가 이미지 또는 지정 시점의 MP4 프레임을 frame lease로
변환한다. `OfflineEvaluationRunner`는 manifest 로딩부터 평가, 회귀 판정, JSON/CSV
파일 생성까지 수행한다.

`TemporalDetectionTracker`는 같은 라벨의 bounding box를 IoU로 연결하는 결정론적
baseline이다. 실제 모델이 track ID를 제공하지 않을 때 `TrackingPerceptionEngine`으로
감싸 사용한다.

## 기준 모델

첫 모델은 COCO로 학습된 EfficientDet-Lite0 int8이며 MediaPipe Tasks Vision 1.0.0의
CPU/IMAGE 모드로 실행한다. 이 모델은 사람·자전거·차량 같은 일반 클래스의 기준선일
뿐, 보도 단차·잔여 통행 폭·공사 가림막을 최종 판정하지 않는다.

모델 파일은 저장소에 넣지 않는다. 공식 Google 저장소에서 내려받고 길이와 MD5를
확인한다.

```powershell
.\scripts\fetch_ai_baseline_model.ps1
```

## 남은 작업과 M1 경계

1. 평가용 현장 데이터와 개인정보 비식별화·보존 규칙 확정
2. 안양 회랑 최소 라벨 세트를 만들어 모델별 실제 precision/recall 비교
3. 보도/노면 segmentation baseline과 mask 지표 추가
4. M1 이후 ARCore CPU image, pose, depth, Recording/Playback 어댑터 연결

테스트 실행:

```powershell
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat :feature:ai-perception:testDebugUnitTest
.\gradlew.bat :feature:ai-perception:connectedDebugAndroidTest
```
