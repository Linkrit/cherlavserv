from flask import Flask, request, jsonify, g, render_template, redirect, url_for
from datetime import datetime
import pymysql
import pymysql.cursors
import pika

app = Flask(__name__)

# Конфигурация базы данных Yandex.Cloud
DB_CONFIG = {
    'host': 'rc1d-5p5ijl6q1jt8j26g.mdb.yandexcloud.net',  # удаленный хост БД
    'user': 'user1',  # имя пользователя БД
    'password': 'adminadmin',  # пароль
    'db': 'restaurant_delivery',
    'charset': 'utf8mb4',
    'cursorclass': pymysql.cursors.DictCursor,
    'port': 3306,
}

def get_db():
    """Получаем активное подключение к БД"""
    if 'db' not in g:
        g.db = pymysql.connect(**DB_CONFIG)
    return g.db

@app.teardown_appcontext
def close_db(error):
    """Закрываем соединение с базой после запроса"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def send_message(queue_name, message):
    connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))  # Если RabbitMQ на той же машине
    # Или используйте IP-адрес, если RabbitMQ на другой машине
    channel = connection.channel()
    channel.queue_declare(queue=queue_name)
    channel.basic_publish(exchange='', routing_key=queue_name, body=message)
    connection.close()

@app.route("/", methods=['GET', 'POST'])
def index():
        return render_template('base.html')


@app.route('/users', methods=['GET'])
def users():
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM Users")
            users = cursor.fetchall()
            return render_template('users.html', users=users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/users_add', methods=['POST'])
def users_add():
    try:
        name = request.form['user-name']
        phone = request.form['user-phone']
        address = request.form['user-address']
        # Отправляем в очередь для асинхронной обработки
        send_message('user_queue', f"{name},{phone},{address}")
        return redirect(url_for('users'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/restaurants', methods=['GET'])
def restaurants():
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM Restaurants")
            restaurants = cursor.fetchall()
            return render_template('restaurants.html', restaurants=restaurants)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/restaurants/menu', methods=['GET'])
def get_restaurants():
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT idRestaurants, name FROM Restaurants")
            restaurant_menus = cursor.fetchall()
            return render_template('menu_restaurant.html', restaurant_menus=restaurant_menus)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/restaurants/menu/<int:restaurant_id>', methods=['GET'])
def menu(restaurant_id):
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute(
                "SELECT idFoods, name, price FROM Foods WHERE Restaurants_idRestaurants = %s",
                (restaurant_id,)
            )
            restaurant_food = cursor.fetchall()
            return render_template('menu_partial.html', restaurant_food=restaurant_food)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/view_orders', methods=['GET'])
def view_orders():
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute("""SELECT o.idOrders, o.order_date, o.status, u.name AS user_name
                              FROM Orders o
                              INNER JOIN Users u ON o.Users_idUsers = u.idUsers
                              WHERE o.status NOT IN ('completed', 'cancelled')""")
            orders = cursor.fetchall()
            cursor.execute("SELECT idUsers, name FROM Users")
            users = cursor.fetchall()
            return render_template('orders.html', orders=orders, users=users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/orders/change_status', methods=['POST'])
def update_order_status():
    try:
        order_id = request.form['order-id']
        new_status = request.form['order-status']
        send_message('status_queue', f"{order_id},{new_status}")
        return redirect(url_for('view_orders'))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/create_order', methods=['GET'])
def create_order_page():
    db = get_db()
    try:
        with db.cursor() as cursor:
            cursor.execute("SELECT * FROM Users")
            clients = cursor.fetchall()
            cursor.execute("SELECT * FROM Foods")
            foods = cursor.fetchall()
            return render_template('create_order.html', clients=clients, foods=foods)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/create_order', methods=['POST'])
def create_order():
    db = get_db()
    try:
        data = request.form
        food_positions = []
        for key, value in data.items():
            if value != '0' and key.startswith('quantity_food'):
                position_id = int(key[13:])
                food_positions.append((position_id, int(value)))

        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO Orders (order_date, status, Users_idUsers) VALUES (%s, %s, %s)",
                (datetime.now().strftime('%Y-%m-%d'), 'pending', data['order-user'])
            )
            order_id = cursor.lastrowid

            for position_id, quantity in food_positions:
                cursor.execute(
                    "INSERT INTO OrderItems (quantity, Orders_idOrders, Foods_idFoods) VALUES (%s, %s, %s)",
                    (quantity, order_id, position_id)
                )
            db.commit()

            send_message('order_queue', f"Order created: {order_id}")

        return redirect(url_for('create_order_page'))
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

