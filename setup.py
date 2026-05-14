from setuptools import find_packages, setup

with open("requirements.txt") as f:
    install_requires = f.read().strip().split("\n")

# get version from __version__ variable in food_mes_kr/__init__.py
from food_mes_kr import __version__ as version

setup(
    name="food_mes_kr",
    version=version,
    description="ERPNext customization for Korean food & beverage manufacturing (HACCP, LOT traceability, FEFO).",
    author="Your Company",
    author_email="dev@example.com",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=install_requires,
)
