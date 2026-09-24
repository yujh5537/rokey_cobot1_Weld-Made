# 최종 산출물 · 발표 계획 (초안, 2026-09-24 병후 · Claude)

근거: 노션 「평가기준」(1-1) · 「프로젝트 서비스 기획」(4-1, 최종 산출물 목록) · 「프로젝트 구성요소(PPT 작성 방법)」(4-3) · 산출물 제출 가이드라인 PDF · PPT 양식(12장). 강의 일정: 9/29(화) 시연 · 발표자료 준비, 9/30(수) 발표 · 평가.

## 1. 외부 요구 요약

| 항목 | 요구 |
|---|---|
| 평가 (조별) | 기능 구현 완전성 · 기능 구현 정확성 · 동작 및 운용 안정성 · 입출력 데이터 이해도 · 기능 동작 지속성(장애 시 연속성). "객관적 자료"로 확인 가능해야 함 |
| 평가 (개인) | 팀 운영 · 의사결정 5 / 의사소통 · 협업 5 / 문제 해결 · 개선 노력 5 |
| 시연 · 발표 | 시연은 발표 전날(9/29). 최종 영상 **1 분 이내** + PPT 로 발표(9/30) |
| 최종 산출물 (조별 노션 등록) | 시스템 아키텍처 · 네트워크 구성도 · 동작 순서도 · 하드웨어 구성 · 토픽/서비스/액션 인터페이스 정의서 · ROS2 Node 구조도 · HMI 화면 구성 · 예외 · 오류 리스트와 처리 · 위험요소 · 안전대책 · Business Requirements |
| 제출물 4 종 | 영상(.mp4) · 발표자료(.pdf) · 소스코드(.zip, src 만 · build/install/log 제외) · Readme.md(시스템 설계 · 플로우차트, OS 환경, 장비 목록, 의존성 requirements.txt, 실행 순서 launch · 스크립트). 파일명 `A-1_협동1_조원1_…_조원6(중도포기).확장자` (중도포기자 반드시 기재) |
| PPT 양식 | 5 장 고정 목차: 01 프로젝트 개요 / 02 팀 구성 및 역할 / 03 수행 절차 및 방법 / 04 수행 경과 / 05 자체 평가 의견. 파일명 `결과보고서_팀명(팀주제명)`. 훈련생이 직접 작성 |

## 2. 최종 산출물 9 종 + BRD — 담당 · 레포에 이미 있는 것 · 할 일

| 산출물 | 담당 | 이미 있는 것 (origin/main) | 할 일 | 결과물 위치 |
|---|---|---|---|---|
| 시스템 아키텍처 | 병후 | `docs/architecture.md`, `docs/design/contact-scan-system-architecture-v1.6.drawio` | phase 2(weld_manager · ExecutePath · weld/*) 추가해 v1.7, png 내보내기 | `docs/deliverables/01-system-architecture.md` + png |
| 네트워크 구성도 | 현지 + 의석 | 루트 README runbook(두 PC · 브로커 · 실기 192.168.1.100 · 포트), `docs/env/setup-record-20260916.md`, `docs/decisions/0002-web-stack-mqtt.md` | 새 그림 1 장: 웹 PC(Docker: mosquitto · FastAPI · PostgreSQL · React) ↔ 메인 PC(ROS 2 노드 6) ↔ 로봇 컨트롤러 · RG2. IP · 포트 · 프로토콜(MQTT · ROS DDS 도메인 30 · DRFL). 의석이 웹 PC 쪽, 현지가 메인 PC · 로봇 쪽 | `02-network.md` + drawio · png |
| 동작 순서도 | 현지 | `scan_manager/README.md` 시퀀스 표, `docs/design/contact-scan-node-diagram-v1.1.md` 시나리오, phase 2 `weld-motion.md` 5절 | 플로우차트 2 장: 스캔(PREPARING → TOP → EDGE ×4 → GEOMETRY → HOMING, 중지 · 안전복귀 · 재시작 분기) · 용접(접근 → 경로 → 후퇴 × 8 → 홈). 예외 분기(래치 · 미접촉 · 정지)를 같은 그림에 | `03-flowchart.md` + drawio · png |
| 하드웨어 구성 | 학민 | `docs/contracts/units-frames.md`(TCP · 홈 · 작업대 원점 · 큐브 · 배치 원칙), `docs/env/tool-tcp-register.md`, 실기 사진 | 장비 목록 표(M0609 · RG2 · 인공눈물 탐침 · 홀더 · 작업대 · 81 mm 큐브 · 테이프 · 메인 PC · 웹 PC · 스위치) + 배치 사진(치수 표기) + TCP · 홈 · 좌표 기준 요약 | `04-hardware.md` + 사진 |
| 인터페이스 정의서 | 병후 | `docs/contracts/ros-interfaces.md` · `mqtt-schema.md` · `docs/phase2/weld-*` | 요약본 1 편: 토픽 · 서비스 · 액션 표(이름 · 타입 · 발행/구독 · 뜻) + MQTT 표 + 대표 msg 3 개 전문. 원본은 링크 | `05-interfaces.md` |
| ROS2 Node 구조도 | 병후 | `docs/design/contact-scan-node-diagram-v1.1.md/.drawio`(연결 40 선) | weld_manager · ExecutePath · /weld/* 추가해 v1.2, png | `06-node-graph.md` + drawio · png |
| HMI 화면 구성 | 의석 | 프런트(React + Three.js 3D 관제), `docs/test-reports/t41-robot-visualization.md`, TR-05 보고 | 화면 캡처(스캔 · 용접)에 요소 번호 → 표시 정보 · 버튼 · 데이터 출처 표. 화면 흐름 1 장 | `07-hmi.md` + 캡처 |
| 예외 · 오류 리스트와 처리 | 학민 | `ros-interfaces.md` 6.1 ReasonCode 표(1xx~6xx) · 7.1 세 정지 경로, `docs/test-reports/daily/20260923.md` §7 SAMPLE_STALE 대응표, safety 감사 보고 | 표 1 개: 상황 → 감지하는 노드 → 코드 → 로봇 동작 → 화면 표시 → 관제자 조치(재시작 · 안전복귀 · 래치 해제). 실기에서 실제로 겪은 것에 ✔ | `08-exceptions.md` |
| 위험요소 · 안전대책 | 학민 | BRD 4.5 · 위험 목록, safety_monitor README, units-frames "탐침 상태 전제조건", 실기 세션 보고(46 N 밀림 · 툴 미등록 12 N · TCP 휘발) | 표: 위험 → 원인 → 대책(설계 · 절차 · 파라미터) → 검증(TR-07 · 실기 사례). 세션 시작 점검표 포함 | `09-safety.md` |
| Business Requirements | 병후 | `docs/BRD.md` v3.2.0 | 그대로 등록 + phase 2 한 절 추가 여부 결정 | `docs/BRD.md` |

- 결과물은 레포 `docs/deliverables/`(신규)에 md + 그림으로 두고, **구글 드라이브 `deliverables` 폴더에 각자 자기 항목을 등록한다**(https://drive.google.com/drive/folders/1tmqt94Llulwl8tlHUwhfSRzS8zGLTK55). 드라이브에는 pdf 또는 png 로 올린다(md 는 레포가 원본).
- 기존 drawio 는 [app.diagrams.net](https://app.diagrams.net)에서 열어 고치고 png 를 같은 이름으로 내보낸다.
- 각 산출물 첫 줄에 "근거: 레포 경로"를 적는다(객관적 자료 요구).

## 3. 제출물 4 종

| 제출물 | 담당(안) | 내용 · 근거 |
|---|---|---|
| 영상 (.mp4, 1 분 이내) | 의석 · 현지 | 9/23 촬영본을 소스로 편집(웹 START → 스캔 → 3D 형상 → 완료), 9/29 용접 성사 시 8 선 장면 추가. 자막으로 단계 표시 |
| 발표자료 (.pdf) | 병후 종합 | PPT 양식 5 장 목차(아래 4 절). 파트 슬라이드는 각자 |
| 소스코드 (.zip) | 현지 | `ws_cobot1/src` + `backend` + `frontend` + `docker` + `docs`. build/install/log · node_modules 제외 |
| Readme.md | 의석 | 루트 README 보강: 시스템 설계 · 플로우차트 그림(02 · 03 · 06 재사용), OS · 버전(`docs/env/versions.md`), 장비 목록(04), `requirements.txt`(Python 의존성 정리 필요), 실행 순서(이미 있는 W0~W3 · M0~M4) |

## 4. PPT 목차

확정본은 **`docs/presentation/outline-v1.md`**(2026-09-24). 양식 5 장 고정 · 15~20 분 · 28~32 장 · 파트별 배분 포함.

## 5. 평가 항목 ↔ 우리 증거 (04-⑦ 장의 뼈대)

| 평가 항목 | 증거 |
|---|---|
| 기능 구현 완전성 | BRD MoSCoW Must 목록 ↔ 구현 · 이슈 · PR 표. 스캔 5 점 → 형상 → 웹 3D, 용접 8 선 |
| 기능 구현 정확성 | TR-01(검출 하중 · 산포), 치수 오차(9/23 실기 폭 +1.5 mm), TR-05(반영 지연 · 중지 1 s), TR-10 |
| 동작 · 운용 안정성 | 실기 통합 3 회 연속 성공(#179), SAMPLE_STALE 대응표, 래치 · 정지 경로 |
| 입출력 데이터 이해도 | 계약 문서(ROS · MQTT · JSON), result.json 저장 · 조회, 단위 · 프레임 규칙, 무효값 규칙 |
| 기능 동작 지속성 | 중지 · 안전복귀 · 재시작 독립, 안전 래치 해제 절차, 예외 · 오류 표(08), 위험 · 안전 대책(09) |

## 6. 일정 (제안, 고정 아님)

| 시점 | 할 일 |
|---|---|
| 9/24~26 | 1차 정리 4 종(README · `docs/phase1/<파트>.md`) + 자기 담당 최종 산출물 초안(2 절) |
| 9/27 | 파트 슬라이드 pptx 제출, 최종 산출물 md · 그림 PR |
| 9/28 | 병후 종합(PPT 합치기 · 01 · 03 · 05 · 대응표), 각자 드라이브 등록, Readme · requirements 정리 |
| 9/29 | 기능 동결(오전) → 실기 → 시연 촬영(영상 1 분) → PPT 04-⑥ · ⑨ 수치 반영 |
| 9/30 | 발표(15~20 분). 제출물 4 종 파일명 확인 후 당일 제출 |
