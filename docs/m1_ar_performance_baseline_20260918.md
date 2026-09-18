# M1 AR 성능 기준선 — 2026-09-18

기준 기기: Samsung SM-S911N, Android 16 (API 36)
장면: 실내 고정 장면, live AR, `route_aligned=false` 안전 폴백
목적: debug 수치를 제품 성능으로 오해하지 않도록 동일 기기·장면에서 non-debuggable 빌드와 비교한다.

## 계측 보정

기존 soak 스크립트의 `dumpsys cpuinfo` 값은 짧은 간격에서 같은 누적값을 반복했고, 2026-09-18에 추가된 구조화 `NaViAR` 로그의 새 필드 때문에 telemetry 정규식도 더 이상 일치하지 않았다. 다음과 같이 수정했다.

- CPU 표본을 `top -b -n 1 -p <pid>`의 프로세스 순간값으로 변경했다.
- 현재 구조화 로그의 failure reason, 실제/예상 loss, lifecycle 필드를 파싱한다.
- ARCore native error 로그를 함께 저장하고 주요 경고를 요약한다.
- CPU/PSS/RSS 평균을 summary에 기록한다.
- 짧은 추적 복구와 재저하가 반복될 때 하나의 loss 에피소드로 합치도록 500ms 안정화 디바운스를 추가했다.

`android/app/build/reports/ar-soak/20260918_144152/`는 구 로그 파서 때문에 AR 표본이 0이라 비교에서 제외했다. `20260918_144533/`은 이전 프로세스가 이미 장시간 `DEGRADED` 상태였으므로 성능 비교에서 제외했지만, 플래핑 카운터 과다 증가를 발견하는 근거로 사용했다.

## 비교 빌드

- debug: 일반 개발 APK, debuggable.
- benchmark: release 설정을 상속하고 non-debuggable로 실행하되 로컬 설치만 가능하도록 debug signing key를 사용한다.
- production `release` 설정과 서명 정책은 변경하지 않았다.
- 두 빌드 모두 같은 application id와 앱 데이터, 같은 장면을 사용했다.

## 1분 비교 결과

| 지표 | debug | benchmark | 변화 |
|---|---:|---:|---:|
| 완료 시간 | 60.1초 | 60.5초 | 동등 |
| tracking 표본 | 11/11 | 12/12 | 모두 정상 |
| Depth active 표본 | 11/11 | 12/12 | 모두 정상 |
| unexpected / total loss | 0 / 0 | 0 / 0 | 손실 없음 |
| CPU 평균 (`top` 순간 표본) | 99.829% | 70.829% | 29.0% 상대 감소 |
| CPU 최대 | 111.0% | 81.4% | 29.6% 상대 감소 |
| frame 처리 평균 | 2.819ms | 1.647ms | 41.6% 상대 감소 |
| frame 처리 p95 | 6.249ms | 3.179ms | 49.1% 상대 감소 |
| 평균 PSS | 423,581KB | 354,851KB | 16.2% 상대 감소 |
| 평균 RSS | 499,492KB | 450,689KB | 9.8% 상대 감소 |
| 최고 battery 온도 | 35.6°C | 35.9°C | 짧은 순차 시험이라 비교 판정 안 함 |
| 최고 thermal status | 0 | 0 | 정상 |
| fatal / process death | 0 / 0 | 0 / 0 | 정상 |

근거:

- debug: `android/app/build/reports/ar-soak/20260918_144949/`
- benchmark: `android/app/build/reports/ar-soak/20260918_145255/`

이 수치는 1분 단일 실행의 개발 기준선이다. 통계적 성능 보증이나 장시간 발열 결과로 사용하지 않는다.

## 스레드 부하 표본

benchmark에서 `top -H`를 5초 간격으로 6회 수집해 같은 이름의 스레드를 합산했다.

| 스레드 그룹 | 평균 CPU | 최대 CPU | 해석 |
|---|---:|---:|---|
| `ms_late_stage` | 33.92% | 40.7% | ARCore motion-stereo/Depth 주 부하로 추정 |
| `Thread-19` | 4.32% | 14.8% | 이름만으로 소유자 확정 불가 |
| `DefaultDispatch` | 3.70% | 7.4% | 앱 coroutine 작업군 |
| `MTC_feature_ext` | 3.08% | 7.4% | ARCore feature extraction으로 추정 |
| `StandardEventLo` | 3.08% | 7.4% | ARCore 이벤트 처리로 추정 |
| `ms_depth` | 3.08% | 11.1% | ARCore Depth 작업으로 추정 |
| 앱 main (`o.navi.mobility`) | 2.47% | 3.7% | 앱 UI/main thread |
| `MTC_vio` | 2.47% | 7.4% | ARCore visual-inertial odometry로 추정 |

스레드 이름에 근거한 해석은 추론이며 심볼 기반 profiler 결과가 아니다. 다만 앱 main thread보다 ARCore motion-stereo 관련 스레드가 훨씬 큰 비중을 차지하므로, 후속 최적화는 앱 렌더링 미세 조정보다 Depth 사용 정책과 ARCore 버전/기기 동작 확인을 우선한다.

## ARCore native 로그

| 오류/경고 | debug | benchmark |
|---|---:|---:|
| `spherical_rectifier.cc:161` | 334 | 0 |
| `FEATURE_DSP_CAM_IMU_DESYNC` | 30 | 29 |
| `VIO_PREDICT_TO_SENSOR_TIMESTAMP_FAIL` | 9 | 0 |

두 빌드 모두 tracking, Depth, 앱 동작은 정상이고 fatal error는 없었다. 따라서 현재는 사용자 가시 기능 실패가 아닌 기기/ARCore native 진단 위험으로 분류한다. debug와 benchmark의 로그 수준 또는 내부 실행 차이도 배제할 수 없으므로, 경고 횟수만으로 benchmark가 문제를 해결했다고 판정하지 않는다.

## 결론과 다음 작업

- 제품 성능 판단에는 debug의 약 100% CPU가 아니라 non-debuggable benchmark의 약 71% CPU를 기준선으로 사용한다.
- Depth를 포함한 ARCore가 주 부하라는 정황이 강하므로 장시간 재시험보다 실제 보행 경로에서 기능 가치와 발열을 함께 판단한다.
- 다음 작업은 사용자 생활권의 공개된 시작 지점을 기준으로 임시 OSM 보행망과 20~30m AR 정합 경로를 준비하는 것이다.
- 로컬 경로의 접근성 속성은 모두 `unknown`, `verified=false`이며 공용 Graph에 반영하지 않는다.
