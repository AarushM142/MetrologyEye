import os
from dotenv import load_dotenv

load_dotenv()

from app.services.extract import extract

image = open('snickers_back.jpg', 'rb').read()
try:
    print(extract(image, 'dummy text'))
except Exception as e:
    import traceback
    traceback.print_exc()
