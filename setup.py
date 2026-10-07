from setuptools import setup, find_packages

with open("requirements.txt") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="coe",
    version="0.1.0",
    description="CLI evaluation framework for testing and grading AI prompts",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Seth Faerber",
    author_email="seth.faerber@improving.com",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "coe=coe.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)
