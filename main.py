import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FILE_TRACKER = 'http://localhost:8000'


@app.get("/")
async def root():
    return {"message": "Backend is running ..."}


@app.get('/create-file')
async def create_file(filename):
    params = {
        "file_id": str(filename),
        "user_id": 123,
        "ip": "127.0.0.1",
        "port": 1234
    }
    response = requests.post(FILE_TRACKER + '/create/', data=params)
    f = open("workdir/"+filename, "w")
    f.write("# Start Collaborating! ...")
    f.close()
    print("create_file", response.json())
    return response.json()


@app.get('/open-file')
async def open_file(filename):
    response = requests.get(FILE_TRACKER + '/open/?file_id=' + str(filename))
    print("open_file", response.json())
    return response.json()
    # response contains IP, port to fetch file


@app.get('/close-file')
async def close_file(filename):
    params = {
        "file_id": str(filename),
        "user_id": 123,
        "ip": "127.0.0.1",
        "port": 1234
    }
    response = requests.post(FILE_TRACKER + '/close/', data=params)
    print("close_file", response.json())
    return response.json()


@app.get('/fetch-file')  # reload file from disk/mem
async def fetch_file(filename):
    contents = open('workdir/' + str(filename), "r").read()
    # print("fetch_file", filename)
    resp = {
        "name": str(filename),
        "content": str(contents)
    }
    print("fetch_file", resp)
    return resp


@app.post('/insert-chars')
async def insert_chars(index, chars):
    # TODO call to CRDT/RabbitMQ
    print(f"Insert 'f{chars}' at index {index}")
    return {"status": "success"}


@app.post('/delete-chars')
async def delete_chars(index, count):
    # TODO call to CRDT/RabbitMQ
    print(f"Delete 'f{count}' chars starting from index {index}")
    return {"status": "success"}
