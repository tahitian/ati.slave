import pika

class rabbitmq:
    def __init__(self, server, port, username, password, queuename):
        self.server = server
        self.port = port
        self.username = username
        self.password = password
        self.queuename = queuename
        self.connection = None
        self.channel = None

    def connect(self):
        credentials = pika.PlainCredentials(self.username, self.password)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.server, self.port, "/", credentials))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue = self.queuename)

    def send_message(self, message):
        done = False
        retry = 0
        while not done and retry < 3:
            try:
                self.channel.basic_publish(
                    exchange = "",
                    routing_key = self.queuename,
                    body = message,
                    properties = pika.BasicProperties(delivery_mode = 2)
                )
                done = True
            except Exception, e:
                if not self.connection.is_open:
                    self.connect()
            retry += 1
        return done

    def receive_message(self):
        message = None
        retry = 0
        while not message and retry < 3:
            try:
                method_frame, header_frame, body = self.channel.basic_get(self.queuename)
                if not method_frame:
                    break
                message = body
                self.channel.basic_ack(delivery_tag = method_frame.delivery_tag)
            except Exception, e:
                if not self.connection.is_open:
                    self.connect()
            retry += 1
        return message

    def disconnect(self):
        self.connection.close()
