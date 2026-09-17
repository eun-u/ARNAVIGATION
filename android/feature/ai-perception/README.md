# AI perception offline harness

M2의 첫 단계는 모델이나 영상 코덱에 종속되지 않는 결정론적 평가 코어다.

`OfflineReplayHarness`는 한 번에 하나의 `PerceptionFrameLease`만 열어
`PerceptionEngine`에 전달한다. 따라서 입력 크기와 관계없이 in-flight frame 수는 1로
제한된다. 각 프레임은 성공·실패 여부와 무관하게 닫힌다.

현재 산출 지표:

- 라벨과 IoU 임계값을 이용한 TP, FP, FN
- 전체 및 클래스별 precision, recall, F1
- 엔진이 보고한 inference latency의 mean, p50, p95, max
- 실패 프레임과 원인, 실행 중 관찰된 모델 버전

평가 데이터 어댑터는 각 샘플을 `OfflineFrameCase`로 변환한다. `openFrame`은 녹화
세션이나 정지 이미지에서 짧은 수명의 frame lease를 만들고, `expected`에는 정규화된
좌표의 정답 영역을 넣는다. 하네스는 디코더를 소유하지 않으므로 같은 평가 코어를
ARCore Recording/Playback, 추출 이미지, 합성 프레임에 재사용할 수 있다.

다음 연결 순서:

1. 평가용 녹화 세션과 개인정보 비식별화 규칙 확정
2. 녹화 프레임/annotation manifest를 `OfflineFrameCase`로 읽는 decoder adapter 추가
3. MediaPipe 또는 LiteRT baseline `PerceptionEngine` 연결
4. 모델별 JSON/CSV 리포트와 golden regression gate 추가

테스트 실행:

```powershell
$env:JAVA_HOME='C:\Program Files\Android\Android Studio\jbr'
.\gradlew.bat :feature:ai-perception:testDebugUnitTest
```
