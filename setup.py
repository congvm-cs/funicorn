# from setuptools import setup

from setuptools import setup, find_packages
from os import path

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

# setup metainfo
libinfo_py = path.join('funicorn', '__init__.py')
libinfo_content = open(libinfo_py, 'r').readlines()
version_line = [l.strip()
                for l in libinfo_content if l.startswith('__version__')][0]
exec(version_line)  # produce __version__

setup(
    name='funicorn',
    version=__version__,
    description='Funicorn',
    # packages=['funicorn'],
    long_description=open('README.md', 'r').read(),
    long_description_content_type='text/markdown',
    author='congvm',
    author_email='congvm.it@gmail.com',
    license='MIT',
    packages=find_packages(),
    zip_safe=False,
    # install_requires=requirements,
    classifiers=(
        'Programming Language :: Python :: 3.6',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Topic :: Scientific/Engineering :: Artificial Intelligence',
    ),
    # entry_points={
    #     'console_scripts': ['face-serving-start=face_service.cli:main',
    #                         'facessd-serving-start=face_service.cli:main_ssd',
    #                         'facemnet-serving-start=face_service.cli:main_mnet'
    #                         'face-serving-terminate=face_service.cli:terminate'],
    # },
    # keywords='tts nlp tensorflow tacotron machine learning sentence encoding embedding serving',
)
