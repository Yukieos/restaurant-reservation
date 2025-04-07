import os
  # accessible as a variable in index.html:
from sqlalchemy import *
from sqlalchemy.pool import NullPool
from flask import flash, Flask, request, render_template, g, redirect, Response, session, url_for
from datetime import datetime

tmpl_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
app = Flask(__name__, template_folder=tmpl_dir)
app.secret_key = 'wanting-is-the-best-123'



#
# The following is a dummy URI that does not connect to a valid database. You will need to modify it to connect to your Part 2 database in order to use the data.
#
# XXX: The URI should be in the format of: 
#
#     postgresql://USER:PASSWORD@34.148.223.31/proj1part2
#
# For example, if you had username zy2431 and password 123123, then the following line would be:
#
#     DATABASEURI = "postgresql://zy2431:123123@34.148.223.31/proj1part2"
#
# Modify these with your own credentials you received from TA!
DATABASE_USERNAME = "wy2470"
DATABASE_PASSWRD = "342930"
DATABASE_HOST = "34.148.223.31"
DATABASEURI = f"postgresql://wy2470:342930@34.148.223.31/proj1part2"


#
# This line creates a database engine that knows how to connect to the URI above.
#
engine = create_engine(DATABASEURI)

#
# Example of running queries in your database
# Note that this will probably not work if you already have a table named 'test' in your database, containing meaningful data. This is only an example showing you how to run queries in your database using SQLAlchemy.
#

@app.before_request
def connect_db():
	"""
	This function is run at the beginning of every web request 
	(every time you enter an address in the web browser).
	We use it to setup a database connection that can be used throughout the request.

	The variable g is globally accessible.
	"""
	try:
		g.conn = engine.connect()
	except:
		print("uh oh, problem connecting to database")
		import traceback; traceback.print_exc()
		g.conn = None

@app.teardown_request
def close_db(exception):
	"""
	At the end of the web request, this makes sure to close the database connection.
	If you don't, the database could run out of memory!
	"""
	try:
		g.conn.close()
	except Exception as e:
		pass
@app.before_request
def load_user():
	user_id = session.get('User_ID')
	g.user = None
	if user_id is not None and g.conn:
		g.user = g.conn.execute(
			'SELECT * FROM Users WHERE User_ID = :uid', {'uid': user_id}
		).fetchone()


#
# @app.route is a decorator around index() that means:
#   run index() whenever the user tries to access the "/" path using a GET request
#
# If you wanted the user to go to, for example, localhost:8111/foobar/ with POST or GET then you could use:
#
#       @app.route("/foobar/", methods=["POST", "GET"])
#
# PROTIP: (the trailing / in the path is important)
# 
# see for routing: https://flask.palletsprojects.com/en/1.1.x/quickstart/#routing
# see for decorators: http://simeonfranklin.com/blog/2012/jul/1/python-decorators-in-12-steps/
#


@app.route('/')
def home():
	return render_template('home.html',logged_in = 'User_ID' in session)
@app.route('/restaurants')
def restaurants():
	with engine.connect() as conn:
		query = """SELECT r.Restaurant_ID, r.Restaurant_name, r.Price_range, AVG(rev.Rating) as avg_rating
		From Restaurant r
		LEFT JOIN Review rev ON r.Restaurant_ID = rev.Restaurant_ID
		GROUP BY r.Restaurant_ID
		"""
		restaurants = []
		for row in conn.execute(text(query)):
			restaurants.append(dict(row._mapping))
		menu_query = "SELECT * FROM Menu"
		menus = {}
		for n in conn.execute(text(menu_query)):
			id = n._mapping['restaurant_id']
			if id not in menus:
				menus[id] = []
			menus[id].append(dict(n._mapping))
		rating_query = "SELECT * FROM Review"
		ratings = {}
		for n in conn.execute(text(rating_query)):
			id = n._mapping['restaurant_id']
			if id not in ratings:
				ratings[id] = []
			ratings[id].append(dict(n._mapping))
	return render_template('restaurants.html', restaurants = restaurants, menus = menus, ratings = ratings)

@app.route('/restaurant/<int:restaurant_id>')
def restaurant_detail(restaurant_id):
    """餐厅详情页（包含菜单、评论）"""
    try:
        with engine.connect() as conn:
            # 获取餐厅基本信息
            restaurant = conn.execute(
                text("""
                SELECT r.*, AVG(rev.rating) as avg_rating, COUNT(rev.review_id) as review_count
                FROM Restaurant r
                LEFT JOIN Review rev ON r.Restaurant_ID = rev.Restaurant_ID
                WHERE r.Restaurant_ID = :rid
                GROUP BY r.Restaurant_ID
                """),
                {'rid': restaurant_id}
            ).mappings().fetchone()

            # 获取完整菜单
            menu_items = conn.execute(
                text("SELECT * FROM menu WHERE restaurant_id = :rid"),
                {'rid': restaurant_id}
            ).mappings().fetchall()

            # 获取最新评论
            reviews = conn.execute(
                text("""
                SELECT rev.*, u.first_name, u.last_name
                FROM review rev
                JOIN users u ON rev.user_id = u.user_id
                WHERE rev.restaurant_id = :rid
                """),
                {'rid': restaurant_id}
            ).mappings().fetchall()

        return render_template('restaurant_detail.html',restaurant=dict(restaurant), menu=menu_items,reviews=reviews
        )
    except Exception as e:
        app.logger.error(f"Restaurant detail error: {str(e)}")
        return "Error loading restaurant details", 500
	
@app.route('/reservation_form', methods=['GET', 'POST'])
def reservation_form():
	if request.method == 'POST':
		try:
			with engine.connect() as conn:
				query = """INSERT INTO Reservation(User_ID, Restaurant_ID, Party_size, Time, Date, Special_event)
				VALUES(:user_id, :restaurant_id, :party_size, :time, :date, :special_event)
				"""
				conn.execute(text(query), 
				 {'user_id':request.form['user_id'], 
				 'restaurant_id':request.form['restaurant_id'],
				 'party_size':request.form['party_size'],
				 'time':request.form['time'],
				 'date':request.form['date'],
				 'special_event':request.form['special_event']
				 })
				conn.commit()
			return redirect(url_for('my_reservations'))
		except Exception as e:
			return f"Error: {str(e)}", 500
	with engine.connect() as conn:
		restaurants = conn.execute(text("SELECT * FROM Restaurant")).fetchall()
	return render_template('reservation_form.html', restaurants = restaurants, min_date = datetime.today().strftime('%Y-%m-%d'))
@app.route('/my-reservations')
def my_reservations():
	if 'user_id' not in session:
		return redirect(url_for('login'))
	with engine.connect() as conn:
		query = text("""SELECT resv.*, r.Restaurant_name 
		FROM Reservation resv
		JOIN Restaurant r ON resv.Restaurant_ID = r.Restaurant_ID
		WHERE resv.User_ID = :user_id
		""")
		reservations = conn.execute(query, {'user_id': session['user_id']}).fetchall()
	return render_template('my_reservations.html',reservations=reservations)
@app.route('/login', methods= ['GET', 'POST'])
def login():
	if request.method == 'POST':
		Phone_Number = request.form['Phone_Number']
		Last_Name = request.form['Last_Name']
		error = None
		with engine.connect() as conn:
			query = """SELECT user_id FROM users 
			WHERE Phone_Number = :Phone_Number AND Last_Name = :Last_Name
			"""
			user = conn.execute(text(query),{'Phone_Number': Phone_Number, 'Last_Name': Last_Name}).mappings().fetchone()
			if not user:
				error = 'Invalid information'
			if error:
				flash(error)
			else:
				session.clear()
				session['user_id'] = user['user_id']
				session.permanent = True
				return redirect(url_for('dashboard'))
				
	return render_template('login.html')
@app.route('/logout')
def logout():
	session.clear()
	return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
	if 'user_id' not in session:
		return redirect(url_for('login'))
	return render_template('dashboard.html')

@app.route('/profile')
def profile():
	if 'user_ID' not in session:
		return redirect(url_for('login'))
	query = "SELECT * FROM Users WHERE User_ID = :User_ID"
	query2 = "SELECT * FROM Card WHERE User_ID = :User_ID"
	with engine.connect() as conn:
		user = conn.execute(text(query), {'user_id': session ['user_id']}).mappings.fetchone()
		card = conn.execute(text(query2), {'user_id': session ['user_id']}).mappings.fetchone()
	return render_template('user_profile.html', user = dict(user), card = dict(card))

if __name__ == "__main__":
	import click

	@click.command()
	@click.option('--debug', is_flag=True)
	@click.option('--threaded', is_flag=True)
	@click.argument('HOST', default='0.0.0.0')
	@click.argument('PORT', default=8111, type=int)
	def run(debug, threaded, host, port):
		"""
		This function handles command line parameters.
		Run the server using:

			python server.py

		Show the help text using:

			python server.py --help

		"""
		HOST, PORT = host, port
		print("running on %s:%d" % (HOST, PORT))
		app.run(host=HOST, port=PORT, debug=debug, threaded=threaded)

run()
