import os
from glob import glob
from setuptools import find_packages, setup

package_name = "sens_analytics"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=["setuptools", "networkx", "pydot", "watchdog"],
    zip_safe=True,
    maintainer="Sens Engineering",
    maintainer_email="engineering@sens.local",
    description="Static STL analysis nodes and graph adapters for the Sens platform.",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "stl_analyzer_node = sens_analytics.stl_analyzer_node:main",
            "file_watcher_node = sens_analytics.file_watcher_node:main",
            "git_subscriber_node = sens_analytics.git_subscriber_node:main",
            "plc_scraper_node = sens_analytics.plc_scraper_node:main",
            "fallback_semantic_node = sens_analytics.fallback_semantic_node:main",
            "source_lifecycle_manager = sens_analytics.source_lifecycle_manager:main",
            "code_bridge_node = sens_analytics.code_bridge_node:main",
            "code_monitor_node = sens_analytics.code_monitor_node:main",
        ],
    },
)
