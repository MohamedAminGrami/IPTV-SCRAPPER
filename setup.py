from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="iptv-scraper",
    version="2.7.1",
    author="Musashi",
    description="A CLI tool to scrape and validate working IPTV links",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/iptv-scraper",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    install_requires=[
        "beautifulsoup4",
        "requests",
        "termcolor",
        "colorama",
        "art",
    ],
    entry_points={
        "console_scripts": [
            "iptv-scraper=iptv_scraper.cli:main",
            "ipsc=iptv_scraper.cli:main",
        ],
    },
)
