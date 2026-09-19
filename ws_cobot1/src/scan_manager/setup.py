from setuptools import find_packages, setup

package_name = 'scan_manager'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='bhpark',
    maintainer_email='ok778ts123@gmail.com',
    description='스캔 순서와 중지 · 안전복귀 · 재시작을 조정하는 노드. 상태 기계는 rclpy 없이 도는 순수 Python 모듈이다.',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'scan_manager = scan_manager.scan_manager:main'
        ],
    },
)
