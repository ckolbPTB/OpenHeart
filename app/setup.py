from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name='openheart',
    author="Johannes Mayer, Christoph Kolbitsch",
    author_email="christoph.kolbitsch@ptb.de",
    url="https://github.com/ckolbPTB/OpenHeart",
    version='0.0.1',
    description='Web app for uploading rawdata to the XNAT OpenHeart Server',
    long_description=long_description,
    long_description_content_type="text/markdown",
    include_package_data=True,
    packages=find_packages(
        where='src',
    ),
    package_dir={"": "src"},
    zip_safe=False,
    install_requires=[
        'flask',
    ],
    extras_require = {
        "dev": [
            "pytest>=3.7",
        ],
    },
)
