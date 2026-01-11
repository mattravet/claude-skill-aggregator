from setuptools import setup, find_packages

setup(
    name="claude-skill-aggregator",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "requests>=2.31.0",
        "pyyaml>=6.0",
        "click>=8.1.0",
        "rich>=13.0.0",
        "anthropic>=0.18.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "skill-agg=aggregator.cli:main",
        ],
    },
    python_requires=">=3.10",
)
