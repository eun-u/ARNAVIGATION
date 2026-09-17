# NaVi Android 현장 검증 절차

## 검증 범위 구분

현재 기본 경로 Graph는 안양역–안양1동 실증 구역이다. 다른 지역에서 앱을 켜도 카메라, 나침반 HUD, 제보, 세션 재탐색 UI는 확인할 수 있지만 해당 지역의 실제 길을 계산하는 것은 아니다. 앱은 Graph 범위 밖 현재 위치를 출발지로 적용하지 않고 이 한계를 알린다.

따라서 검증을 두 부분으로 나눈다.

- 기능 검증: 에뮬레이터 또는 사용자의 생활권에서 카메라/센서/제보 흐름 확인
- 공간 검증: 현재 안양 synthetic 시나리오 또는 향후 별도로 구축한 사용자 생활권 Graph로 경로 차이 확인

로드뷰는 현장 후보를 미리 확인하는 참고 자료로만 사용한다. 로드뷰 이미지에서 추정한 턱·경사·통행 가능 여부를 검증 완료 데이터로 등록하지 않는다.

## 사전 준비

1. 백엔드를 실행한다.
2. Android 앱의 서버 주소를 확인한다.
3. 에뮬레이터는 `10.0.2.2:8000`, 실기기는 개발 PC의 LAN 주소를 사용한다.
4. 실기기와 개발 PC를 같은 네트워크에 연결한다.
5. 실제 이동 테스트 전에는 보호자 동행과 안전한 정지 지점을 정한다. 이동 중 조작하지 않는다.

## 자동 검증

```powershell
.\.venv\Scripts\python.exe -m pytest

cd android
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat :app:testDebugUnitTest :app:assembleDebug :app:assembleDebugAndroidTest
```

## 시나리오 A — 일반/접근 가능 경로 비교

1. 앱을 열고 휠체어 프로필을 선택한다.
2. 기본 출발지 A와 목적지 B로 `접근 가능한 길 찾기`를 누른다.
3. 일반 최단경로 `1,081.9m`와 접근 가능 경로 `1,302.5m`를 확인한다.
4. 우회 이유에 `계단 구간 제외`가 표시되는지 확인한다.
5. 화면에 synthetic·미검증 고지가 있는지 확인한다.

## 시나리오 B — 카메라 HUD

1. `이 경로로 안내 시작` → `카메라 안내 보기`를 누른다.
2. 카메라 권한을 허용한다.
3. 영상 위에 파랑/보라 프리즘 경로 리본이 보이는지 확인한다.
4. 기기를 회전했을 때 나침반 기준 안내 방향이 바뀌는지 확인한다.
5. 영상이 파일 또는 서버에 저장되지 않는지 확인한다.

카메라 HUD는 이동 방향의 개념 증명이며 실제 보도 면에 고정되는 AR이 아니다.

## 시나리오 C — 현장 장애와 즉시 재탐색

1. 지도 또는 카메라 안내에서 `앞 구간 통과 불가`를 누른다.
2. `공사`, `높은 턱`, `계단` 등 사유를 선택한다.
3. `이 구간을 피해 다시 찾기`를 누른다.
4. 현재 세션이 즉시 우회 적용 상태가 되는지 확인한다.
5. 변경 경로가 `1,736.3m`이며 보라색으로 표시되는지 확인한다.
6. 제보 상태가 `pending`, 공용 Graph가 `아직 변경되지 않음`인지 확인한다.

확인 API:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/edges/OSM_E_915477950_ab67cf4d52
Invoke-RestMethod 'http://127.0.0.1:8000/observations/candidates?status=pending'
```

세션 재탐색 뒤에도 위 Edge의 `blocked`는 `false`여야 한다. 새 수동 후보는 `source=manual_camera`, `confidence=null`, `verified=false`여야 한다.

## 사용자 생활권으로 확장할 때

`scripts/fetch_osm.py --bbox LEFT BOTTOM RIGHT TOP`으로 작은 OSM 보행망 스냅샷을 받을 수 있다. 다만 현재 `build_graph.py`는 안양 ONWAY 표본과 데모 노드 선정 규칙에 연결되어 있으므로, 좌표만 바꿔 실행한 결과를 실제 접근성 Graph라고 취급하면 안 된다.

다음 단계에서는 지역 독립형 Graph 빌더에 아래 입력을 명시적으로 받는다.

- origin/destination 좌표
- synthetic 장애 Edge와 사유
- Roadview 참고 URL 및 관찰일
- `source`, `confidence`, `verified=false`

실제 턱·경사·폭은 현장 측정 또는 사람 검수 전까지 `unknown`으로 유지한다.
