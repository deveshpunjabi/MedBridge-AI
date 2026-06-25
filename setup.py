from setuptools import setup, find_packages

setup(
    name="medbridge-ai",
    version="1.0.0",
    packages=find_packages(),
    py_modules=["main", "config"],
    install_requires=[
        "click>=8.1.0",
        "google-genai>=1.0.0",
        "spacy>=3.7.0",
        "mcp>=1.0.0",
        "requests>=2.31.0",
        "python-dotenv>=1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "med-ai=main:main_entry",
        ],
    },
)
