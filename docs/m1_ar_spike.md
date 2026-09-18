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
| 안양 경로 공간 리본 | 현장 위치에서 검증 필요 |
| 20분 연속 세션 | 통과, crash·process death·안전 중단 없음 |
| Recording | 통과, MP4와 telemetry CSV 생성 확인 |
| Playback | 통과, 완료 상태와 live camera 복귀 확인 |

2026-09-17 스모크 테스트에서는 `navi_ar_20260917_234640_046.mp4`와 CSV 65행을 생성했다. Playback 전환 중 발견한 camera texture 재바인딩 오류를 수정한 뒤 전체 재생과 실시간 카메라 복귀까지 통과했다.

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

## 실기기 실행

USB 연결 동안 개발 PC의 로컬 백엔드를 쓰려면 다음 포트 reverse가 필요하다.

```powershell
adb -s R3CWA0J3XRZ reverse tcp:8000 tcp:8000
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

1. 안양 고정 구간에서 GPS 횡오차와 리본 횡방향 오차를 함께 기록한다.
2. compass heading을 화면 회전축에 맞게 보정하고 yaw accuracy를 수집한다.
3. 동일 dataset을 여러 번 재생해 tracking loss와 frame time 분산을 비교한다.
4. CPU profiler로 live AR 렌더링의 지속 부하를 분해하고 release 빌드와 비교한다.
5. Geospatial/VPS는 Google Cloud 프로젝트와 API key가 준비된 뒤 별도 capability gate로 연결한다.

## 참고

- [ARCore를 Android 앱에 optional로 연결](https://developers.google.com/ar/develop/java/enable-arcore)
- [ARCore Depth 개발 가이드](https://developers.google.com/ar/develop/java/depth/developer-guide)
- [ARCore Recording/Playback 개발 가이드](https://developers.google.com/ar/develop/java/recording-and-playback/developer-guide)
- [ARCore 지원 기기 목록](https://developers.google.com/ar/devices)
