#!/usr/bin/env python

"""The setup script."""

from setuptools import find_packages, setup

with open("README.md") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = ["requests", "hl7"]

test_requirements = []

setup(
    author="Open Healthcare Network",
    author_email="info@ohc.network",
    python_requires=">=3.6",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    description="",
    install_requires=requirements,
    license="MIT license",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="teleicu_devices",
    name="teleicu_devices",
    packages=find_packages(
        include=[
            "camera_device",
            "camera_device.*",
            "gateway_device",
            "gateway_device.*",
            "lab_analyzer_device",
            "lab_analyzer_device.*",
            "vitals_observation_device",
            "vitals_observation_device.*",
        ]
    ),
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/ohcnetwork/care_teleicu_devices",
    version="0.1.0",
    zip_safe=False,
)
