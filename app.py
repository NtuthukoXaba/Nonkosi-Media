from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

# --- App setup ---
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///maskandi.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads/profile_pics'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# --- Database and LoginManager ---
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Models ---
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    profile_pic = db.Column(db.String(100), nullable=False, default='default.jpg')
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    news_articles = db.relationship('News', backref='author', lazy=True)

    def update_last_seen(self):
        self.last_seen = datetime.utcnow()
        db.session.commit()

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

# --- Add these routes to your existing app.py ---

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# --- Journalist Management Routes ---
@app.route('/admin/manage_journalists')
@login_required
def manage_journalists():
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    # Default to page 1 if not specified
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Number of journalists per page
    
    # Get paginated journalists
    journalists = User.query.filter(User.role.in_(['journalist', 'senior_journalist', 'junior_journalist']))\
                          .order_by(User.username)\
                          .paginate(page=page, per_page=per_page, error_out=False)
    
    return render_template('manage_journalists.html', 
                         journalists=journalists.items,
                         page=page,
                         total_pages=journalists.pages)

@app.route('/admin/add_journalist', methods=['POST'])
@login_required
def add_journalist():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    username = request.form.get('username')
    email = request.form.get('email')
    role = request.form.get('role')
    password = request.form.get('password')
    
    # Validation
    if not all([username, email, role, password]):
        return jsonify({'success': False, 'message': 'All fields are required'}), 400
    
    if User.query.filter((User.username == username) | (User.email == email)).first():
        return jsonify({'success': False, 'message': 'Username or email already exists'}), 400
    
    try:
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_journalist = User(
            username=username,
            email=email,
            password=hashed_password,
            role=role
        )
        
        # Handle file upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{username}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                new_journalist.profile_pic = filename
        
        db.session.add(new_journalist)
        db.session.commit()
        flash('Journalist added successfully', 'success')
        return jsonify({'success': True, 'redirect': url_for('manage_journalists')})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/edit_journalist/<int:journalist_id>', methods=['POST'])
@login_required
def edit_journalist(journalist_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    journalist = User.query.get_or_404(journalist_id)
    username = request.form.get('username')
    email = request.form.get('email')
    role = request.form.get('role')
    
    # Validation
    if not all([username, email, role]):
        return jsonify({'success': False, 'message': 'All fields are required'}), 400
    
    if User.query.filter(User.id != journalist_id, 
                       (User.username == username) | (User.email == email)).first():
        return jsonify({'success': False, 'message': 'Username or email already exists'}), 400
    
    try:
        journalist.username = username
        journalist.email = email
        journalist.role = role
        
        # Handle file upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"{username}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                journalist.profile_pic = filename
        
        db.session.commit()
        flash('Journalist updated successfully', 'success')
        return jsonify({'success': True, 'redirect': url_for('manage_journalists')})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/delete_journalist/<int:journalist_id>', methods=['DELETE'])
@login_required
def delete_journalist(journalist_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    journalist = User.query.get_or_404(journalist_id)
    
    try:
        db.session.delete(journalist)
        db.session.commit()
        flash('Journalist deleted successfully', 'success')
        return jsonify({'success': True, 'redirect': url_for('manage_journalists')})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# --- DB init ---
def create_database():
    with app.app_context():
        db.create_all()
        create_admin()
        print("Database initialized successfully!")

if __name__ == '__main__':
    create_database()
    app.run(debug=True)