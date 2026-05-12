from setuptools import setup, find_packages

setup(
    name="scalekit-sdk-python-lite",
    version="0.1.0",
    description="Lightweight Scalekit SDK for Python 3.5+",
    packages=find_packages(exclude=["tests*"]),
    python_requires=">=3.5",
    install_requires=[
        "rsa>=3.4",
    ],
    extras_require={
        "dev": ["pytest"],
    },
)
