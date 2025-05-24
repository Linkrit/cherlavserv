import pika
import pymysql

DB_CONFIG = {
    'host': 'rc1d-5p5ijl6q1jt8j26g.mdb.yandexcloud.net',
    'user': 'user1',
    'password': 'adminadmin',
    'db': 'restaurant_delivery',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'port': 3306
}

def callback_user(ch, method, properties, body):
    print(f"Received user data: {body.decode()}")
    try:
        name, phone, address = body.decode().split(',')
    except Exception as e:
        print(f"Error parsing user data: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    db = pymysql.connect(**DB_CONFIG)
    try:
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Users (name, phone, address) VALUES (%s, %s, %s)",
                (name, phone, address)
            )
            db.commit()
            print("User added to database.")
    except Exception as e:
        print(f"DB error: {e}")
    finally:
        db.close()
    ch.basic_ack(delivery_tag=method.delivery_tag)

def callback_status(ch, method, properties, body):
    print(f"Received status update: {body.decode()}")
    try:
        order_id, new_status = body.decode().split(',')
    except Exception as e:
        print(f"Error parsing status update: {e}")
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    db = pymysql.connect(**DB_CONFIG)
    try:
        with db.cursor() as cursor:
            cursor.execute(
                "UPDATE Orders SET status = %s WHERE idOrders = %s",
                (new_status, order_id)
            )
            db.commit()
            print("Order status updated in database.")
    except Exception as e:
        print(f"DB error: {e}")
    finally:
        db.close()
    ch.basic_ack(delivery_tag=method.delivery_tag)

def callback_order(ch, method, properties, body):
    print(f"Received order creation message: {body.decode()}")
    # Здесь можно добавить дополнительную логику обработки заказа, если нужно
    print("New order created.")
    ch.basic_ack(delivery_tag=method.delivery_tag)

def start_worker():
    print("Connecting to RabbitMQ...")
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))  # Измените, если RabbitMQ на другом хосте
    channel = connection.channel()
    print("Connected to RabbitMQ.")

    channel.queue_declare(queue='user_queue')
    channel.basic_consume(queue='user_queue', on_message_callback=callback_user, auto_ack=False)

    channel.queue_declare(queue='status_queue')
    channel.basic_consume(queue='status_queue', on_message_callback=callback_status, auto_ack=False)

    channel.queue_declare(queue='order_queue')
    channel.basic_consume(queue='order_queue', on_message_callback=callback_order, auto_ack=False)

    print('Waiting for messages. To exit press CTRL+C')
    channel.start_consuming()

if __name__ == "__main__":
    start_worker()
