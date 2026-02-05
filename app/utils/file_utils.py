import os

def save_file(file, destination: str):
    with open(destination, "wb") as f:
        f.write(file)
