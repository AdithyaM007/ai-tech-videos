from setuptools import setup

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="python-basics-videos",
    version="1.0.0",
    description="Automated Python Basics series video generation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Adithya Madhushankar",
    author_email="techbytes.explained@gmail.com",
    package_dir={"": "src"},
    py_modules=[
        "config",
        "compat",
        "script_generator",
        "video_generator",
        "generate_episode",
    ],
    python_requires=">=3.10",
    install_requires=[
        "anthropic>=1.0,<2",
        "requests>=2.31.0",
        "moviepy==1.0.3",
        "Pillow>=10.1.0",
        "imageio>=2.33",
        "imageio-ffmpeg>=0.5.1",
        "pygments>=2.17.0",
        "matplotlib>=3.8.0",
        "networkx>=3.2",
        "python-dotenv>=1.0.0",
        "numpy>=1.26",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "pytest-mock>=3.12.0",
            "black>=23.12.0",
            "flake8>=6.1.0",
            "mypy>=1.7.0",
            "bandit>=1.7.5",
        ]
    },
    entry_points={
        "console_scripts": ["python-basics-videos=generate_episode:main"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Multimedia :: Video",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
)
