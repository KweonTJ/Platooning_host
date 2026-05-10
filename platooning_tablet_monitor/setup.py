from glob import glob
import os

from setuptools import find_packages
from setuptools import setup


package_name = "platooning_tablet_monitor"


setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
        (os.path.join("share", package_name, "web"), glob("web/*")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="ktj",
    maintainer_email="kweontj0701@naver.com",
    description="Tablet-friendly web monitor for platooning host status.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "tablet_monitor_server = platooning_tablet_monitor.tablet_monitor_server:main",
        ],
    },
)
