#!/usr/bin/env python3
# coding: utf-8
# This is a small script to download / update the Nga sources.

import requests
import os.path
import sys

urls = [
         'https://raw.githubusercontent.com/crcx/nga/master/nga.c',
         'https://raw.githubusercontent.com/crcx/nga/master/sdk/nabk.py',
         'https://raw.githubusercontent.com/crcx/nga/master/sdk/naje.py',
       ]

print('Downloading')
for url in urls:
    sys.stdout.write('  ' + os.path.basename(url) + '\t\t')
    r =  requests.get(url)
    fn = os.path.basename(url)
    with open(fn, 'w') as f:
        f.write(r.content.decode())
    print(str(len(r.content)) + ' bytes')
print('Finished')
