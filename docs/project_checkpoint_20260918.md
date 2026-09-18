# NaVi 프로젝트 중간 체크포인트

기준일: 2026-09-18

기준 브랜치: `master`
체크포인트 직전 커밋: `0491327` (`프론트 구조 변경`)

이 문서는 M1 AR, M2 AI, 공간자료 평가와 Graph 반영 후보 분석을 함께 진행한 시점의 저장 상태를 정리한다.

## 한눈에 보는 현재 상태

| 영역 | 상태 | 핵심 결과 | 다음 Gate |
|---|---|---|---|
| M0 모듈화 | 완료 | AR·AI·fusion·공통 계약을 독립 Gradle 모듈로 분리 | live 계약 변경 시 호환성 유지 |
| M1 AR | 기술 스파이크 완료 | ARCore session, pose/depth, route ribbon, fallback, Recording/Playback, telemetry | live CPU image lease와 pose/depth timestamp 정렬 |
| M2 AI | device-free 범위 완료 | MP4 replay, EfficientDet-Lite0, tracker, 회귀 보고서, 에뮬레이터 자동 실행 | 실제 현장 라벨 세트와 모델 비교 |
| 공간자료 평가 | 자동평가 완료·검수 대기 | 원본/CRS/coverage 검증, 414개 review queue 생성 | Human Review 승인 |
| Graph enrichment | 후보 bundle 완료 | 235개 후보/192개 Edge, route 영향 후보 5개 | 승인 전 기준 Graph 반영 금지 |
| 서비스 Graph | 유지 | 504 Node, 723 Edge, 평가 전후 SHA-256 동일 | 검증된 observation만 별도 승격 |

## M1 AR 기술 스파이크

- `:feature:ar-navigation`이 ARCore session lifecycle을 소유한다.
- Tracking quality, 자동 Depth, route ribbon 정렬과 2D HUD fallback을 구현했다.
- ARCore Recording/Playback과 telemetry CSV 기록 경로를 구현했다.
- Galaxy SM-S911N 기준으로 Tracking·Depth·route ribbon·fallback·Recording/Playback을 확인했다.
- 20분 연속 세션에서 crash와 camera deadlock 없이 종료했고 최대 thermal status는 2(Moderate)였다.

아직 남은 경계는 ARCore CPU image를 복사 수명 계약이 있는 `PerceptionFrameLease`로 넘기고, 동일 timestamp의 pose/depth와 AI 결과를 결합하는 것이다. 상세 내용은 [M1 실행 기록](m1_ar_spike.md)을 기준으로 한다.

## M2 AI device-free harness

- M1 MP4와 telemetry CSV를 versioned manifest로 변환한다.
- 입력 SHA-256, 실제 MP4 duration, telemetry 형식, 최근접 sample offset과 추정 동기화 오차를 검증한다.
- MediaPipe Tasks Vision 1.0.0과 EfficientDet-Lite0 int8 CPU/IMAGE baseline을 사용한다.
- detector 단독 또는 deterministic temporal IoU tracker를 선택할 수 있다.
- 전체/label/context/객체 크기별 precision·recall·F1, latency, 실패 frame, track ID switch를 기록한다.
- JSON, 집계 CSV, frame CSV, 반복 실행 결정성/model diff 결과를 생성한다.
- 실패 frame만 별도 manifest로 재실행한다.
- segmentation은 unsigned 8-bit mask 계약과 IoU·Dice·pixel recall evaluator/golden fixture까지 준비했다.
- 물리 단말 serial은 실행 스크립트가 거부하며 실제 모델 실행은 Android 에뮬레이터에서 수행한다.

주 진입점은 `scripts/run_m2_device_free.ps1`이며 상세 계약은 [M2 실행 문서](m2_device_free_harness.md)에 있다. 에뮬레이터 latency는 기능 회귀용이며 production 성능 기준이 아니다.

## 공간자료와 Graph 후보

자동평가는 기준 Graph를 변경하지 않았다.

- 공통 검증: 184 checks 중 pass 176, warning 7, hold 1, fail 0
- 기준 Graph: 504 Node, 723 Edge, SHA-256 `b6c746a47c80d516bc506473335e0177eade52d82b8b635d1cb0f8ce2d9cac78`
- 평가 전후 Graph SHA-256 동일
- 수치지형도 회랑 객체 1,351개: unique 390, ambiguous 450, unmatched 511
- DEM: Graph coverage 100%, 해상도 90m이므로 Edge hard constraint에는 사용 금지
- 정사영상: 약 25cm/pixel이나 독립 기준점 RMSE가 없어 geometry 자동 수정 보류
- 공공 횡단보도 context 후보 402개, HD map 20m 이내 대응 12개
- Human Review queue 414개, 전부 `pending`, `verified=false`, `graph_update_allowed=false`

Graph enrichment bundle은 235개 후보를 192개 Edge에 연결했다. 이 중 5개는 `stairs=true`를 제안하는 route 영향 후보이고 나머지 230개는 geometry/evidence 전용이다. 5개 제안을 적용한 별도 시뮬레이션 사본에서는 후보 Edge별 우회 증가 또는 접근 가능 경로 없음이 발생하므로 현장 확인 전 적용하지 않는다.

재배포 제한이 있는 NGII 원자료와 그 geometry 파생 산출물은 로컬 전용이다. `data/processed/evaluation/`은 Git에서 제외하고, 저장소에는 재현 스크립트와 집계 보고서만 보관한다.

## 안전 및 데이터 승격 원칙

1. 원본 공간자료와 기준 Graph는 자동평가가 수정하지 않는다.
2. AI·공간매핑 결과는 후보일 뿐이며 기본값은 `pending`, `verified=false`다.
3. AI confidence는 접근 가능 확률이나 검증 완료를 뜻하지 않는다.
4. 세션 임시 차단은 공용 Graph 상태와 분리한다.
5. Human Review에서 승인된 observation만 provenance와 함께 Graph 갱신 절차로 전달한다.
6. 카카오 로드뷰 등 저장·학습·재배포 권리가 확인되지 않은 이미지는 평가 데이터로 커밋하지 않는다.
7. 모델 파일, 촬영 원본, M2 실행 결과와 제한 자료의 파생 geometry는 Git에서 제외한다.

## 체크포인트 검증 기준

커밋 직전 다음 명령을 다시 실행한다.

```powershell
.\.venv\Scripts\python.exe -m pytest -q

cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat :app:testDebugUnitTest :feature:ai-perception:testDebugUnitTest
.\gradlew.bat :app:assembleDebug :app:assembleDebugAndroidTest
.\gradlew.bat :feature:ai-perception:lintDebug
```

실기기 M1 결과와 device-free M2 E2E 결과는 각각 [M1 실행 기록](m1_ar_spike.md), [M2 실행 문서](m2_device_free_harness.md)에 기록한다.

이번 체크포인트 직전 재검증 결과는 다음과 같다.

- Python: 46 tests passed
- Android/JVM unit: 30 tests passed, failure 0
- Android app debug APK와 androidTest APK assemble 성공
- AI perception Android lint 성공

## 다음 우선순위

1. 414개 공간 review queue와 route 영향 후보 5개를 사람이 검수한다.
2. 실제 촬영 MP4를 비식별화하고 최소 현장 annotation 세트를 만든다.
3. detector/segmenter 후보를 동일 manifest에서 비교해 초기 회귀 기준을 고정한다.
4. ARCore camera image·pose·depth를 동일 frame 계약으로 연결해 M3 spatial fusion을 시작한다.
5. 실제 단말에서 end-to-end latency, 발열, battery, false reroute와 missed hazard를 측정한다.
