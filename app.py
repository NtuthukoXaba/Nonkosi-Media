from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import UserMixin, LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
from flask import request

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

# --- Models ---
class VoteEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)  # e.g. "Song of the Month - June 2025"
    category = db.Column(db.String(50), nullable=False)  # 'song', 'artist', 'song_of_year', 'artist_of_year'
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    options = db.relationship('VoteOption', backref='vote_event', lazy=True, cascade='all, delete-orphan')
    votes = db.relationship('VoteRecord', backref='vote_event', lazy=True, cascade='all, delete-orphan')

class VoteOption(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vote_event_id = db.Column(db.Integer, db.ForeignKey('vote_event.id'), nullable=False)
    song_id = db.Column(db.Integer, db.ForeignKey('song.id'))  # For song-related votes
    artist_id = db.Column(db.Integer, db.ForeignKey('artist.id'))  # For artist-related votes
    vote_count = db.Column(db.Integer, default=0)
    
    # Relationships
    song = db.relationship('Song', backref='vote_options')
    artist = db.relationship('Artist', backref='vote_options')

class VoteRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vote_event_id = db.Column(db.Integer, db.ForeignKey('vote_event.id'), nullable=False)
    option_id = db.Column(db.Integer, db.ForeignKey('vote_option.id'), nullable=False)
    ip_address = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    option = db.relationship('VoteOption', backref='votes')

class VoteResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    vote_event_id = db.Column(db.Integer, db.ForeignKey('vote_event.id'), nullable=False)
    winner_id = db.Column(db.Integer, nullable=False)  # ID of winning song/artist
    winner_type = db.Column(db.String(10), nullable=False)  # 'song' or 'artist'
    votes_received = db.Column(db.Integer, nullable=False)
    date_announced = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    vote_event = db.relationship('VoteEvent', backref='results')

# ... (rest of your existing models and routes)

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
    articles = db.relationship('News', backref='author', lazy=True)  # This creates the relationship

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
    album = db.Column(db.String(100))  # New field - can be null for singles
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
    image = db.Column(db.String(100), nullable=False, default='default_news.jpg')
    date_posted = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    is_published = db.Column(db.Boolean, default=False)
    views = db.Column(db.Integer, default=0)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # REMOVE THIS LINE - it's the duplicate relationship causing the conflict
    # author = db.relationship('User', backref='news_articles')

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

@app.context_processor
def inject_datetime():
    return {'datetime': datetime}

# --- Routes ---
@app.route('/')
def home():
    # Get top 3 songs for the home page
    top_3 = Song.query.filter(Song.chart_position != None)\
                     .order_by(Song.chart_position)\
                     .limit(3)\
                     .all()
    
    return render_template('index.html', top_3=top_3)

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
    
@app.route('/admin/charts_manager')
@login_required
def charts_manager():
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    all_songs = Song.query.order_by(Song.title).all()
    top_songs = Song.query.filter(Song.chart_position != None)\
                        .order_by(Song.chart_position)\
                        .limit(20)\
                        .all()
    artists = Artist.query.order_by(Artist.name).all()
    
    return render_template('charts_manager.html', 
                         all_songs=all_songs,
                         top_songs=top_songs,
                         artists=artists)

@app.route('/admin/update_charts', methods=['POST'])
@login_required
def update_charts():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        # Clear all current chart positions
        db.session.query(Song).update({Song.chart_position: None})
        
        # Update with new positions from the request
        chart_data = request.get_json()
        for item in chart_data:
            song = Song.query.get(item['song_id'])
            if song:
                song.chart_position = item['position']
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Chart updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    
@app.route('/admin/add_song', methods=['POST'])
@login_required
def add_song():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        title = request.form.get('title')
        artist_id = request.form.get('artist_id')
        genre = request.form.get('genre')
        album = request.form.get('album')
        
        # Validation
        if not all([title, artist_id, genre]):
            return jsonify({'success': False, 'message': 'Title, Artist and Genre are required'}), 400
        
        # Handle file upload
        cover_image = 'default_song.jpg'  # Default image
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"song_{title}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                cover_image = filename
        
        new_song = Song(
            title=title,
            artist_id=artist_id,
            genre=genre,
            album=album if album else None,
            cover_image=cover_image,
            spotify_link=request.form.get('spotify_link'),
            youtube_link=request.form.get('youtube_link')
        )
        
        db.session.add(new_song)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Song added successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/edit_song/<int:song_id>', methods=['POST'])
@login_required
def edit_song(song_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    song = Song.query.get_or_404(song_id)
    
    try:
        song.title = request.form.get('title')
        song.artist_id = request.form.get('artist_id')
        song.genre = request.form.get('genre')
        song.album = request.form.get('album')
        song.spotify_link = request.form.get('spotify_link')
        song.youtube_link = request.form.get('youtube_link')
        
        # Handle file upload
        if 'cover_image' in request.files:
            file = request.files['cover_image']
            if file and allowed_file(file.filename):
                filename = secure_filename(f"song_{song.title}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                song.cover_image = filename
        
        db.session.commit()
        return jsonify({'success': True, 'message': 'Song updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/delete_song/<int:song_id>', methods=['DELETE'])
@login_required
def delete_song(song_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    song = Song.query.get_or_404(song_id)
    
    try:
        db.session.delete(song)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Song deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    
@app.route('/api/artists', methods=['GET'])
def get_artists():
    artists = Artist.query.order_by(Artist.name).all()
    return jsonify([{'id': a.id, 'name': a.name} for a in artists])

@app.route('/api/artists', methods=['POST'])
@login_required
def create_artist():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify({'success': False, 'message': 'Artist name required'}), 400
    
    try:
        new_artist = Artist(
            name=data['name'],
            bio=data.get('bio', ''),
            image='artist_default.jpg'
        )
        db.session.add(new_artist)
        db.session.commit()
        return jsonify({'success': True, 'artist': {'id': new_artist.id, 'name': new_artist.name}})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
@app.route('/charts')
def charts():
    # Get current top 20 songs ordered by chart position
    top_songs = Song.query.filter(Song.chart_position != None)\
                        .order_by(Song.chart_position)\
                        .limit(20)\
                        .all()
    
    # Format the current date
    current_date = datetime.now().strftime('%B %d, %Y')
    
    return render_template('charts.html', 
                         top_songs=top_songs,
                         current_date=current_date)

# --- Voting Event Routes ---
@app.route('/admin/voting_events')
@login_required
def voting_events():
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    events = VoteEvent.query.order_by(VoteEvent.start_date.desc()).all()
    return render_template('voting_events.html', events=events)

@app.route('/admin/create_voting_event', methods=['GET', 'POST'])
@login_required
def create_voting_event():
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            category = request.form.get('category')
            end_date_str = request.form.get('end_date')
            
            # Convert string to datetime
            end_date = datetime.strptime(end_date_str, '%Y-%m-%dT%H:%M')
            
            new_event = VoteEvent(
                title=title,
                category=category,
                end_date=end_date
            )
            
            db.session.add(new_event)
            db.session.commit()
            
            flash('Voting event created successfully!', 'success')
            return redirect(url_for('voting_events'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating event: {str(e)}', 'error')
    
    return render_template('create_voting_event.html')

@app.route('/admin/add_options/<int:event_id>', methods=['GET', 'POST'])
@login_required
def add_voting_options(event_id):
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    event = VoteEvent.query.get_or_404(event_id)
    
    if request.method == 'POST':
        try:
            # For song voting
            if event.category in ['song', 'song_of_year']:
                song_ids = request.form.getlist('song_options')
                for song_id in song_ids:
                    option = VoteOption(
                        vote_event_id=event.id,
                        song_id=song_id
                    )
                    db.session.add(option)
            
            # For artist voting
            elif event.category in ['artist', 'artist_of_year']:
                artist_ids = request.form.getlist('artist_options')
                for artist_id in artist_ids:
                    option = VoteOption(
                        vote_event_id=event.id,
                        artist_id=artist_id
                    )
                    db.session.add(option)
            
            db.session.commit()
            flash('Options added successfully!', 'success')
            return redirect(url_for('voting_events'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding options: {str(e)}', 'error')
    
    # Get appropriate options based on category
    if event.category in ['song', 'song_of_year']:
        options = Song.query.order_by(Song.title).all()
        return render_template('add_song_options.html', event=event, options=options)
    else:
        options = Artist.query.order_by(Artist.name).all()
        return render_template('add_artist_options.html', event=event, options=options)

@app.route('/admin/close_event/<int:event_id>')
@login_required
def close_voting_event(event_id):
    if current_user.role != 'admin':
        flash('You are not authorized to perform this action', 'error')
        return redirect(url_for('home'))
    
    event = VoteEvent.query.get_or_404(event_id)
    event.is_active = False
    db.session.commit()
    
    flash('Voting event closed successfully', 'success')
    return redirect(url_for('voting_events'))

@app.route('/vote')
def vote_home():
    # Get active and past voting events
    active_events = VoteEvent.query.filter(
        VoteEvent.is_active == True,
        VoteEvent.end_date > datetime.utcnow()
    ).all()
    
    past_events = VoteEvent.query.filter(
        (VoteEvent.is_active == False) | 
        (VoteEvent.end_date <= datetime.utcnow())
    ).order_by(VoteEvent.end_date.desc()).all()
    
    return render_template('vote_home.html', 
                         active_events=active_events,
                         past_events=past_events)

@app.route('/vote/event/<int:event_id>')
def view_voting_event(event_id):
    event = VoteEvent.query.get_or_404(event_id)
    options = VoteOption.query.filter_by(vote_event_id=event_id).all()
    
    # Check if user has already voted (by IP)
    ip_address = request.remote_addr
    has_voted = VoteRecord.query.filter_by(
        vote_event_id=event_id,
        ip_address=ip_address
    ).first() is not None
    
    # For past events, get the winner
    winner = None
    if not event.is_active or datetime.utcnow() > event.end_date:
        result = VoteResult.query.filter_by(vote_event_id=event.id).first()
        if result:
            if event.category in ['song', 'song_of_year']:
                winner = Song.query.get(result.winner_id)
            else:
                winner = Artist.query.get(result.winner_id)
    
    return render_template('view_event.html',
                         event=event,
                         options=options,
                         has_voted=has_voted,
                         winner=winner)

@app.route('/vote/submit/<int:event_id>', methods=['POST'])
def submit_vote(event_id):
    event = VoteEvent.query.get_or_404(event_id)
    option_id = request.form.get('option_id')
    
    # Validate event is active
    if not event.is_active or datetime.utcnow() > event.end_date:
        flash('This voting event is no longer active', 'error')
        return redirect(url_for('view_voting_event', event_id=event_id))
    
    # Check IP hasn't voted already
    ip_address = request.remote_addr
    existing_vote = VoteRecord.query.filter_by(
        vote_event_id=event_id,
        ip_address=ip_address
    ).first()
    
    if existing_vote:
        flash('You have already voted in this event', 'error')
        return redirect(url_for('view_voting_event', event_id=event_id))
    
    # Record the vote
    try:
        # Update vote count
        option = VoteOption.query.get(option_id)
        option.vote_count += 1
        db.session.add(option)
        
        # Record the vote
        new_vote = VoteRecord(
            vote_event_id=event_id,
            option_id=option_id,
            ip_address=ip_address
        )
        db.session.add(new_vote)
        
        db.session.commit()
        flash('Your vote has been recorded!', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while recording your vote', 'error')
    
    return redirect(url_for('view_voting_event', event_id=event_id))

@app.route('/admin/announce_winner/<int:event_id>')
@login_required
def announce_winner(event_id):
    if current_user.role != 'admin':
        flash('You are not authorized to perform this action', 'error')
        return redirect(url_for('home'))
    
    event = VoteEvent.query.get_or_404(event_id)
    
    # Find the option with most votes
    winner_option = VoteOption.query.filter_by(vote_event_id=event_id)\
                                 .order_by(VoteOption.vote_count.desc())\
                                 .first()
    
    if not winner_option:
        flash('No votes have been cast for this event', 'error')
        return redirect(url_for('voting_events'))
    
    # Record the winner
    winner_type = 'song' if event.category in ['song', 'song_of_year'] else 'artist'
    winner_id = winner_option.song_id if winner_type == 'song' else winner_option.artist_id
    
    result = VoteResult(
        vote_event_id=event_id,
        winner_id=winner_id,
        winner_type=winner_type,
        votes_received=winner_option.vote_count
    )
    
    # Close the event
    event.is_active = False
    
    try:
        db.session.add(result)
        db.session.commit()
        flash('Winner announced successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error announcing winner: {str(e)}', 'error')
    
    return redirect(url_for('voting_events'))

# --- Artist Management Routes ---
@app.route('/admin/artists')
@login_required
def manage_artists():
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    # Get all artists with their song and gig counts
    artists = db.session.query(
        Artist,
        db.func.count(Song.id).label('song_count'),
        db.func.count(Gig.id).label('gig_count')
    ).outerjoin(Song, Artist.id == Song.artist_id)\
     .outerjoin(Gig, Artist.id == Gig.artist_id)\
     .group_by(Artist.id)\
     .order_by(Artist.name)\
     .all()
    
    return render_template('manage_artists.html', artists=artists)

@app.route('/admin/add_artist', methods=['GET', 'POST'])
@login_required
def add_artist():
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            name = request.form.get('name')
            bio = request.form.get('bio')
            
            # Social media links
            social_media = {
                'facebook': request.form.get('facebook'),
                'twitter': request.form.get('twitter'),
                'instagram': request.form.get('instagram'),
                'youtube': request.form.get('youtube')
            }
            
            # Handle file upload
            image = 'artist_default.jpg'
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"artist_{name}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image = filename
            
            new_artist = Artist(
                name=name,
                bio=bio,
                image=image,
                social_media=social_media
            )
            
            db.session.add(new_artist)
            db.session.commit()
            
            flash('Artist added successfully!', 'success')
            return redirect(url_for('manage_artists'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding artist: {str(e)}', 'error')
    
    return render_template('add_artist.html')

@app.route('/admin/edit_artist/<int:artist_id>', methods=['GET', 'POST'])
@login_required
def edit_artist(artist_id):
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    artist = Artist.query.get_or_404(artist_id)
    
    if request.method == 'POST':
        try:
            artist.name = request.form.get('name')
            artist.bio = request.form.get('bio')
            
            # Update social media
            artist.social_media = {
                'facebook': request.form.get('facebook'),
                'twitter': request.form.get('twitter'),
                'instagram': request.form.get('instagram'),
                'youtube': request.form.get('youtube')
            }
            
            # Handle file upload
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"artist_{artist.name}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    artist.image = filename
            
            db.session.commit()
            flash('Artist updated successfully!', 'success')
            return redirect(url_for('manage_artists'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating artist: {str(e)}', 'error')
    
    return render_template('edit_artist.html', artist=artist)

@app.route('/admin/delete_artist/<int:artist_id>', methods=['POST'])
@login_required
def delete_artist(artist_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    artist = Artist.query.get_or_404(artist_id)
    
    try:
        db.session.delete(artist)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Artist deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# --- Gig Management Routes ---
@app.route('/admin/artist/<int:artist_id>/gigs')
@login_required
def manage_gigs(artist_id):
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    artist = Artist.query.get_or_404(artist_id)
    gigs = Gig.query.filter_by(artist_id=artist_id).order_by(Gig.date).all()
    
    return render_template('manage_gigs.html', artist=artist, gigs=gigs)

@app.route('/admin/add_gig/<int:artist_id>', methods=['POST'])
@login_required
def add_gig(artist_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({'success': False, 'message': 'No data received'}), 400
        
        venue = data.get('venue')
        city = data.get('city')
        date_str = data.get('date')
        
        # Validation
        if not all([venue, city, date_str]):
            return jsonify({'success': False, 'message': 'All fields are required'}), 400
        
        # Convert string to datetime
        date = datetime.strptime(date_str, '%Y-%m-%dT%H:%M')
        
        new_gig = Gig(
            artist_id=artist_id,
            venue=venue,
            city=city,
            date=date
        )
        
        db.session.add(new_gig)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Gig added successfully'})
    except ValueError as e:
        return jsonify({'success': False, 'message': 'Invalid date format'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/delete_gig/<int:gig_id>', methods=['DELETE'])
@login_required
def delete_gig(gig_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    gig = Gig.query.get_or_404(gig_id)
    
    try:
        db.session.delete(gig)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Gig deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500
    
    # --- Journalist News Routes ---
@app.route('/journalist/articles')
@login_required
def journalist_articles():
    if current_user.role not in ['journalist', 'senior_journalist', 'junior_journalist']:
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    articles = News.query.filter_by(user_id=current_user.id).order_by(News.date_posted.desc()).all()
    return render_template('journalist_articles.html', articles=articles)

@app.route('/journalist/article/new', methods=['GET', 'POST'])
@login_required
def new_article():
    if current_user.role not in ['journalist', 'senior_journalist', 'junior_journalist']:
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        try:
            title = request.form.get('title')
            content = request.form.get('content')
            category = request.form.get('category')
            
            if not all([title, content, category]):
                flash('All fields are required', 'error')
                return redirect(url_for('new_article'))
            
            # Handle file upload
            image = 'default_news.jpg'
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"news_{datetime.now().timestamp()}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    image = filename
            
            new_article = News(
                title=title,
                content=content,
                category=category,
                image=image,
                user_id=current_user.id,
                is_published=False  # Needs admin approval
            )
            
            db.session.add(new_article)
            db.session.commit()
            flash('Article created successfully! Waiting for admin approval.', 'success')
            return redirect(url_for('journalist_articles'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating article: {str(e)}', 'error')
    
    categories = ['Events', 'Releases', 'Interviews', 'Reviews', 'Culture']
    return render_template('create_article.html', categories=categories)

@app.route('/journalist/article/edit/<int:article_id>', methods=['GET', 'POST'])
@login_required
def edit_article(article_id):
    article = News.query.get_or_404(article_id)
    
    # Check ownership
    if article.user_id != current_user.id:
        flash('You are not authorized to edit this article', 'error')
        return redirect(url_for('journalist_articles'))
    
    if request.method == 'POST':
        try:
            article.title = request.form.get('title')
            article.content = request.form.get('content')
            article.category = request.form.get('category')
            
            # Handle file upload
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"news_{datetime.now().timestamp()}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    article.image = filename
            
            db.session.commit()
            flash('Article updated successfully!', 'success')
            return redirect(url_for('journalist_articles'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating article: {str(e)}', 'error')
    
    categories = ['Events', 'Releases', 'Interviews', 'Reviews', 'Culture']
    return render_template('edit_article.html', article=article, categories=categories)

@app.route('/journalist/article/delete/<int:article_id>', methods=['POST'])
@login_required
def delete_article(article_id):
    article = News.query.get_or_404(article_id)
    
    # Check ownership
    if article.user_id != current_user.id:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    try:
        db.session.delete(article)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Article deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/journalist/article/preview/<int:article_id>')
@login_required
def preview_article(article_id):
    article = News.query.get_or_404(article_id)
    
    # Check ownership
    if article.user_id != current_user.id:
        flash('You are not authorized to view this article', 'error')
        return redirect(url_for('journalist_articles'))
    
    return render_template('article_preview.html', article=article)

# --- Admin News Moderation Routes ---
@app.route('/admin/news')
@login_required
def admin_news():
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    # Get all news articles with author information
    news_articles = db.session.query(News, User)\
                            .join(User, News.user_id == User.id)\
                            .order_by(News.date_posted.desc())\
                            .all()
    
    return render_template('admin_news.html', news_articles=news_articles)

@app.route('/admin/news/publish/<int:article_id>')
@login_required
def publish_article(article_id):
    if current_user.role != 'admin':
        flash('You are not authorized to perform this action', 'error')
        return redirect(url_for('home'))
    
    article = News.query.get_or_404(article_id)
    article.is_published = True
    db.session.commit()
    
    flash('Article published successfully!', 'success')
    return redirect(url_for('admin_news'))

@app.route('/admin/news/unpublish/<int:article_id>')
@login_required
def unpublish_article(article_id):
    if current_user.role != 'admin':
        flash('You are not authorized to perform this action', 'error')
        return redirect(url_for('home'))
    
    article = News.query.get_or_404(article_id)
    article.is_published = False
    db.session.commit()
    
    flash('Article unpublished successfully!', 'success')
    return redirect(url_for('admin_news'))

@app.route('/admin/news/edit/<int:article_id>', methods=['GET', 'POST'])
@login_required
def admin_edit_article(article_id):
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    article = News.query.get_or_404(article_id)
    
    if request.method == 'POST':
        try:
            article.title = request.form.get('title')
            article.content = request.form.get('content')
            article.category = request.form.get('category')
            
            # Handle file upload
            if 'image' in request.files:
                file = request.files['image']
                if file and allowed_file(file.filename):
                    filename = secure_filename(f"news_{datetime.now().timestamp()}_{file.filename}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    article.image = filename
            
            db.session.commit()
            flash('Article updated successfully!', 'success')
            return redirect(url_for('admin_news'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating article: {str(e)}', 'error')
    
    categories = ['Events', 'Releases', 'Interviews', 'Reviews', 'Culture']
    return render_template('admin_edit_article.html', article=article, categories=categories)

@app.route('/admin/news/delete/<int:article_id>', methods=['POST'])
@login_required
def admin_delete_article(article_id):
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Unauthorized'}), 403
    
    article = News.query.get_or_404(article_id)
    
    try:
        db.session.delete(article)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Article deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/news/stats')
@login_required
def news_stats():
    if current_user.role != 'admin':
        flash('You are not authorized to access this page', 'error')
        return redirect(url_for('home'))
    
    # Get basic stats
    total_articles = News.query.count()
    published_articles = News.query.filter_by(is_published=True).count()
    pending_articles = News.query.filter_by(is_published=False).count()
    
    # Get top performing articles
    top_articles = News.query.order_by(News.views.desc()).limit(5).all()
    
    # Get articles by category
    categories = db.session.query(
        News.category,
        db.func.count(News.id).label('count')
    ).group_by(News.category).all()
    
    return render_template('news_stats.html',
                         total_articles=total_articles,
                         published_articles=published_articles,
                         pending_articles=pending_articles,
                         top_articles=top_articles,
                         categories=categories)

# --- DB init ---
def create_database():
    with app.app_context():
        db.create_all()
        create_admin()
        print("Database initialized successfully!")

if __name__ == '__main__':
    create_database()
    app.run(debug=True)