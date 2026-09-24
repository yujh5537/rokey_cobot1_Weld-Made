# P5 scan_manager: 용접 중 스캔 시작 · 재시작 거절 (601)

**세션 이름: P5 scan_manager 601 거절**
담당: 병후 · 권장 기한: 9/27 · 공통 절차: `_common.md`

## 이 task
용접이 돌고 있을 때 웹이 스캔 시작이나 재시작을 누르면 scan_manager 가 `WELD_ACTIVE(601)` 로 거절하게 한다. 한 줄짜리 가드지만 로봇을 두 관리자가 동시에 잡지 않게 하는 마지막 울타리다.

## 계약 (확정)
- `docs/phase2/weld-ros-interfaces.md` 7.1(배타 규칙). `/weld/state`(STATE QoS, TRANSIENT_LOCAL) 를 구독한다. 한 번도 안 왔으면 용접이 없다고 본다. 안전복귀(`/scan/home`)는 막지 않는다.
- 파라미터 `weld_state_timeout_s`(출발값 5.0, `state_publish_period_s` 1.0 의 5 배): 마지막 stamp 가 이보다 오래됐으면 없는 것으로 본다(1차 `safety_status_timeout_s` 와 같은 규칙).

## 초기 설계
- `scan_manager.py`: 구독 추가(`WeldState`, `QOS_STATE`), 마지막 메시지 · 수신 시각 보관. `_on_run_goal` · `_on_resume_goal` 의 기존 거절 검사(래치 · 로봇 상태) 앞 또는 뒤에 "weld phase ∉ {IDLE, DONE, ERROR, STOPPED} → 601" 추가. `contract_enums.Reason.WELD_ACTIVE` 는 PR #184 에 이미 있다.
- 로그 한 줄(`/scan/log` WARN, code 601).

## 테스트
- `test/test_node_scan.py`: 가짜 `/weld/state`(WELDING) 발행 뒤 START → 거절 601, RESUME → 601, HOME → 통과. IDLE 발행 뒤 START → 통과. 오래된 stamp → 통과.
- 회귀: `python3 -m pytest src/scan_manager/test -q`.
