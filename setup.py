import setuptools

setuptools.setup(
    name="kingspan-connect-sensor",
    version="1.0",
    author="Jon Connell",
    author_email="python@figsandfudge.com",
    description="API to get oil tank from Kingspan SENSiT sensors",
    license='MIT',
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    url="https://github.com/masaccio/kingspan-connect-sensor",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
