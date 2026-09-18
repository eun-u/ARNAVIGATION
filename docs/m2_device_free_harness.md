# M2 device-free AI harness

M2의 오프라인 객체 탐지 실험은 실제 Android 단말 없이 실행할 수 있다. 입력은 M1이 기록한
일반 MP4와 AR telemetry CSV이며, 모델 실행에는 Android 에뮬레이터만 사용한다. 에뮬레이터의
지연시간은 기능 회귀 확인용이고 실제 단말 성능 기준으로 사용하지 않는다.

## 한 번에 실행

```powershell
.\scripts\run_m2_device_free.ps1 `
  -VideoPath C:\captures\walk-01.mp4 `
  -TelemetryPath C:\captures\walk-01.csv `
  -DatasetId anyang-walk-01 `
  -PrivacyStatus redacted
```

스크립트는 다음 작업을 순서대로 수행한다.

1. 입력을 로컬 전용 `artifacts/m2-device-free/` 아래에 복사하고 SHA-256을 기록한다.
2. telemetry 시작 행을 영상 0ms로 두고 일정 간격의 프레임을 최근접 telemetry 행에 연결한다.
3. EfficientDet-Lite0 int8 모델을 검증하고 AI 모듈의 계측 APK를 빌드한다.
4. 실행 중인 Android 에뮬레이터를 선택한다. 없으면 첫 AVD를 headless가 아닌 숨김 창으로 시작한다.
5. MP4 프레임을 순차 디코딩하여 detector와 선택적 IoU tracker를 실행한다.
6. JSON, 집계 CSV, 프레임 CSV를 로컬로 가져온다.
7. 실패한 프레임이 있으면 해당 case만 담은 manifest로 한 번 더 실행한다.
8. 성공한 실행은 같은 입력을 다시 실행해 latency를 제외한 예측 결정성을 비교한다.

`-EmulatorSerial`에는 `emulator-*`만 허용한다. 물리 단말 serial은 의도적으로 거부한다.
`-AvdName`으로 자동 시작할 AVD를 지정할 수 있고, 빠른 단일 실행이 필요할 때만
`-SkipDeterminismCheck`를 사용한다. detector 단독 결과가 필요하면 `-DisableTracker`를 지정한다.

## 입력 계약

Telemetry 헤더는 아래와 정확히 일치해야 한다.

```text
elapsed_realtime_ms,tracking_quality,depth_active,route_aligned,tracking_loss_count,last_recovery_ms,frame_time_ms,message
```

시간은 엄격히 증가해야 하며 boolean은 `true` 또는 `false`여야 한다. 현재 M1 기록에는 MP4의
정확한 recording-relative 시작 timestamp가 없으므로 첫 telemetry 행을 영상 0ms로 간주한다.
manifest의 `estimated_sync_error_ms`는 관측한 최대 telemetry 간격과 실제 최근접 행 offset 중 큰
값이다. 기본 M1 샘플 간격에서는 보수적으로 약 300ms이다.

객체 정답은 선택적 annotation JSON으로 추가한다. JSON root는 생성되는 `case_id`를 key로 사용한다.

```json
{
  "anyang-walk-01-000000": {
    "annotations": [
      {
        "label": "person",
        "instance_id": "person-01",
        "left": 0.10,
        "top": 0.20,
        "right": 0.40,
        "bottom": 0.90
      }
    ],
    "segmentation": {
      "mask_path": "masks/000000.png",
      "labels": {"1": "sidewalk", "2": "roadway", "3": "terrain"}
    }
  }
}
```

좌표는 회전 적용 후 화면 기준 `[0, 1]`이다. 동일 물체의 `instance_id`를 연속 프레임에 유지해야
track ID switch를 계산할 수 있다. Segmentation mask는 한 픽셀당 unsigned 8-bit class ID 계약을
사용하며 현재 M2에는 mask 평가기(IoU, Dice, pixel recall)와 golden fixture까지 포함되어 있다.
실제 segmentation 모델 adapter는 다음 모델 선택 단계에서 연결한다.

## 결과와 비교

각 실행에는 다음 파일이 생긴다.

- `<dataset>-report.json`: provenance, 프레임 예측, 전체/label/context/크기별 지표, tracking 지표
- `<dataset>-metrics.csv`: 전체, label, tracking/depth/route/session, 객체 크기별 집계
- `<dataset>-frames.csv`: case별 상태, latency, 예측 수, telemetry context
- `determinism.json`: 두 실행의 예측 비교. latency는 의도적으로 제외

다른 모델 결과를 비교할 때도 같은 도구를 사용한다. `--allow-differences`를 주면 차이를 보고서로
남기되 종료 코드를 실패로 만들지 않는다.

```powershell
.\.venv\Scripts\python.exe scripts\offline_report_tools.py compare `
  --baseline artifacts\baseline-report.json `
  --candidate artifacts\candidate-report.json `
  --output artifacts\model-diff.json `
  --allow-differences
```

지표에는 precision/recall/F1, label별 결과, small/medium/large 객체 recall, AR tracking quality,
depth 활성 여부, route 정렬 여부, session별 결과, latency, 실패 frame, annotated instance의 track ID
switch가 포함된다.

## 개인정보와 안전 경계

- `privacy_status`는 `unreviewed`, `redacted`, `approved` 중 하나로 provenance에 남는다.
- 촬영 동의나 내부 승인 번호가 있으면 `-ConsentReference`로 함께 기록한다.
- 원본, 실행 결과, 모델 파일은 Git ignore 대상이다.
- 외부 이미지 공급자의 약관이 저장·학습·재배포를 허용하지 않으면 평가 데이터로 사용하지 않는다.
- AI 결과는 공용 경로 graph를 직접 수정하지 않는다. 현장 후보는 기존 human review 흐름을 거친다.

## 검증 명령

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests\test_build_ar_offline_manifest.py backend\tests\test_offline_report_tools.py

cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat :feature:ai-perception:testDebugUnitTest
.\gradlew.bat :feature:ai-perception:assembleDebugAndroidTest
```

## M1 이후에만 가능한 범위

이 패키지는 기록된 MP4와 telemetry를 이용하는 오프라인 평가를 완결한다. 다음 항목은 M1의 live
frame/pose/depth 계약이 추가되어야 진행할 수 있다.

- ARCore camera image를 복사 없이 `PerceptionFrameLease`로 전달
- 동일 timestamp의 camera pose/depth와 detector 결과 결합
- 실제 거리, 통행 가능 폭, 로컬/지리 좌표 추정
- live tracking loss 시 2D HUD fallback과 처리량/발열 성능 기준 확정

따라서 새 촬영 데이터 수집과 live AR+AI 통합은 M1 경계지만, manifest 생성, 일반 MP4 detector,
회귀 비교, annotation/segmentation 계약, 리포팅은 물리 단말 없이 계속 수행할 수 있다.
