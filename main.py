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
import pickle
import codecs
from dotenv import load_dotenv
import os
load_dotenv(dotenv_path=".env")


app = Flask(__name__)

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# must configure these
FILE_TRACKER = f'http://{os.getenv("FILE_TRACKER_IP")}'
RABBITMQ_HOST = os.getenv('RABBITMQ_HOST')

# set to private ip if collaborating over LAN
MY_IP = os.getenv('MY_IP')
MY_PORT = os.getenv('MY_PORT')

WORKDIR = 'workdir/'
MY_USERID = os.getenv('MY_USERID')
######################
file_cursors = {
    # 'hello': 0,
    # 'file2': 0
}

crdt_file = {
    # 'hello': Doc(),
    # 'file2': Doc()
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
def root():
    return {
        "message": "Backend is running ...",
        "IP": MY_IP,
        "Port": MY_PORT,
        "UserID": MY_USERID,
        "FileTrackerPath": FILE_TRACKER,
        "RabbitMQ Host": RABBITMQ_HOST,
        "WorkDirPath": WORKDIR
    }


@app.route('/get-file-list')
def get_file_list():
    return {
        "open_files": list(crdt_file.keys()),
    }


@app.route('/create-file', methods=['POST'])
def create_file():
    filename = request.args.get('filename')
    content = request.get_data().decode('utf-8')
    print(filename)
    print(content)

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
    if(content):
        create_CRDT_Embeddings(content, crdt_file[filename])
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
def open_file():
    filename = request.args.get('filename')
    response = requests.get(FILE_TRACKER + '/open/?file_id=' + str(filename))
    resp = response.json()
    print("open_file", resp)

    # if no user under file tracker having the file
    if 'ip' in resp:
        pass
    else:
        return {"status": "File doesn't exist or no user to serve the file."}

    ip = resp['ip']
    port = resp['port']
    
    # if found such user, attempt requesting the file
    try: 
        resp = requests.get(
        f'http://{ip}:{port}/fetch-crdt?filename={filename}', timeout=2).json()
    except requests.exceptions.Timeout as e: 
        print(e)
        return {"status": "Failed to fetch file from the user specified by file tracker."}

    if ('crdt' in resp) and ('name' in resp) and (resp['name'] == filename):
        # File successfully opened

        print(resp)

        # only do this once
        crdt = pickle.loads(codecs.decode(resp['crdt'].encode(), "base64"))
        crdt_file[filename] = crdt
        crdt_file[filename].site = MY_USERID
        file_cursors[filename] = 0

        rabbitmq_listeners[filename] = Process(
            target=rabbitmq_listen, args=(filename, ))
        rabbitmq_listeners[filename].start()

        params = {
            "file_id": str(filename),
            "user_id": MY_USERID,
            "ip": MY_IP,
            "port": MY_PORT
        }
        requests.post(FILE_TRACKER + '/opened/', data=params)

        new_resp = {
            "status": "success",
            "content": crdt.text,
            "filename": filename,
            "cursor": file_cursors[filename]
        }

        return new_resp

    else:
        return {"status": "Failed to fetch file from the user specified by file tracker."}


@app.route('/close-file')
def close_file():
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

    file_cursors.pop(filename)
    crdt_file.pop(filename)

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


@app.route('/fetch-crdt')  # send crdt
def fetch_crdt():
    filename = request.args.get('filename')

    # contents = pickle.dumps(crdt_file[filename])
    crdt = codecs.encode(pickle.dumps(crdt_file[filename]), "base64").decode()

    resp = {
        "name": str(filename),
        "crdt": crdt
    }
    print("fetch_crdt", resp)
    return resp


def move_cursor(filename, key):
    if key == 'ArrowRight':
        file_cursors[filename] = min(
            len(crdt_file[filename].text), file_cursors[filename] + 1)
    elif key == 'ArrowLeft':
        file_cursors[filename] = max(0, file_cursors[filename] - 1)
    elif key == 'ArrowUp':
        # previous line break
        prev_newLine = crdt_file[filename].text[::-1].find(
            '\n', len(crdt_file[filename].text) - file_cursors[filename])
        if prev_newLine < 0:
            return
        else:
            prev_newLine = len(crdt_file[filename].text) - prev_newLine - 1

        # previous previous line break
        prev_prev_newLine = crdt_file[filename].text[::-1].find(
            '\n', len(crdt_file[filename].text) - prev_newLine)
        if prev_prev_newLine < 0:
            prev_prev_newLine = -1
        else:
            prev_prev_newLine = len(
                crdt_file[filename].text) - prev_prev_newLine - 1

        file_cursors[filename] = prev_prev_newLine + \
            (file_cursors[filename] - prev_newLine)

    elif key == 'ArrowDown':
        # next line break
        next_newLine = crdt_file[filename].text.find(
            '\n', file_cursors[filename])
        if next_newLine < 0:
            return

        # previous line break
        prev_newLine = crdt_file[filename].text[::-1].find(
            '\n', len(crdt_file[filename].text) - file_cursors[filename])
        if prev_newLine < 0:
            prev_newLine = -1
        else:
            prev_newLine = len(crdt_file[filename].text) - prev_newLine - 1

        file_cursors[filename] = next_newLine + \
            (file_cursors[filename] - prev_newLine)
        file_cursors[filename] = min(
            len(crdt_file[filename].text), file_cursors[filename])


@app.route('/patch-from-rabbitmq', methods=['POST'])
def receive_patch():
    patch = request.get_json()
    if patch['id'] == MY_USERID:
        return 'success'

    orig_file = crdt_file[patch['filename']].text
    crdt_file[patch['filename']].apply_patch((patch['patch']))
    new_file = crdt_file[patch['filename']].text

    if json.loads(patch['patch'])['op'] == "i":
        pos = 0
        while pos < len(orig_file):
            if orig_file[pos] != new_file[pos]:
                break
            pos += 1
        if pos < len(orig_file) and pos < file_cursors[patch['filename']]:
            file_cursors[patch['filename']] += 1

    else:
        pos = 0
        while pos < len(orig_file):
            if orig_file[pos] != new_file[pos]:
                break
            pos += 1
        if pos < len(orig_file) and pos < file_cursors[patch['filename']]:
            file_cursors[patch['filename']] -= 1

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
def key_press():
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
    app.run(debug=True, host='0.0.0.0', port='4000')
