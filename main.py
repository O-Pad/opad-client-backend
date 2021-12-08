import requests
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mahitahi.mahitahi import Doc
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
file_cursors = {
    'hello': 0,
    'file2': 0
}

crdt_file = {
    'hello': Doc(),
    'file2': Doc()
}

def create_CRDT_Embeddings(content, doc_file):
    # create logoot/CRDT embeddings
    pos = 0
    for line in content:
        # add embedding
        for c in line:
            doc_file.insert(pos, c)
            pos += 1
        
        doc_file.insert(pos, '\n')
        pos += 1

create_CRDT_Embeddings( open(WORKDIR + 'hello', "r").read(), crdt_file['hello'] )


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
        # File successfully opened

        crdt_file[filename].site = MY_USERID

        create_CRDT_Embeddings(resp['content'], crdt_file[filename])

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
    # contents = list(map(lambda line: line[:-1] if line[-1] == '\n' else line, open(WORKDIR + str(filename), "r").readlines()))
    # print("fetch_file", filename)
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
        file_cursors[filename] += max(0, file_cursors[filename] - 1)
    elif key == 'ArrowUp':
        pass # TODO
    elif key == 'ArrowDown':
        pass # TODO

def insert_char(filename, key):
    crdt_file[filename].insert(file_cursors[filename], key)
    file_cursors[filename] += 1

def delete_char(filename, key):
    if file_cursors[filename] == 0:
        # first index of file
        return

    crdt_file[filename].delete(file_cursors[filename] - 1)
    file_cursors[filename] -= 1

@app.get('/key-press')
async def key_press(filename, key):
    if key == 'ArrowRight' or key == 'ArrowLeft' or key == 'ArrowUp' or key == 'ArrowDown':
        move_cursor(filename, key)
    elif key == 'Enter':
        insert_char('\n')
    elif len(key) == 1:
        insert_char(key)
    elif key == 'Backspace':
        delete_char()
    return fetch_file(filename)

# @app.get('/add-char')
# async def add_char(filename, line, pos, key):
#     line = int(line)
#     pos = int(pos)
#     contents = list(map(lambda line: line[:-1] if line[-1] == '\n' else line, open(WORKDIR + str(filename), "r").readlines()))
#     ln = contents[line]
#     contents[line] = ln[:pos] + key + ln[pos:]
#     resp = {
#         "name": str(filename),
#         "content": contents
#     }
#     open(WORKDIR + str(filename), "w").writelines(list(map(lambda line: line + '\n', contents)))
    
#     # update CRDT embedding
#     cur_index = 0
#     for i in range(line):
#         cur_index += character_counter[filename][i]
    
#     cur_index += pos
#     print(cur_index)

#     add_msg = crdt_file[filename].insert(cur_index, key)
#     character_counter[filename][line] += 1

#     # send add_msg to rabbitMQ
#     print(add_msg)
#     print(crdt_file[filename].text)

#     return resp

# @app.get('/delete-char')
# async def delete_char(filename, line, pos):
#     line = int(line)
#     pos = int(pos)
#     contents = list(map(lambda line: line[:-1] if line[-1] == '\n' else line, open(WORKDIR + str(filename), "r").readlines()))
#     ln = contents[line]
#     contents[line] = ln[:pos] + ln[pos + 1:]
#     resp = {
#         "name": str(filename),
#         "content": contents
#     }
#     open(WORKDIR + str(filename), "w").writelines(list(map(lambda line: line + '\n', contents)))
    
#     # update CRDT embedding
#     cur_index = 0
#     for i in range(line):
#         cur_index += character_counter[filename][i]
    
#     cur_index += pos

#     add_msg = crdt_file[filename].delete(cur_index)
#     character_counter[filename][line] -= 1

#     # send add_msg to rabbitMQ
#     print(add_msg)
#     print(crdt_file[filename].text)
    
#     return resp

# @app.get('/add-line')
# async def add_line(filename, line):
#     line = int(line)
#     contents = list(map(lambda line: line[:-1] if line[-1] == '\n' else line, open(WORKDIR + str(filename), "r").readlines()))
#     contents = contents[:line] + [""] + contents[line:]
    
#     resp = {
#         "name": str(filename),
#         "content": contents
#     }
#     open(WORKDIR + str(filename), "w").writelines(list(map(lambda line: line + '\n', contents)))
    

    
#     return resp

# @app.get('/delete-line')
# async def delete_line(filename, line):
#     line = int(line)
#     contents = list(map(lambda line: line[:-1] if line[-1] == '\n' else line, open(WORKDIR + str(filename), "r").readlines()))
#     contents = contents[:line] + contents[line+1:]
#     resp = {
#         "name": str(filename),
#         "content": contents
#     }
#     open(WORKDIR + str(filename), "w").writelines(list(map(lambda line: line + '\n', contents)))
#     return resp

# TODO: Get updates from RabbitMQ and make appropriate changes to the local file.

if __name__ == "__main__":
    uvicorn.run("main:app", host=MY_IP, port=MY_PORT,
                reload=True, debug=True, workers=3)
