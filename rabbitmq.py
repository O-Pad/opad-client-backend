#!/usr/bin/env python
import pika
from multiprocessing import Process
import requests
import json


def rabbitmq_listen(exchange, PORT):

    def callback(ch, method, properties, body):
        BACKEND_URL = "http://localhost:" + str(PORT) + "/"
        # get/post opad - backend with parameter body
        print(" [x] %r" % body)
        msg = json.loads(body)
        print(msg)
        filename = msg["filename"]
        patch = json.dumps(msg["patch"])
        requests.get(BACKEND_URL + f"patch-from-rabbitmq?filename={filename}&patch={patch}")

    print("listening on exchange: %s" % exchange)
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host='localhost'))
    channel = connection.channel()

    channel.exchange_declare(exchange=exchange, exchange_type='fanout')

    result = channel.queue_declare(queue='', exclusive=True)
    queue_name = result.method.queue

    channel.queue_bind(exchange=exchange, queue=queue_name)

    print(' [*] Waiting for logs. To exit press CTRL+C')
    channel.basic_consume(
        queue=queue_name, on_message_callback=callback, auto_ack=True)

    channel.start_consuming()


if __name__ == '__main__':
    p = Process(target=rabbitmq_listen, args=('logs',))
    p.start()
    p.join()
    print('done')
