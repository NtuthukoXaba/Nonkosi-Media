from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

# --- App setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///maskandi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- Database and LoginManager ---
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'  # redirect to 'login' if @login_required fails

# --- User Loader for Flask-Login ---
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Models ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # 'admin', 'journalist', 'user'
    profile_pic = db.Column(db.String(20), nullable=False, default='default.jpg')
    news_articles = db.relationship('News', backref='author', lazy=True)

def create_admin():
    admin_exists = User.query.filter_by(username='admin').first()
    if not admin_exists:
        hashed_password = generate_password_hash('admin123', method='pbkdf2:sha256')
        admin = User(
            username='admin',
            email='admin@maskandi.com',
            password=hashed_password,
            role='admin',
            profile_pic='admin.jpg'
        )
        db.session.add(admin)
        db.session.commit()
        print("Admin user created successfully!")
    else:
        print("Admin user already exists")

class Artist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    bio = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(20), nullable=False, default='artist_default.jpg')
    social_media = db.Column(db.JSON)
    songs = db.relationship('Song', backref='artist', lazy=True)
    gigs = db.relationship('Gig', backref='artist', lazy=True)

class Song(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    genre = db.Column(db.String(50), nullable=False)
    release_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    cover_image = db.Column(db.String(20), nullable=False)
    spotify_link = db.Column(db.String(200))
    youtube_link = db.Column(db.String(200))
    artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'), nullable=False)
    chart_position = db.Column(db.Integer)

class News(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    image = db.Column(db.String(20), nullable=False)
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

class Gig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    venue = db.Column(db.String(200), nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    city = db.Column(db.String(100), nullable=False)
    artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'), nullable=False)

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    month_year = db.Column(db.String(20), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    winner_id = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=False)

class ContactMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    date_sent = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

# --- Routes ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/admin')
@login_required
def admin_home():
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    return render_template('admin_home.html')

@app.route('/journalist')
@login_required
def journalist_home():
    if current_user.role != 'journalist':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    return render_template('journalist_home.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_home'))
            elif user.role == 'journalist':
                return redirect(url_for('journalist_home'))
            else:
                return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'error')
    return render_template('Login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- DB init ---
def create_database():
    with app.app_context():
        db.create_all()
        create_admin()
        print("Database initialized successfully!")

if __name__ == '__main__':
    create_database()
    app.run(debug=True)