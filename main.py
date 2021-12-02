import requests
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# must configure these
FILE_TRACKER = 'http://localhost:8000'
WORKDIR = 'workdir/'
MY_IP = '127.0.0.1'  # set to private ip if collaborating over LAN
MY_PORT = int(sys.argv[1])
MY_USERID = 123
######################


@app.get("/")
async def root():
    return {
        "message": "Backend is running ...",
        "IP": MY_IP,
        "Port": MY_PORT,
        "UserID": MY_USERID,
        "FileTrackerPath": FILE_TRACKER,
        "WorkDirPath": WORKDIR
    }


@app.get('/create-file')
async def create_file(filename):
    params = {
        "file_id": str(filename),
        "user_id": MY_USERID,
        "ip": MY_IP,
        "port": MY_PORT
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
    resp = response.json()
    print("open_file", resp)

    ip = resp['ip']
    port = resp['port']
    resp = requests.get(
        f'http://{ip}:{port}/fetch-file?filename={filename}').json()

    if ('content' in resp) and ('name' in resp) and (resp['name'] == filename):
        params = {
            "file_id": str(filename),
            "user_id": MY_USERID,
            "ip": MY_IP,
            "port": MY_PORT
        }
        requests.post(FILE_TRACKER + '/opened/', data=params)
        return resp

    else:
        return {"status": "Failed to fetch file from the user specified by file tracker."}


@app.get('/close-file')
async def close_file(filename):
    params = {
        "file_id": str(filename),
        "user_id": MY_USERID,
        "ip": MY_IP,
        "port": MY_PORT
    }
    response = requests.post(FILE_TRACKER + '/close/', data=params)
    print("close_file", response.json())
    return response.json()


@app.get('/fetch-file')  # reload file from disk/mem
async def fetch_file(filename):
    contents = open(WORKDIR + str(filename), "r").read()
    # print("fetch_file", filename)
    resp = {
        "name": str(filename),
        "content": str(contents)
    }
    print("fetch_file", resp)
    return resp


@app.get('/edit-file')
async def edit_file(filename, idx, char, type, timestamp):
    """
        - type='insert' or 'delete'
        - calculate crdt index using 'idx' and 'timestamp'
        - apply edit to local copy
        - submit edit to RabbitMQ
    """
    pass

if __name__ == "__main__":
    uvicorn.run("main:app", host=MY_IP, port=MY_PORT,
                reload=True, debug=True, workers=3)
