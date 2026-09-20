from setuptools import find_packages, setup

package_name = 'contact_detector'

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
    maintainer='yujh5537',
    maintainer_email='yujh5537@users.noreply.github.com',
    description='접촉 · 과대 외력 판정 노드와 오프라인 분석기',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'contact_detector = contact_detector.contact_detector:main',
            'analyze_samples = contact_detector.offline:main',
        ],
    },
)
