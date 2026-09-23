cmake_minimum_required(VERSION 3.8)
project(contact_scan_interfaces)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(action_msgs REQUIRED)

# 타입 전문의 기준은 docs/contracts/ros-interfaces.md 3~6장이다. 파일을 고칠 때는 계약 문서와 같이 고친다.
rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/RobotSample.msg"
  "msg/RobotStatus.msg"
  "msg/ContactEvent.msg"
  "msg/ScanState.msg"
  "msg/ScanResult.msg"
  "msg/Segment.msg"
  "msg/ScanLog.msg"
  "msg/SafetyStatus.msg"
  "msg/WebHeartbeat.msg"
  "msg/ScanConfig.msg"
  "msg/ReasonCode.msg"
  "msg/WeldConfig.msg"
  "msg/WeldState.msg"
  "msg/WeldLine.msg"
  "msg/WeldResult.msg"
  "srv/StopRobot.srv"
  "srv/StopScan.srv"
  "srv/TareForce.srv"
  "srv/SetConfig.srv"
  "srv/ResetSafety.srv"
  "srv/StopWeld.srv"
  "action/RunScan.action"
  "action/ReturnHome.action"
  "action/Resume.action"
  "action/ExecuteMotion.action"
  "action/RunWeld.action"
  "action/ExecutePath.action"
  DEPENDENCIES builtin_interfaces geometry_msgs action_msgs
)

# QoS 프로파일(계약 6.3절). rosidl 이 이미 contact_scan_interfaces 라는 Python 패키지를
# 설치하므로 같은 이름으로는 설치할 수 없다(CMake 타깃 중복). 다른 모듈 이름으로 둔다.
ament_python_install_package(contact_scan_qos)

# 테스트용 ROS_DOMAIN_ID 를 고르는 공용 헬퍼(#126). 네 패키지의 conftest 가 쓴다.
ament_python_install_package(contact_scan_testing)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  # colcon test 는 이 패키지 자신의 install 환경을 source 하지 않는다. 설치된 결과물을 직접 가리킨다.
  foreach(_test test_constants test_qos test_contract_sync test_domain_isolation)
    ament_add_pytest_test(${_test} test/${_test}.py
      APPEND_ENV PYTHONPATH=${CMAKE_INSTALL_PREFIX}/${PYTHON_INSTALL_DIR}
      APPEND_LIBRARY_DIRS ${CMAKE_INSTALL_PREFIX}/lib
      TIMEOUT 60
    )
  endforeach()
endif()

ament_package()
