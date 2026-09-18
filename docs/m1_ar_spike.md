# M1 AR 기술 스파이크 실행 기록

기준일: 2026-09-17
기준 기기: Samsung SM-S911N, Android 16 (API 36)

## 현재 수직 슬라이스

- `:feature:ar-navigation`이 ARCore 카메라 세션을 단독 소유한다.
- ARCore는 앱의 필수 조건이 아닌 `optional` 기능이다.
- 기기가 지원하면 `DepthMode.AUTOMATIC`을 켜고 실제 depth frame 도착 여부를 관측한다.
- ARCore local pose에 최대 45m의 전방 경로 리본을 고정한다.
- GPS 정확도 15m 초과, 경로 횡오차 20m 초과, heading 부재, tracking 손실이면 기존 2D HUD로 전환한다.
- 화면에서 tracking 상태, depth 활성 여부, frame 처리 시간, tracking loss 횟수를 확인할 수 있다.
- 화면에서 ARCore MP4 녹화를 시작·종료하고 가장 최근 dataset을 반복 재생할 수 있다.
- MP4와 같은 이름의 CSV에 tracking, depth, route alignment, frame time, tracking loss를 약 300ms 간격으로 저장한다.

## 기준 기기 확인 결과

| 항목 | 결과 |
|---|---|
| ADB transport | 정상 |
| Google Play Services for AR | 1.56.262080393 |
| ARCore Java SDK | 1.56.0 |
| ARCore session 생성 | 통과 |
| Automatic Depth capability | 지원 |
| 앱 콜드 스타트 | 통과 |
| AR camera 화면 진입 | 통과 |
| tracking loss 후 회복 | 통과 (`EXCESSIVE_MOTION` → `TRACKING`) |
| 전북대 내부 로컬 25m 경로 | 106 학생군사교육단 남측 구간·backend 계약 통과, SM-S911N 화면·현장 정합 3회 대기 |
| 20분 연속 세션 | 통과, crash·process death·안전 중단 없음 |
| Recording | 통과, MP4와 telemetry CSV 생성 확인 |
| Playback | 통과, 동일 dataset 5회 연속 완료와 live camera 복귀 확인 |

2026-09-17 스모크 테스트에서는 `navi_ar_20260917_234640_046.mp4`와 CSV 65행을 생성했다. Playback 전환 중 발견한 camera texture 재바인딩 오류를 수정한 뒤 전체 재생과 실시간 카메라 복귀까지 통과했다.

### Playback 5회 반복 검증

2026-09-18 SM-S911N을 USB로 연결하고 동일한 `navi_ar_20260917_234640_046.mp4`를 앱 재시작 없이 5회 연속 재생했다.

| 회차 | 결과 | 완료 시 tracking / depth | 누적 loss / 최근 회복 | 로그상 재생 구간 |
|---|---|---|---|---|
| 1 | `PLAYBACK_FINISHED` | `TRACKING` / active | 0 / 없음 | 약 20.8초 |
| 2 | `PLAYBACK_FINISHED` | `TRACKING` / active | 1 / 5,325ms | 약 20.7초 |
| 3 | `PLAYBACK_FINISHED` | `TRACKING` / active | 2 / 5,327ms | 약 20.6초 |
| 4 | `PLAYBACK_FINISHED` | `TRACKING` / active | 4 / 668ms | 약 20.7초 |
| 5 | `PLAYBACK_FINISHED` | `TRACKING` / active | 6 / 679ms | 약 20.7초 |

다섯 회차 모두 동일 앱 프로세스(PID 24402)에서 완료됐고 `AndroidRuntime` fatal error는 없었다. 각 회차 뒤 live camera 전환도 동작했으며, 마지막 전환 뒤 1,503ms 안에 `TRACKING`과 Depth active로 복귀했다. 전체 세션에서 관측한 전환 회복 시간은 668–8,381ms였다. loss 값은 단일 앱 실행 중 live/playback ARCore 세션을 교체하며 누적되는 카운터이므로 녹화본 내부의 서로 다른 손실 횟수를 뜻하지 않는다. 현 위치가 안양 고정 경로 밖이어서 `route_aligned=false`인 것은 예상된 안전 폴백이다.

### 추적 손실 관측성 보강

2026-09-18 기존의 단일 loss 카운터를 실제 추적 손실과 예상된 ARCore session 전환 손실로 분리했다. 구조화 로그와 신규 녹화 CSV에는 failure reason, lifecycle, 화면 interactive 상태, session generation, dataset mode, transition reason과 expected transition 여부를 기록한다. process-scoped diagnostics store가 View와 session 재생성 사이에 카운터와 generation을 유지한다.

보강 후 Playback → live 1회에서 Playback 시작 저하는 expected loss 1회, 669ms 복구로 분류됐고 live 복귀 저하는 expected loss 누적 2회, 1,618ms 복구로 분류됐다. unexpected loss는 0회였고 session generation은 `1 → 2`로 기록됐다.

이어 수행한 원인별 통제 실험 결과는 다음과 같다.

| 자극 | lifecycle / failure reason | 실제/예상 loss | 복구 | 결과 |
|---|---|---|---|---|
| 화면 잠금 → 해제 | `PAUSED → STOPPED → STARTED → RESUMED`; `INSUFFICIENT_FEATURES → EXCESSIVE_MOTION → NONE` | 0 / 누적 3 | 4,938ms | 예상된 session 전환으로 정확히 분리 |
| 카메라 완전 가림 약 8초 | `RESUMED`; `NONE` | 0 / 변화 없음 | 손실 없음 | `TRACKING` 유지 |
| 카메라 가림 + 느린 회전 약 15초 | `RESUMED`; `NONE` | 0 / 변화 없음 | 손실 없음 | `TRACKING`과 Depth active 유지 |
| 급격한 움직임 약 5초 | `RESUMED`; `NONE` | 0 / 변화 없음 | 손실 없음 | `TRACKING`과 Depth active 유지 |

잠금 해제 뒤 별도의 앱 background/foreground 전환도 expected loss 누적 4, unexpected loss 0, 3,470ms 복구로 기록됐다. 전체 실험 동안 앱 프로세스는 유지됐고 fatal exception은 없었다. 카메라 가림과 움직임 자극에서 손실이 발생하지 않은 결과 자체를 그대로 채택하며 실패를 만들기 위한 반복은 하지 않는다.

ARCore 네이티브 로그에서는 Depth motion-stereo의 `spherical_rectifier.cc:161`과 camera/IMU desync 경고가 반복됐다. 앱은 계속 `TRACKING`, Depth active였으므로 즉시 기능 실패로 판정하지 않되 후속 성능 기준선에서 경고 빈도와 사용자 가시 이상을 함께 확인한다.

### 20분 연속 세션 결과

2026-09-17 23:59:41부터 SM-S911N에서 디버그 APK의 live AR 화면을 1,200.2초 연속 실행했다. 시작 시 어두운 장면으로 tracking이 저하됐지만 조명 조건이 회복된 뒤 ARCore tracking과 Depth가 활성화됐다.

| 지표 | 결과 |
|---|---|
| crash / process death | 0 / 0 |
| AR telemetry | 225개 표본 |
| tracking / degraded | 210 / 15 |
| Depth active | 209 / 225 |
| tracking loss / 회복 | 최대 1회 / 866ms |
| frame 처리 시간 | 평균 2.09ms, p95 6.198ms |
| 배터리 | USB 전원에서 100% 유지 |
| 배터리 온도 | 38.7°C 시작, 최대 42.3°C |
| AP / skin 최고 온도 | 52.9°C / 42.0°C |
| Android thermal status | 최대 2 (Moderate) |
| total PSS | 시작 354,329KB, 범위 302,181–446,669KB, 종료 409,866KB |
| 앱 CPU 표본 | 평균 83.71%, 최대 109% |

PSS는 시험 중 감소와 재할당이 반복되어 단조 증가하지 않았다. 다만 디버그 빌드의 지속 CPU 부하는 후속 프로파일링 대상으로 남긴다. 원시 CSV, AR 로그와 요약 JSON은 `android/app/build/reports/ar-soak/20260917_235940/`에 저장했다.

### debug/benchmark 성능 기준선

2026-09-18 같은 SM-S911N과 실내 고정 장면에서 debug와 non-debuggable benchmark를 각각 1분 측정했다. 두 빌드 모두 전 telemetry 표본에서 tracking과 Depth가 활성화됐고 실제 tracking loss, fatal exception, process death는 없었다. benchmark는 debug 대비 CPU 평균이 99.829%에서 70.829%로, frame 평균이 2.819ms에서 1.647ms로, 평균 PSS가 423,581KB에서 354,851KB로 낮아졌다.

benchmark의 스레드별 6표본에서는 ARCore motion-stereo 계열로 추정되는 `ms_late_stage`가 평균 33.92%로 가장 컸고 앱 main thread는 평균 2.47%였다. 따라서 현재 높은 부하는 앱 UI보다 ARCore Depth 쪽일 가능성이 높다. 이는 스레드 이름 기반 추론이며 Depth on/off 인과 비교는 아직 수행하지 않았다. 상세 방법·원시 결과·경고 분석은 [M1 AR 성능 기준선](m1_ar_performance_baseline_20260918.md)에 기록했다.

### 전북대학교 전주캠퍼스 내부 M1-ALIGN 경로 준비

2026-09-18 캠퍼스 전체 보행망 후보를 비교해 106 학생군사교육단 남측 녹지 보행로의 25m를 활성 AR 정합 경로로 확정했다. 기존 안양 데모 Graph와 기존 정문 주변 경로는 사용하지 않는다.

| 항목 | 결과 |
|---|---|
| 원본 | OpenStreetMap 로컬 스냅샷, ODbL |
| 선택 way | `471373639`, `highway=footway` |
| 시험 길이 / 방위 | `25.0m` / `93.09°` |
| 원 보행선 / 양끝 여유 | `75.031m` / 약 `25m`, `25m` |
| 접근성 계약 | `unknown`, `verified=false`, `field_test_only=true` |
| 공용 Graph 변경 | 금지, `shared_graph_mutation_allowed=false` |
| backend 계약 | 2 nodes, 1 edge, pending 후보 0, 두 경로 모두 25.0m |
| SM-S911N UI | 이전 경로 UI 계약 통과, 새 내부 경로 표시는 기기 미연결로 재확인 대기 |
| 실제 AR 정합 | 미검증, 현장 3회 측정 대기 |

원본 GraphML, 정확한 좌표, route GeoJSON과 manifest는 `data/runtime/local-field-tests/jbnu-jeonju-campus-poc/`에만 저장하고 Git에서 제외한다. 데스크톱 선별에서 차량 통행선 약 `22.8m`, 계단·횡단 약 `19.6m`, 건물 약 `11.1m`, 캠퍼스 경계 약 `215.9m` 이격을 확인했지만 현장 안전 증거는 아니다. 선정 근거는 [전북대 내부 PoC 경로 선정 기록](m1_jbnu_route_selection.md), 전체 실행 절차와 기록표는 [전북대 내부 M1 로컬 현장 시험](m1_local_field_route_jbnu.md)에 고정했다.

이 25m Graph는 2 nodes/1 edge라 장애 Edge 차단 뒤 우회가 불가능하다. 안내 중 장애물 확인부터 재탐색·도착까지는 같은 현장의 별도 [E2E-WC 전북대 재탐색 경로](e2e_wc_jbnu_route.md)를 사용한다. E2E Graph는 8 nodes/8 edges이고, backend에서 A `130.7m`가 지정 Edge의 session-local 차단 뒤 B `153.5m`로 바뀌는 계약을 확인했다. 실제 접근성은 아직 `unknown`, `verified=false`다.

## 실기기 실행

USB 연결 동안 개발 PC의 로컬 백엔드를 쓰려면 다음 포트 reverse가 필요하다.

```powershell
adb -s R3CWA0J3XRZ reverse tcp:8000 tcp:8000
```

기기 로컬 `8000` 포트가 점유된 경우 개발 전용 주소와 reverse 포트를 함께 `8001`로 우회한다.

```powershell
adb -s R3CWA0J3XRZ reverse tcp:8001 tcp:8000
```

```properties
NAVI_BACKEND_URL=http\://127.0.0.1\:8001
```

`android/local.properties`의 개발 전용 주소는 다음과 같이 둔다.

```properties
NAVI_BACKEND_URL=http\://127.0.0.1\:8000
```

검증 명령:

```powershell
$env:JAVA_HOME = 'C:\Program Files\Android\Android Studio\jbr'
cd android
.\gradlew.bat testDebugUnitTest assembleDebug assembleDebugAndroidTest
adb -s R3CWA0J3XRZ install -r .\app\build\outputs\apk\debug\app-debug.apk
adb -s R3CWA0J3XRZ install -r .\app\build\outputs\apk\androidTest\debug\app-debug-androidTest.apk
adb -s R3CWA0J3XRZ shell am instrument -w -r `
  -e class kr.co.navi.mobility.ar.ArCoreCapabilityTest `
  kr.co.navi.mobility.test/androidx.test.runner.AndroidJUnitRunner
```

20분 안정성 시험은 AR 화면에 진입한 뒤 저장소 루트에서 다음과 같이 실행한다. thermal status 4 이상 또는 배터리 45°C 이상이면 자동 중단한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\scripts\ar_soak_test.ps1 `
  -DurationMinutes 20 `
  -SampleSeconds 30
```

dataset은 앱 전용 외부 저장소에 있으며 앱에서 업로드하지 않는다.

```text
/sdcard/Android/data/kr.co.navi.mobility/files/ar-datasets/
├── navi_ar_YYYYMMDD_HHMMSS_SSS.mp4
└── navi_ar_YYYYMMDD_HHMMSS_SSS.csv
```

필요하면 다음 명령으로 PC에 복사한다.

```powershell
adb -s R3CWA0J3XRZ pull `
  /sdcard/Android/data/kr.co.navi.mobility/files/ar-datasets `
  .\artifacts\ar-datasets
```

## 다음 체크포인트

1. 현재 위치 forward segment 기반 2D fallback과 `10m / 정확도 15m / 3회 / 최소 2초` 도착 gate는 구현·단위 검증을 완료했다.
2. 활성 frontend에 실제 `CameraHud`, 현재 선분 방향과 도착 상태를 연결했고 실제 작업공간 앱 테스트·debug APK 빌드도 통과했다.
3. 단독 에뮬레이터 완료 세션 `9393bae7-34bb-4058-9022-efcd0b70a735`에서 합성 위치 `A 130.7m → session block → B 153.5m → 저정확도 거부 → 3회·2초 자동 도착`을 검증했다. Graph revision은 `0`, 원본 Edge는 `blocked=false`, 후보는 `pending`, `verified=false`였다.
4. ARCore/Play Store가 없는 환경의 자동 설치 화면 crash를 수정했다. availability를 먼저 확인하고 후면 카메라 또는 ARCore가 없으면 2D 안내로 강등하며, 재시험에서 fatal exception과 CameraX 재시도 로그가 없었다.
5. 다음 활성 작업은 [M1-VIS 병렬 정합 스파이크](ar_ai_parallel_alignment_spike.md)의 정적 거리 frame A/B harness다.
6. 전북대 현장에서는 먼저 25m M1-ALIGN을 같은 조건으로 3회 기록하고, E2E 경로 A·B의 접근성을 사람이 별도 사전 점검한다.
7. A·B가 모두 통과 가능한 경우에만 AI 없이 수동 E2E 폐루프를 1회 수행한다. 실제 통행을 방해하는 장애물은 설치하지 않는다.
8. GPS 횡오차, 현재 segment 방향, 리본 전환, tracking/fallback, 도착 gate와 ARCore Depth native 경고를 함께 기록한다.
9. Geospatial/VPS는 Google Cloud 프로젝트와 API key가 준비된 뒤 별도 capability gate로 연결한다.

## 참고

- [ARCore를 Android 앱에 optional로 연결](https://developers.google.com/ar/develop/java/enable-arcore)
- [ARCore Depth 개발 가이드](https://developers.google.com/ar/develop/java/depth/developer-guide)
- [ARCore Recording/Playback 개발 가이드](https://developers.google.com/ar/develop/java/recording-and-playback/developer-guide)
- [ARCore 지원 기기 목록](https://developers.google.com/ar/devices)
