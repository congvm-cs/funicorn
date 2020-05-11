from setuptools import setup, find_packages
from funicorn import __version__
from os import path

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

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
    entry_points={
        'console_scripts': ['funicorn-start=funicorn.cli:start',
                            'funicorn-worker-terminate=funicorn.cli:worker_terminate',
                            'funicorn-worker-idle=funicorn.cli:worker_idle',
                            'funicorn-worker-resume=funicorn.cli:worker_resume',
                            'funicorn-worker-restart=funicorn.cli:worker_restart',
                            'funicorn-worker-add=funicorn.cli:add_workers',
                            ],
    }
)
