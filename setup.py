from setuptools import setup

with open('requirements.txt') as f:
    requirements = f.read().splitlines()

setup(
   name='funicorn',
   version='1.0',
   description='Funicorn',
   author='congvm',
   author_email='congvm.it@gmail.com',
   packages=['funicorn'],
   install_requires=requirements,
)