from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="iptv-scraper",
    version="2.7.1",
    author="Musashi",
    author_email="",
    description="A powerful CLI tool to scrape and validate working IPTV links",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/iptv-scraper",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Console",
        "Intended Audience :: End Users/Desktop",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Multimedia :: Video",
        "Topic :: Internet",
    ],
    keywords="iptv, scraper, m3u, playlist, streaming, tv, channels",
    python_requires=">=3.6",
    install_requires=[
        "beautifulsoup4>=4.9.0",
        "requests>=2.25.0",
        "termcolor>=1.1.0",
        "colorama>=0.4.0",
        "art>=5.0",
    ],
    entry_points={
        "console_scripts": [
            "iptv-scraper=iptv_scraper.cli:main",
            "ipsc=iptv_scraper.cli:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/MohamedAminGrami/iptv-scraper/issues",
        "Source": "https://github.com/MohamedAminGrami/iptv-scraper",
    },
)
