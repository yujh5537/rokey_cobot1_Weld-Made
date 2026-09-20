from setuptools import find_packages, setup

package_name = 'robot_manager'

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
    maintainer='rokeyhak',
    maintainer_email='rokeyhak@users.noreply.github.com',
    description='두산 M0609 제어와 RobotSample · RobotStatus 발행',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'robot_manager = robot_manager.robot_manager:main',
        ],
    },
)
