from google.cloud.pubsub_v1 import PublisherClient
from google.cloud import storage
from pika import BasicProperties
from pika import BlockingConnection
from pika import URLParameters
from pika.exceptions import AMQPError
from structlog import get_logger

logger = get_logger()


class LogSubmitter():  # pylint: disable=no-self-use

    def send_message(self, message, queue, tx_id):  # pylint: disable=unused-argument
        logger.info('sending message')
        logger.info('message payload', message=message, queue=queue)
        return True


class PubSubSubmitter():  # pylint: disable=no-self-use

    def __init__(self, project_id, topic):
        self.publisher = PublisherClient()

        self.topic_path = 'projects/{project_id}/topics/{topic}'.format(
            project_id=project_id,
            topic=topic,
        )

    def send_message(self, message, queue, tx_id):  # pylint: disable=unused-argument
        logger.info('sending message')
        self.publisher.publish(self.topic_path, str(message).encode('utf8'))
        return True


class GCSSubmitter():  # pylint: disable=no-self-use

    def __init__(self, bucket_name):
        client = storage.Client()
        self.bucket = client.get_bucket(bucket_name)

    def send_message(self, message, queue, tx_id):  # pylint: disable=unused-argument
        logger.info('sending message')

        blob = self.bucket.blob(tx_id)
        blob.upload_from_string(str(message).encode('utf8'))
        return True


class RabbitMQSubmitter():
    def __init__(self, host, secondary_host, port, username=None, password=None):
        if username and password:
            self.rabbitmq_url = 'amqp://{username}:{password}@{host}:{port}/%2F'.format(username=username,
                                                                                        password=password,
                                                                                        host=host,
                                                                                        port=port)
            self.rabbitmq_secondary_url = 'amqp://{username}:{password}@{host}:{port}/%2F'.format(username=username,
                                                                                                  password=password,
                                                                                                  host=secondary_host,
                                                                                                  port=port)
        else:
            self.rabbitmq_url = 'amqp://{host}:{port}/%2F'.format(host=host, port=port)
            self.rabbitmq_secondary_url = 'amqp://{host}:{port}/%2F'.format(host=secondary_host, port=port)

    def _connect(self):
        try:
            logger.info('attempt to open connection', server='primary', category='rabbitmq')
            return BlockingConnection(URLParameters(self.rabbitmq_url))
        except AMQPError as e:
            logger.error('unable to open connection', exc_info=e, server='primary', category='rabbitmq')
            try:
                logger.info('attempt to open connection', server='secondary', category='rabbitmq')
                return BlockingConnection(URLParameters(self.rabbitmq_secondary_url))
            except AMQPError as err:
                logger.error('unable to open connection', exc_info=e, server='secondary', category='rabbitmq')
                raise err

    @staticmethod
    def _disconnect(connection):
        try:
            if connection:
                logger.info('attempt to close connection', category='rabbitmq')
                connection.close()
        except AMQPError as e:
            logger.error('unable to close connection', exc_info=e, category='rabbitmq')

    def send_message(self, message, queue, tx_id):
        """
        Sends a message to rabbit mq and returns a true or false depending on if it was successful
        :param message: The message to send to the rabbit mq queue
        :param queue: the name of the queue
        :return: a boolean value indicating if it was successful
        """
        message_as_string = str(message)
        logger.info('sending message', category='rabbitmq')
        logger.info('message payload', message=message_as_string, category='rabbitmq')
        connection = None
        try:
            connection = self._connect()
            channel = connection.channel()
            channel.queue_declare(queue=queue, durable=True)
            properties = BasicProperties(headers={},
                                         delivery_mode=2)

            if tx_id:
                properties.headers['tx_id'] = tx_id

            published = channel.basic_publish(exchange='',
                                              routing_key=queue,
                                              body=message_as_string,
                                              mandatory=True,
                                              properties=properties)
            if published:
                logger.info('sent message', category='rabbitmq')
            else:
                logger.error('unable to send message', category='rabbitmq')
            return published
        except AMQPError as e:
            logger.error('unable to send message', exc_info=e, category='rabbitmq')
            return False
        finally:
            if connection:
                self._disconnect(connection)
