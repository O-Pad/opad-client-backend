import requests
from flask import request
import uvicorn
from flask import Flask
from fastapi.middleware.cors import CORSMiddleware
from mahitahi.mahitahi import Doc
import sys
from rabbitmq import rabbitmq_listen
from multiprocessing import Process
import pika
import json
from pydantic import BaseModel


app = Flask(__name__)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# must configure these
FILE_TRACKER = 'http://localhost:8000'
RABBITMQ_HOST = 'localhost'

MY_IP = 'be90-122-161-48-178.ngrok.io'  # set to private ip if collaborating over LAN
MY_PORT = 80

WORKDIR = 'workdir/'
MY_USERID = 18059
######################
file_cursors = {
    'hello': 0,
    'file2': 0
}

crdt_file = {
    'hello': Doc(),
    'file2': Doc()
}

rabbitmq_listeners = {}


def create_CRDT_Embeddings(content, doc_file):
    # create logoot/CRDT embeddings
    pos = 0
    for c in content:
        doc_file.insert(pos, c)
        pos += 1

@app.after_request
def after_request(response):
    header = response.headers
    header['Access-Control-Allow-Origin'] = '*'
    header['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    header['Access-Control-Allow-Methods'] = 'OPTIONS, HEAD, GET, POST, DELETE, PUT'
    return response

@app.route("/")
async def root():
    return {
        "message": "Backend is running ...",
        "IP": MY_IP,
        "Port": MY_PORT,
        "UserID": MY_USERID,
        "FileTrackerPath": FILE_TRACKER,
        "RabbitMQ Host": RABBITMQ_HOST,
        "WorkDirPath": WORKDIR
    }


@app.route('/create-file')
async def create_file():
    filename = request.args.get('filename')
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

    # only do this once
    crdt_file[filename] = Doc()
    crdt_file[filename].site = MY_USERID
    file_cursors[filename] = 0

    # spawn rabbitmq listener
    rabbitmq_listeners[filename] = Process(
        target=rabbitmq_listen, args=(filename, ))
    rabbitmq_listeners[filename].start()

    resp = response.json()
    resp["content"] = ""
    resp["key"] = filename

    print("create_file", resp)
    return resp


@app.route('/open-file')
async def open_file():
    filename = request.args.get('filename')
    response = requests.get(FILE_TRACKER + '/open/?file_id=' + str(filename))
    resp = response.json()
    print("open_file", resp)

    # make sure actually opened

    ip = resp['ip']
    port = resp['port']
    resp = requests.get(
        f'http://{ip}:{port}/fetch-file?filename={filename}').json()

    if ('content' in resp) and ('name' in resp) and (resp['name'] == filename):
        # File successfully opened

        print(resp)
        
        # only do this once
        crdt_file[filename] = Doc()
        crdt_file[filename].site = MY_USERID
        file_cursors[filename] = 0

        rabbitmq_listeners[filename] = Process(
            target=rabbitmq_listen, args=(filename, MY_PORT, ))
        rabbitmq_listeners[filename].start()

        create_CRDT_Embeddings(resp['content'], crdt_file[filename])

        params = {
            "file_id": str(filename),
            "user_id": MY_USERID,
            "ip": MY_IP,
            "port": MY_PORT
        }
        requests.post(FILE_TRACKER + '/opened/', data=params)

        resp["status"] = "success"
        return resp

    else:
        return {"status": "Failed to fetch file from the user specified by file tracker."}


@app.route('/close-file')
async def close_file():
    filename = request.args.get('filename')
    params = {
        "file_id": str(filename),
        "user_id": MY_USERID,
        "ip": MY_IP,
        "port": MY_PORT
    }
    print("closing ...")
    response = requests.post(FILE_TRACKER + '/close/', data=params)
    print("close_file", response.json())

    rabbitmq_listeners[filename].terminate()
    
    return response.json()


@app.route('/fetch-file')  # reload file from disk/mem
def fetch_file():
    filename = request.args.get('filename')

    contents = crdt_file[filename].text
    resp = {
        "name": str(filename),
        "content": contents,
        "cursor": file_cursors[filename]
    }
    print("fetch_file", resp)
    return resp


def move_cursor(filename, key):
    if key == 'ArrowRight':
        file_cursors[filename] = file_cursors[filename] + 1
    elif key == 'ArrowLeft':
        file_cursors[filename] = max(0, file_cursors[filename] - 1)
    elif key == 'ArrowUp':
        pass  # TODO
    elif key == 'ArrowDown':
        pass  # TODO


@app.post('/patch-from-rabbitmq')
def receive_patch():
    patch = request.get_json()
    if patch['id'] == MY_USERID:
        return 'success'
    crdt_file[patch['filename']].apply_patch((patch['patch']))
    return 'success'


def send_patch(filename, patch):
    # send this patch to rabbitmq
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    msg = {
        "filename": filename,
        "patch": patch,
        "id": MY_USERID,
    }
    print(msg)
    channel.basic_publish(
        exchange=filename, routing_key='', body=json.dumps(msg))


def insert_char(filename, key):
    insert_patch = crdt_file[filename].insert(file_cursors[filename], key)
    file_cursors[filename] += 1
    open(WORKDIR + str(filename), "w").write(crdt_file[filename].text)

    send_patch(filename, insert_patch)


def delete_char(filename):
    if file_cursors[filename] == 0:
        # first index of file
        return

    delete_patch = crdt_file[filename].delete(file_cursors[filename] - 1)
    file_cursors[filename] -= 1
    open(WORKDIR + str(filename), "w").write(crdt_file[filename].text)

    send_patch(filename, delete_patch)


@app.route('/key-press')
async def key_press():
    filename = request.args.get('filename')
    key = request.args.get('key')
    if key == 'ArrowRight' or key == 'ArrowLeft' or key == 'ArrowUp' or key == 'ArrowDown':
        move_cursor(filename, key)
    elif key == 'Enter':
        insert_char(filename, '\n')
    elif key == 'Space':
        insert_char(filename, ' ')
    elif len(key) == 1:
        insert_char(filename, key)
    elif key == 'Backspace':
        delete_char(filename)
    return fetch_file()

if __name__ == "__main__":
    # uvicorn.run("main:app", port=int(sys.argv[1]),
    #             reload=True, debug=True, workers=3)
    app.run(debug=True, port='4000')
