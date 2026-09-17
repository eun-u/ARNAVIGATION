# NaVi 1차 실증 절차

## 재현

1. 서버를 새 SQLite DB로 시작합니다.
2. Android 앱을 실행합니다.
3. 기본 출발지 `CW04`, 목적지 `CW20`, 휠체어 조건을 확인하고 `접근 가능한 길 찾기`를 누릅니다.
4. 일반 경로 1,081.9m와 접근 가능 경로 1,302.5m 및 추천 근거 화면을 확인합니다.
5. `카메라 안내 보기`를 누르고 CameraX 미리보기 위 프리즘 HUD를 확인합니다.
6. `앞 구간 통과 불가`에서 사유를 고르고 현재 세션의 실험 Edge를 임시 차단합니다.
7. 재탐색 완료 상태와 새 접근 경로 1,736.3m를 확인합니다.
8. 수동 후보가 `pending`, `verified=false`로 저장되고 공용 Edge의 `blocked=false`가 유지되는지 확인합니다.
9. 관리자 `/review`에서 후보를 확인하되 실제 검수 없이 승인하지 않습니다.

거리 기대값은 현재 동결 OSM 스냅샷의 값이며 새 OSM을 수집·빌드하면 달라질 수 있습니다. 새 빌드의 기대값은 GeoJSON `metadata.demo.expected`를 기준으로 검증합니다.

## 후보 검수

1. `/review`에서 pending 후보 5건을 확인합니다.
2. 외부 로드뷰 링크와 AI note를 참고하되 AI 문구를 사실로 복사하지 않습니다.
3. 검수자, 실제 관찰 시각, 판정, 근거를 입력합니다.
4. 근거가 부족하면 `needs_more_evidence`, 오류면 `rejected`를 선택합니다.
5. `approved`만 verified observation으로 취급합니다.
6. 공사 차단 승인 시 Edge history와 graph revision 증가를 확인합니다.

실제 검수자를 가장한 샘플 승인은 저장소에 포함하지 않습니다. 초기 5건은 모두 `pending`, `verified=false`입니다.

## 자동 검증

```powershell
.\.venv\Scripts\python.exe -m pytest
cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:assembleDebugAndroidTest
```

자동 테스트는 일반 경로, 계단/차단 제외, no-route, OSM 3단계 거리, 세션 분리·만료, 승인 경계, 재시작 영속성, Android API 계약과 방향 계산을 다룹니다. 실제 카메라와 지도 렌더링은 에뮬레이터 또는 실기기에서 별도로 확인합니다.
