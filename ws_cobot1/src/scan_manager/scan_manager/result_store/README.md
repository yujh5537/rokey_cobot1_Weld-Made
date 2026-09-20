# result_store

스캔의 진행 기록과 최종 결과 원본을 메인 PC 파일로 보존하는 모듈이다(BRD 4.4.7). 담당은 병후다.
중지 · 프로세스 종료 뒤에도 "어디까지 했고 무엇을 확정했는지"가 남아 있어야 재시작(4.4.8)이 기존 측정값을 유지한 채 이어 갈 수 있다.

- `rclpy` · `contact_scan_interfaces` · `state_machine`을 import하지 않는 순수 Python이다. `contract_enums`(`Phase` · `Direction`)만 쓴다.
- **사실만 기록한다.** 재시작을 허용할지는 판단하지 않는다(판단은 `scan_manager/resume.py`와 상태 기계). 웹 전달 · DB 저장 여부도 기록하지 않는다(그것은 웹 쪽의 사실이다).
- 단위는 ROS 내부 단위(m · rad · N) 그대로다. mm 변환은 mqtt_bridge에서만 한다.
- 기준은 `docs/contracts/ros-interfaces.md` v0.1.1이다. 파일 형식은 계약 9장의 TBD이며 아래는 그에 대한 안이다.

| 파일 | 내용 |
|---|---|
| `records.py` | 기록 자료형(dataclass), 값 규칙 검사, 파일(dict) 변환 |
| `store.py` | `ResultStore`, 원자적 쓰기, 오류 클래스, 재개 후보 조회 |

## 파일 구조
```
<result_dir>/<scan_id>/progress.json   진행 기록. 바뀔 때마다 통째로 원자적 교체
<result_dir>/<scan_id>/result.json     최종 결과 원본. GEOMETRY 끝에 한 번만 쓴다
```
- `result_dir`은 생성자 인자다. 모듈 안에 경로가 없다. ROS 파라미터 `result_dir`의 선언과 yaml은 T19의 일이고, 출발값은 `ws_cobot1/data/`(gitignore)다.
- `scan_id`는 계약 6.2절의 `YYYYMMDD-HHMMSS-xxxx`만 받는다(디렉터리 이름이라 경로 문자를 막는다).
- 파일을 둘로 나눈 이유: 결과는 "원본"이라 뒤따르는 HOMING · DONE 갱신이 다시 쓰면 안 된다. 진행 기록에는 `result_saved` · `result_success`만 남긴다.
- 방향별 편향 보정량은 `result.json`에만 있다(계약 3.5절).

### 공통 규칙
| 항목 | 규칙 |
|---|---|
| 헤더 | `schema_version`(현재 1) · `kind`(`contact_scan.progress` / `contact_scan.result`) · `units` |
| 미측정 · 실패 값 | 파일에서 `null` + 짝이 되는 `*_valid=false`. **0을 쓰지 않는다.** NaN · Infinity는 파일에 나오지 않는다(`allow_nan=False`) |
| 시각 | `{"sec", "nanosec"}` 정수 쌍. float로 바꾸지 않는다 |
| phase · direction | 이름 문자열(`"EDGE_SEARCH"` · `"POS_X"`). `reason_code`는 정수 |
| 좌표 | `position_m` · `orientation_xyzw` · `frame_id` · `stamp`를 항상 같이 둔다 |
| 키 이름 | 계약 msg를 옮긴 필드는 계약 이름 그대로(`z_drop_m` · `descend_speed_mps` · `z_top` · `width`). 여기서 새로 만든 필드는 단위 접미사(`position_m` · `correction_m` · `force_n`) |

### progress.json
| 블록 | 내용 |
|---|---|
| `scan_id` · `started_at` · `updated_at` · `revision` | `revision`은 쓸 때마다 +1 |
| `state` | `phase` · `direction` · `progress` · `progress_total` · `motion_id` (ScanState, 계약 3.4절) |
| `last_motion_id` | 이 작업에서 기록된 가장 큰 `motion_id`. `state.motion_id`는 휴지 phase에서 0으로 돌아가므로 따로 둔다 |
| `frames` | `detection`(판정 · 정지 좌표의 프레임, `base_link`) · `result`(ScanResult의 프레임, `workpiece_fixture`) |
| `direction_order` | 모서리 탐색 순서 |
| `config` | ScanConfig 12개 값 + `*_set`(계약 3.9절 이름 그대로). 모르는 값은 `null` + `*_set=false` |
| `node_params` | scan_manager 자체 파라미터의 자유 형식 스냅샷(`search_origin_pose` · `base_to_fixture` · `tip_radius_m` 등). 무엇을 넣을지는 T19가 정한다 |
| `measurements.top` · `measurements.edges.{POS_X,NEG_X,POS_Y,NEG_Y}` | 아래 "측정값 한 칸" |
| `interruptions[]` | 작업 중지 목록. 중지를 접수한 시점의 `phase` · `direction` · `progress`, 중단 위치 `pose`(+`pose_valid`), `during_final_homing`, `stopped_at`, `resumed_at`(`null` = 아직 재시작하지 않음) |
| `home_return` | 홈 안전복귀의 사실. `requested` · `request_count` · `requested_at` · `interruptions_at_request`(접수 때까지 기록돼 있던 중지의 수. "어느 중지 뒤의 복귀인가"를 시계에 기대지 않고 남긴다) · `origin_phase` · `completed`(`null` = 끝을 모름) · `completed_at` · `final_pose` |
| `failure` | `reason_code` · `detail` · `phase`(실패가 난 phase) · `recorded_at`. 없으면 `null` |
| `result_saved` · `result_success` | `result.json`을 썼는지, 그 형상이 성공인지(`null` = 아직 없음) |

**측정값 한 칸**
| 필드 | 뜻 |
|---|---|
| `status` | `NOT_ATTEMPTED`(아직 탐색 안 함) · `CONFIRMED`(확정) · `FAILED`(탐색했지만 실패). 미탐색과 실패를 이 값으로 구분한다 |
| `valid` | `status == CONFIRMED` |
| `detection` | **판정 좌표**(ContactEvent, 계약 3.3절): `event_type` · `event_id` · `sample_id` · `motion_id` · `source` · `pose`(`stamp` = `pose_stamp`) · `force_stamp` · `detect_stamp` · `force_delta_n` · `z_drop_m` + `z_drop_valid` · `debounce_count` · `wrench`(선택). 확정이 아니면 `null` |
| `stop_pose` + `stop_pose_valid` | **정지 좌표**(`ExecuteMotion.Result.pose`). 판정 좌표와 섞지 않는다. 실패한 탐색에서는 "어디서 멈췄는가"다 |
| `reason_code` · `detail` | 실패 사유. 실패가 아니면 `null` |
| `recorded_at` | store가 기록한 시각 |

### result.json
| 블록 | 내용 |
|---|---|
| `shape` | ScanResult(계약 3.5절)와 같은 이름 · 같은 순서 규약. `z_top` · `x_pos` · `x_neg` · `y_pos` · `y_neg` · `support_z`(+`*_valid`), `width` · `length` · `height`(+`dims_valid`), `vertices[8]` · `edges[12]` · `path_candidates[4]`(+`box_valid`), `success` · `reason_code` · `detail` · `frame_id` · `started_at` · `finished_at`. 무효여도 배열 길이를 유지하고 원소를 `null`로 둔다 |
| `bias_corrections.{방향}` | `raw_coordinate_m`(보정 전 판정 좌표의 그 축 값) · `correction_m`(진행 방향 반대로 적용한 크기) · `valid` · `inputs`(`z_drop_m` · `tip_radius_m` · `slide_speed_mps` · `detect_latency_s` 등. 모르면 `null`) |
| `config` · `node_params` | 진행 기록에서 store가 옮겨 적는다. 결과 파일 하나만으로 재현 조건을 알 수 있게 한다 |
| `saved_at` | store가 기록한 시각 |

형상 계산이 실패한 결과(`success=false`, 예: `INVALID_SHAPE`)도 원본으로 저장한다. 얻은 값만 있고 나머지는 `null`이다.
`success=true`이면 모든 값이 유효해야 한다(`*_valid` · `dims_valid` · `box_valid`). 하나라도 무효면 `ValueError`다.

## 값 규칙 (CLAUDE.md 규칙 4)
- `valid=false`인데 숫자가 오면 `ValueError`다. **0을 끼워 넣을 수 없다.** NaN만 `None`으로 바꾼다(ROS msg가 미측정을 NaN으로 싣기 때문이다).
- `valid=true`인데 `None` · NaN · inf이면 `ValueError`다. bool도 숫자로 받지 않는다(`False`가 `0.0`이 되지 않게).
- 같은 검사를 **읽을 때도** 한다. 누군가 파일의 `null`을 `0.0`으로 바꿔 놓았다면 `CorruptRecordError`다.
- 실제로 잰 `0.0`(예: `x_neg = 0.0`)은 `valid=true`인 정상값이다.
- msg로 옮길 때: `Measured.value is None` → `NaN` + `*_valid=false`. msg에서 가져올 때: `Measured(msg.z_top, msg.z_top_valid)`.

## 내구성 · 오류
- 모든 쓰기: 같은 디렉터리의 임시 파일 → `flush` + `fsync` → `os.replace` → 디렉터리 `fsync`. 쓰는 도중에 죽어도 이전 파일이 그대로 남는다. 남은 임시 파일(`.progress.json.*.tmp`)은 읽을 때 무시한다.
- 인스턴스는 기록을 메모리에 들고 있지 않다. 바꿀 때마다 파일을 읽어 고친 뒤 쓴다. 쓰기가 실패해도 메모리와 파일이 어긋나지 않고, 프로세스를 재시작한 새 인스턴스가 같은 기록을 본다.
- 한 프로세스 안의 여러 스레드는 안전하다(내부 락). **여러 프로세스가 같은 작업을 쓰는 것은 막지 않는다.** scan_manager 하나만 쓴다.
- `result.json`을 쓴 직후 · 진행 기록에 표시하기 전에 죽은 경우: 다음 `save_result`가 `ResultAlreadySaved`를 던지면서 진행 기록의 표시를 있는 파일대로 고친다. 조회에서는 `ResumeCandidate.result_file_exists`로 드러난다.

| 예외 (`ResultStoreError` 하위) | 언제 |
|---|---|
| `RecordNotFound` | 그 `scan_id`의 기록 · 결과가 없다 |
| `ScanAlreadyExists` | 이미 기록이 있는 `scan_id`로 `begin_scan` |
| `MeasurementAlreadyConfirmed` | 확정 측정값을 덮어쓰려 했다(BRD 4.4.8 "기존 측정값 유지"). `FAILED` → `CONFIRMED`는 된다 |
| `ResultAlreadySaved` | `result.json`은 한 번만 쓴다 |
| `RecordStateError` | 기록과 맞지 않는 호출(중지 기록 없이 `record_resume`, 접수 없이 `record_home_finished`) |
| `CorruptRecordError` | JSON이 아니다 · 필드 누락 · 값 규칙 위반 · 파일의 `scan_id`가 디렉터리와 다르다. `.scan_id` · `.path` |
| `UnsupportedSchemaError` | 모르는 `schema_version`. `.found`. 읽지도 덮어쓰지도 않는다 |

입력값이 틀리면(형식이 아닌 `scan_id`, `valid=false`에 숫자 등) `ValueError`다.
깨진 기록은 그 작업에만 영향을 준다. 다른 작업의 `load` · 쓰기는 그대로 된다.

## API
```python
from scan_manager.result_store import (
    ResultStore, ConfigSnapshot, Frames, Stamp, PoseRecord, Detection, Measurement,
    Interruption, ShapeResult, SegmentRecord, Measured, BiasCorrection, TOP,
    EVENT_CONTACT, EVENT_EDGE,
)

store = ResultStore(result_dir, now_fn=lambda: Stamp(*node.get_clock().now().seconds_nanoseconds()))
```
| 메서드 | 부르는 시점 | 비고 |
|---|---|---|
| `begin_scan(scan_id, *, state, config, frames, direction_order, started_at=None, node_params=None)` | START가 **접수된 뒤** | `state`는 그 Snapshot(PREPARING). 접수 전에 부르면 거절된 작업의 기록이 남는다 |
| `record_state(snapshot)` | 상태가 바뀔 때마다 | T10의 `Snapshot`을 그대로 넣는다(`scan_id` · `phase` · `direction` · `progress` · `progress_total` · `motion_id` 속성만 본다). `scan_id == ""`(IDLE)이면 `ValueError` |
| `record_top(scan_id, Measurement)` | 윗면 확정. **그 뒤에** `notify(TOP_FOUND)` | `detection.event_type`은 `CONTACT` |
| `record_edge(scan_id, direction, Measurement)` | 모서리 확정. **그 뒤에** `notify(EDGE_FOUND)` | `EDGE` |
| `record_attempt_failed(scan_id, target, reason_code, detail='', stop_pose=None)` | 한 점의 탐색 실패(`NO_CONTACT` · `NO_EDGE` …) | `target`은 `TOP` 또는 `Direction` |
| `record_failure(scan_id, failure)` | `notify(FAILED)` 뒤 | T10의 `sm.failure`를 그대로 넣는다(`reason_code` · `detail` · `phase`) |
| `record_stop(scan_id, Interruption(phase, direction, progress, pose, during_final_homing))` | 정지 완료를 확인하고 중단 위치를 얻은 뒤, **`notify(STOP_CONFIRMED)` 전에**. STOPPED가 된 뒤에야 안전복귀가 접수되므로 그래야 "중지 → 안전복귀"의 순서가 기록에서도 같다 | `phase` 등은 STOP 접수 **직전**의 Snapshot 값. 마무리 HOMING 중이었는지는 호출 측이 밝힌다(store는 추론하지 않는다) |
| `record_resume(scan_id)` | RESUME이 접수된 뒤 | 가장 최근 중지에 `resumed_at`을 채운다 |
| `record_home_requested(scan_id, origin_phase=None)` | 안전복귀(HOME)가 접수된 뒤 | 마무리 복귀(7.4절)에는 쓰지 않는다 |
| `record_home_finished(scan_id, completed, final_pose=None)` | 안전복귀가 끝났다(성공 · 실패) | |
| `save_result(scan_id, ShapeResult, bias_corrections=None)` | GEOMETRY 끝, `/scan/result` 발행 **전**(계약 7.4절) | 실패한 형상도 저장한다 |
| `load(scan_id)` → `ScanRecord` · `load_result(scan_id)` → `ResultRecord` · `has_result(scan_id)` | | 그 작업의 파일만 읽는다 |
| `scan_ids()` · `list_scans()` → `(records, errors)` | | 최신순. 읽지 못한 기록은 `errors`로 나온다 |
| `find_resume_candidate(scan_id='')` → `ResumeCandidate` | Resume goal | 아래 |

### 재개 후보
```python
candidate = store.find_resume_candidate(goal.scan_id)   # "" = 가장 최근 중단 작업
record = candidate.record                                # 없으면 None → NO_RESUMABLE_SCAN
```
- `""`이면 **phase가 DONE이 아닌 가장 최근 기록**이다. ERROR로 끝난 최신 작업이 있으면 그것이 후보이고, 그보다 오래된 STOPPED 작업은 후보가 아니다. T10의 "START는 이전 재개 지점을 버린다"와 같은 의미다.
- 값이 있으면 그 기록을 phase와 무관하게 돌려준다. 없으면 `record=None`, 깨졌으면 예외다.
- "가장 최근"은 `scan_id`의 사전순이다. **`scan_id`는 벽시계로 발급해야 한다.** sim time(1970년부터)으로 발급하면 순서가 깨진다.

돌려주는 것은 사실뿐이다. 판단(계약 5.3절의 거절 사유)은 호출 측이 한다.
이 사실들만으로 T10 상태 기계의 RESUME 판정(`OK` · `NOT_SUPPORTED` · `NO_RESUMABLE_SCAN`)을 맞힐 수 있다는 것을 `test_recorded_facts_predict_the_resume_verdict`가 무작위 명령열로 확인한다(그 테스트의 `verdict_from_facts`가 판정 예시다).
| 사실 | 쓰임 |
|---|---|
| `record.resume_point`(`phase` · `direction` · `progress` · `pose` · `resumed_at`) | **재개 지점**: 측정 단계 또는 마무리 HOMING에서의 가장 최근 중지. 어느 단계 · 방향에서 멈췄는가. RESUMING · 안전복귀 HOMING 중의 중지는 재개 지점을 바꾸지 않는다(T10 상태 기계와 같은 규칙). `None`이면 측정 중에 중지된 적이 없다(중지 기록 없이 프로세스가 죽었다면 중단 위치를 모른다) |
| `record.last_interruption` · `record.state` | 가장 최근 중지(복귀 도중의 중지일 수 있다)와 마지막으로 기록된 상태. **재개 방향을 여기서 읽지 않는다** |
| `record.top` · `record.edges` · `record.confirmed_edges` | 유지할 기존 측정값 |
| `record.home_return_since_resume_point` | 재개 지점 뒤에 안전복귀를 접수했다 → `NOT_SUPPORTED`(5.3절). 끝까지 갔는지와 무관하고, **복귀 도중에 다시 중지된 경우에도 참**이다. 순서는 시각이 아니라 `interruptions_at_request`로 본다. `record.home_return_requested`는 "이 작업에서 한 번이라도" |
| `record.stopped_during_final_homing` · `record.result_saved` · `candidate.result_file_exists` | 측정이 이미 끝난 작업이다 → `NO_RESUMABLE_SCAN`(7.4절). 예외: 재개 지점이 GEOMETRY이고 `result_saved`가 참이면(결과를 쓴 직후 · `GEOMETRY_DONE` 전에 중지) 상태 기계는 재시작을 받는다. 그때는 다시 계산하지 말고 `load_result()`로 읽어 재발행한다 |
| `record.failure` | 실패로 끝난 작업(재시작 허용 조건은 TBD, #26) |
| `record.last_motion_id` | 재시작 뒤에 `motion_id`를 이어서 발급한다 |
| `candidate.is_latest` · `candidate.newer_scan_ids` | 더 나중에 시작된 작업이 있는가 |
| `candidate.skipped_errors` | 후보보다 최신인데 읽지 못한 기록. 조용히 건너뛰지 않으려고 같이 준다 |

## 사용 주의: 상태 기계의 `on_change` 안에서 쓰지 않는다
쓰기는 `fsync`까지 하고 돌아온다(수 ms ~ 수십 ms). T10의 `on_change`는 **상태 기계의 락을 쥔 채** 불리므로, 그 안에서 store의 쓰기 메서드를 부르면 그동안 `/scan/stop`의 `request(STOP)`이 기다린다.
반대로 락 밖에서 `request()` · `notify()`의 반환값으로 기록하면 두 스레드의 쓰기 순서가 뒤집혀 옛 상태가 파일에 남을 수 있다(Snapshot에는 순번이 없다).

권장 연결: **쓰기 전용 스레드 1개**에 모든 쓰기를 맡긴다. 스레드가 하나라서 넣은 순서대로 쓰인다.
```python
from concurrent.futures import ThreadPoolExecutor

self._writer = ThreadPoolExecutor(max_workers=1, thread_name_prefix='result_store')

def _on_change(self, snap):                      # 락 안: 넣기만 하고 돌아온다
    self._publish_state(snap)
    if not snap.scan_id:
        return
    if snap.scan_id != self._begun:              # 새 작업의 첫 통지(PREPARING) = begin_scan
        self._begun = snap.scan_id
        job = self._writer.submit(self._store.begin_scan, snap.scan_id, state=snap, **self._begin_args)
    else:
        job = self._writer.submit(self._store.record_state, snap)
    job.add_done_callback(self._log_write_error)  # Future의 예외는 꺼내 보지 않으면 사라진다

# 측정값 · 결과: 디스크에 있는 것을 확인한 뒤 다음 단계로 간다 (on_change 밖, 시퀀스 스레드)
self._writer.submit(self._store.record_edge, scan_id, direction, measurement).result()
self._sm.notify(Signal.EDGE_FOUND)
```
- `_begin_args`(config · frames · direction_order · started_at · node_params)는 `request(START)`를 부르기 **전에** 준비해 둔다. START가 거절되면 `on_change`가 불리지 않으므로 기록도 생기지 않는다.
- 재시작으로 기존 작업을 이을 때는 `self._begun = record.scan_id`로 둔다(`begin_scan`을 다시 부르지 않는다). 노드는 기록에서 상태를 되돌릴 때(`_adopt_recorded_scan`) 그렇게 한다.
- 이 연결은 `test/test_result_store_scenario.py`의 `SimScanManager`가 그대로 쓰며, 쓰기 스레드가 멈춰 있어도 STOP이 접수 · 확인되는 것을 테스트로 고정했다.

## 테스트
```bash
cd ws_cobot1
python3 -m pytest src/scan_manager/test -q     # ROS를 source하지 않은 셸. tmp_path만 쓴다
```
| 파일 | 내용 |
|---|---|
| `test/test_result_store_records.py` | 값 규칙: `None` 왕복, 0 · NaN 차단, 플래그 일치 |
| `test/test_result_store.py` | 새 인스턴스로 다시 읽기, 쓰기 도중 실패(예외 주입), 깨진 파일 · 모르는 `schema_version`, 재개 후보 |
| `test/test_result_store_scenario.py` | **시뮬레이션**: T10 상태 기계 + 가상 직육면체 + store. 정상 완료, +x 중 중지 → (프로세스 재시작) → 재시작 → `z_top` 유지, 안전복귀 뒤 재시작 거절, 마무리 HOMING 중 중지, 탐색 실패, 모션 도중 프로세스 종료, 느린 디스크 |
| `test/result_store_helpers.py` | 공용 입력(수치는 테스트용 임의값) |
