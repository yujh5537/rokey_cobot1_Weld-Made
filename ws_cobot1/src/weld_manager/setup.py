from setuptools import find_packages, setup

package_name = 'weld_manager'

setup(
    name=package_name,
    version='0.2.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='HyeonJi Nam',
    maintainer_email='rokeycollab12@gmail.com',
    description='phase 2 용접 모션 순서 조정 노드. 경로 계산은 rclpy 없이 도는 순수 Python 모듈이다.',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    # 노드 실행 파일(console_scripts)은 노드 모듈을 만드는 단계(P2-4)에서 더한다
)
